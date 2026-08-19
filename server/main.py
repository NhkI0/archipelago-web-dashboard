"""
FastAPI app builder: REST + WebSocket bridge between browsers and the AP server.

Self-hosted entrypoint: `python -m server` (see `server/__main__.py`), which
resolves a `RoomConfig` from `config.toml` + env vars and calls `build_app()`.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any

from fastapi import Cookie, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import RoomConfig, public_config, tag_ids
from .hall_of_fame import load_entries as load_hall_of_fame
from .multidata import load_multidata
from .session import SessionManager
from .state import WorldState
from .tracker import Tracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("ap.web")


class LoginBody(BaseModel):
    slot: str
    password: str = ""


class HintBody(BaseModel):
    kind: str         # "item" | "location"
    target: str       # item or location name as the AP server expects it


class HintTagBody(BaseModel):
    finding_slot: int
    receiving_slot: int
    item_id: int
    location_id: int
    tag: str = ""     # one of state.HINT_TAGS, or "" to clear


def build_app(room: RoomConfig) -> FastAPI:
    """Build one room's FastAPI app from an already-resolved `RoomConfig`.

    Raises whatever `load_multidata` raises on a bad/corrupt `.archipelago` file
    the caller decides how to report that (the CLI entrypoint exits loudly;
    the hosted supervisor marks the room creation as failed).
    """
    try:
        multidata = load_multidata(room.ap_file)
    except Exception as e:
        log.error("=" * 78)
        log.error("COULD NOT READ %s AS A MULTIDATA FILE", room.ap_file)
        log.error("Reason: %s", e)
        log.error("It may be corrupt, truncated, or not actually a *.archipelago file,")
        log.error("try re-downloading it from the room/generation you're hosting.")
        log.error("=" * 78)
        raise

    world = WorldState(
        multidata,
        items_file=room.items_file,
        tags_file=room.tags_file,
        allowed_tags=tag_ids(room.config),
    )
    if room.hint_cost is not None:
        world.hint_cost = room.hint_cost

    tracker = Tracker(
        world,
        host=room.ap_host,
        port=room.ap_port,
        password=room.ap_password,
        secure=room.ap_secure,
        deaths_file=room.deaths_file,
    )
    sessions = SessionManager(host=room.ap_host, port=room.ap_port, multidata=multidata, secure=room.ap_secure)

    app = FastAPI(title="Archipelago Web", version="0.1.0")

    # lifecycle

    @app.on_event("startup")
    async def _on_start() -> None:
        tracker.start()

    @app.on_event("shutdown")
    async def _on_stop() -> None:
        await tracker.stop()

    # REST

    def _asset_url(name: str) -> str:
        """Resolve a branding image name to a servable URL.

        A host file dropped into ``assets_dir`` wins (served under /host/);
        otherwise the name is served from the bundled frontend at the site root.
        Absolute URLs and paths are passed through untouched.
        """
        if not name or name.startswith(("http://", "https://", "/")):
            return name
        if (room.assets_dir / name).is_file():
            return f"/host/{name}"
        return f"/{name}"

    @app.get("/api/config")
    async def api_config() -> dict[str, Any]:
        payload = public_config(room.config)
        payload["branding"]["hero_image"] = _asset_url(payload["branding"].get("hero_image", ""))
        return payload

    @app.get("/api/hall_of_fame")
    async def api_hall_of_fame() -> list[dict[str, Any]]:
        return load_hall_of_fame(room.hall_of_fame_dir)

    @app.get("/api/state")
    async def api_state() -> dict[str, Any]:
        return world.snapshot()

    @app.get("/api/deaths")
    async def api_deaths() -> dict[str, Any]:
        rows = tracker.death_rows()
        return {"available": bool(rows) or tracker.death_client_connected(), "rows": rows}

    @app.get("/api/slot/{name}")
    async def api_slot(name: str) -> dict[str, Any]:
        slot = next((s for s in world.slots.values() if s.name == name), None)
        if slot is None:
            raise HTTPException(404, "slot not found")
        md = world.multidata
        locs = md.locations.get(slot.slot, {})
        checked = slot.checked

        # Hints concerning this slot, either as finder or recipient
        related_hints = [
            h.to_dict()
            for h in world.hints
            if h.finding_slot == slot.slot or h.receiving_slot == slot.slot
        ]

        # locs is keyed by FINDER slot : slot.slot finds these in its own world,
        # but each item there belongs to the RECIPIENT's game (recv = the second tuple field).
        locations_payload = []
        for loc_id, (item_id, recv, _flags) in locs.items():
            locations_payload.append({
                "id": loc_id,
                "name": md.location_name(slot.slot, loc_id),
                "checked": loc_id in checked,
                "item_for_slot": recv,
                "item_name": md.item_name(recv, item_id) if any(
                    h["location_id"] == loc_id and h["finding_slot"] == slot.slot
                    for h in related_hints
                ) or loc_id in checked else None,
            })
        locations_payload.sort(key=lambda x: x["name"])

        # Items the slot will RECEIVE that haven't been sent yet: scan every world
        # for entries with recv==slot.slot whose finder location is unchecked.
        # Use counts so duplicate items still appear when only some copies have arrived.
        pending: Counter[str] = Counter()
        for finder_slot, table in md.locations.items():
            finder_checked = world.slots[finder_slot].checked if finder_slot in world.slots else set()
            for loc_id, (item_id, recv, _flags) in table.items():
                if recv == slot.slot and loc_id not in finder_checked:
                    pending[md.item_name(slot.slot, item_id)] += 1
        available_items = sorted(pending.elements())

        return {
            "slot": slot.to_dict(),
            "locations": locations_payload,
            "hints": related_hints,
            "available_items": available_items,
            "received_items": world.received_for(slot.slot),
        }

    # Live updates

    def _slot_num_for_session(sid: str | None) -> int | None:
        """Resolve a session cookie to its slot number, if logged in."""
        if not sid:
            return None
        sess = sessions.get(sid)
        if not sess:
            return None
        slot_info = world.multidata.slot_by_name(sess.slot)
        return slot_info.slot if slot_info else None

    @app.websocket("/ws/live")
    async def ws_live(ws: WebSocket) -> None:
        await ws.accept()
        queue = world.subscribe()
        sid = ws.cookies.get("ap_session")
        # Presence (the green dot) follows this socket's logged-in session. We hold
        # the slot we last lit so we can both react to logout
        # (session vanishes while the socket stays open) and always release on disconnect.
        present_slot: int | None = None

        def sync_presence() -> None:
            nonlocal present_slot
            slot_num = _slot_num_for_session(sid)
            if slot_num == present_slot:
                return
            if present_slot is not None:
                world.remove_presence(present_slot)
            if slot_num is not None:
                world.add_presence(slot_num)
            present_slot = slot_num

        async def pump() -> None:
            await ws.send_json({"type": "snapshot", "snapshot": world.snapshot()})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=5.0)
                    await ws.send_json(event)
                except asyncio.TimeoutError:
                    pass  # idle tick; fall through to re-check the session
                sync_presence()

        async def watch_disconnect() -> None:
            # Reading the socket is the only way to notice a client close promptly when no world events are flowing;
            # without it a dropped tab would keep its dot lit until the next unrelated emit.
            try:
                while True:
                    await ws.receive()
            except WebSocketDisconnect:
                return

        sync_presence()
        tasks = [asyncio.create_task(pump()), asyncio.create_task(watch_disconnect())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
            world.unsubscribe(queue)
            if present_slot is not None:
                world.remove_presence(present_slot)

    # Auth + hints

    @app.post("/api/login")
    async def api_login(body: LoginBody, response: Response) -> dict[str, Any]:
        slot_info = world.multidata.slot_by_name(body.slot)
        if slot_info is None:
            raise HTTPException(404, f"unknown slot {body.slot!r}")
        try:
            sess = await sessions.login(body.slot, body.password, slot_info.game)
        except PermissionError as e:
            raise HTTPException(401, str(e))
        except ConnectionError as e:
            raise HTTPException(503, str(e))
        response.set_cookie(
            "ap_session",
            sess.sid,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 8,
        )
        return {
            "ok": True,
            "slot": sess.slot,
            "game": slot_info.game,
            "hint_points": sess.hint_points,
        }

    @app.post("/api/logout")
    async def api_logout(response: Response, ap_session: str | None = Cookie(default=None)) -> dict[str, Any]:
        if ap_session:
            await sessions.logout(ap_session)
        response.delete_cookie("ap_session")
        return {"ok": True}

    @app.post("/api/hint")
    async def api_hint(body: HintBody, ap_session: str | None = Cookie(default=None)) -> dict[str, Any]:
        if not ap_session:
            raise HTTPException(401, "not logged in")
        sess = sessions.get(ap_session)
        if not sess:
            raise HTTPException(401, "session expired")
        if body.kind not in ("item", "location"):
            raise HTTPException(400, "kind must be 'item' or 'location'")
        result = await sessions.send_hint(ap_session, body.kind, body.target)
        return {**result, "hint_points": sess.hint_points}

    @app.post("/api/hint_tag")
    async def api_hint_tag(body: HintTagBody, ap_session: str | None = Cookie(default=None)) -> dict[str, Any]:
        if not ap_session:
            raise HTTPException(401, "not logged in")
        slot_num = _slot_num_for_session(ap_session)
        if slot_num is None:
            raise HTTPException(401, "session expired")
        # Tags live on a receiver's "For my world" hints, so only the receiving slot may tag its own incoming items.
        if slot_num != body.receiving_slot:
            raise HTTPException(403, "you can only tag hints for your own world")
        try:
            applied = world.set_hint_tag(
                body.finding_slot, body.receiving_slot, body.item_id, body.location_id, body.tag
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
        if not applied:
            raise HTTPException(404, "hint not found")
        return {"ok": True, "tag": body.tag}

    @app.get("/api/me")
    async def api_me(ap_session: str | None = Cookie(default=None)) -> dict[str, Any]:
        if not ap_session:
            return {"logged_in": False}
        sess = sessions.get(ap_session)
        if not sess:
            return {"logged_in": False}
        return {
            "logged_in": True,
            "slot": sess.slot,
            "hint_points": sess.hint_points,
            "last_text": sess.last_text,
        }

    # Static frontend

    # Host-droppable images (hero/border image, etc.)
    # served under /host/ so a host can swap branding assets without rebuilding the frontend.
    if room.assets_dir.is_dir():
        app.mount("/host", StaticFiles(directory=room.assets_dir), name="host")

    # Hall of Fame images dropped by the host, described in entries.toml
    # (see server/hall_of_fame.py), no rebuild needed.
    if room.hall_of_fame_dir.is_dir():
        app.mount("/hall-of-fame", StaticFiles(directory=room.hall_of_fame_dir), name="hall_of_fame")

    if room.static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=room.static_dir / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str) -> FileResponse:
            # Serve any real file at the top of dist/ (favicon.ico, robots.txt,
            # public assets like /games/<slug>.png, etc.) before falling back to the SPA shell.
            if full_path:
                candidate = (room.static_dir / full_path).resolve()
                try:
                    candidate.relative_to(room.static_dir.resolve())
                except ValueError:
                    candidate = None  # path traversal, refuse
                if candidate and candidate.is_file():
                    return FileResponse(candidate)
            index = room.static_dir / "index.html"
            if not index.exists():
                return JSONResponse({"error": "frontend not built"}, status_code=503)
            return FileResponse(index)

    return app
