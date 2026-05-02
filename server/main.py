"""
FastAPI app: REST + WebSocket bridge between browsers and the AP server.

Run with:
    uvicorn server.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
from typing import Any

from fastapi import Cookie, FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .multidata import load_multidata
from .session import SessionManager
from .state import WorldState
from .tracker import Tracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("ap.web")

# ── Config ────────────────────────────────────────────────────────────────────

AP_HOST = os.environ.get("AP_HOST", "localhost")
AP_PORT = int(os.environ.get("AP_PORT", "38281"))
AP_FILE = os.environ.get("AP_FILE", "/opt/archipelago/output/latest.archipelago")
AP_TRACKER_SLOT = os.environ.get("AP_TRACKER_SLOT", "DeathTracker")

STATIC_DIR = pathlib.Path(os.environ.get("WEB_DIST", pathlib.Path(__file__).parent.parent / "frontend" / "dist"))


# ── State ─────────────────────────────────────────────────────────────────────

multidata = load_multidata(AP_FILE)
world = WorldState(multidata)
tracker = Tracker(world, host=AP_HOST, port=AP_PORT, slot_name=AP_TRACKER_SLOT)
sessions = SessionManager(host=AP_HOST, port=AP_PORT)

app = FastAPI(title="Archipelago Web", version="0.1.0")


@app.on_event("startup")
async def _on_start() -> None:
    tracker.start()


@app.on_event("shutdown")
async def _on_stop() -> None:
    await tracker.stop()


# ── REST ──────────────────────────────────────────────────────────────────────

@app.get("/api/state")
async def api_state() -> dict[str, Any]:
    return world.snapshot()


@app.get("/api/slot/{name}")
async def api_slot(name: str) -> dict[str, Any]:
    slot = next((s for s in world.slots.values() if s.name == name), None)
    if slot is None:
        raise HTTPException(404, "slot not found")
    md = world.multidata
    locs = md.locations.get(slot.slot, {})
    checked = slot.checked

    # Hints concerning this slot — either as finder or recipient
    related_hints = [
        h.to_dict()
        for h in world.hints
        if h.finding_slot == slot.slot or h.receiving_slot == slot.slot
    ]

    locations_payload = []
    for loc_id, (item_id, sender, _flags) in locs.items():
        locations_payload.append({
            "id": loc_id,
            "name": md.location_name(slot.slot, loc_id),
            "checked": loc_id in checked,
            # Don't leak item identity unless the location is hinted/checked
            "item_for_slot": sender,
            "item_name": md.item_name(sender, item_id) if any(
                h["location_id"] == loc_id and h["finding_slot"] == slot.slot
                for h in related_hints
            ) or loc_id in checked else None,
        })
    locations_payload.sort(key=lambda x: x["name"])

    return {
        "slot": slot.to_dict(),
        "locations": locations_payload,
        "hints": related_hints,
    }


# ── Live updates ──────────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await ws.accept()
    queue = world.subscribe()
    try:
        await ws.send_json({"type": "snapshot", "snapshot": world.snapshot()})
        while True:
            event = await queue.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        world.unsubscribe(queue)


# ── Auth + hints ──────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    slot: str
    password: str = ""


class HintBody(BaseModel):
    kind: str         # "item" | "location"
    target: str       # item or location name as the AP server expects it


@app.post("/api/login")
async def api_login(body: LoginBody, response: Response) -> dict[str, Any]:
    slot_info = world.multidata.slot_by_name(body.slot)
    if slot_info is None:
        raise HTTPException(404, f"unknown slot {body.slot!r}")
    try:
        sess = await sessions.login(body.slot, body.password, slot_info.game)
    except PermissionError as e:
        raise HTTPException(401, str(e))
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


# ── Static frontend ───────────────────────────────────────────────────────────

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        # SPA fallback — every non-/api route serves index.html
        index = STATIC_DIR / "index.html"
        if not index.exists():
            return JSONResponse({"error": "frontend not built"}, status_code=503)
        return FileResponse(index)
