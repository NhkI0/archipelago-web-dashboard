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

from .config import find_multiworld_file, load_config, public_config, tag_ids
from .hall_of_fame import load_entries as load_hall_of_fame
from .multidata import load_multidata
from .session import SessionManager
from .state import WorldState
from .tracker import Tracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("ap.web")

# ── Config ────────────────────────────────────────────────────────────────────
#
# Values come from config.toml (see server/config.py); environment variables
# still override them for hosts that prefer env-based config over editing the file.

CONFIG = load_config()


def _env_or(cfg_val: Any, env_key: str, cast=str) -> Any:
    raw = os.environ.get(env_key)
    return cast(raw) if raw is not None else cfg_val


_data_dir = pathlib.Path(CONFIG["paths"]["data_dir"])
_multiworld = CONFIG["server"]["multiworld_dir"]
try:
    AP_FILE = os.environ.get("AP_FILE") or find_multiworld_file(_multiworld)
except FileNotFoundError as e:
    log.error("=" * 78)
    log.error("NO MULTIWORLD FOUND")
    log.error(str(e))
    log.error(
        "Did you forget to drop your generated .archipelago file into %s ?",
        pathlib.Path(_multiworld).resolve(),
    )
    log.error("=" * 78)
    raise SystemExit(1) from None
AP_HOST_YAML = os.environ.get("AP_HOST_YAML") or (
    CONFIG["paths"]["host_yaml"] or str(pathlib.Path(_multiworld).parent / "host.yaml")
    if pathlib.Path(_multiworld).is_file()
    else CONFIG["paths"]["host_yaml"] or str(pathlib.Path(_multiworld) / "host.yaml")
)
DEATHS_FILE = os.environ.get("DEATHS_FILE") or str(_data_dir / "death_leaderboard.json")
ITEMS_FILE = os.environ.get("ITEMS_FILE") or str(_data_dir / "received_items.json")
TAGS_FILE = os.environ.get("TAGS_FILE") or str(_data_dir / "hint_tags.json")
ASSETS_DIR = pathlib.Path(CONFIG["paths"]["assets_dir"])
HALL_OF_FAME_DIR = pathlib.Path(CONFIG["paths"]["hall_of_fame_dir"])


def _read_server_options_from_host_yaml(path: str) -> dict[str, str]:
    """Parse scalars under `server_options:` from Archipelago's host.yaml.

    Tiny ad-hoc YAML parse: we only need single-line scalars under a known
    section, so avoiding a PyYAML dependency keeps the web service slim.
    Values are returned as raw strings; callers cast as needed.
    """
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fp:
            in_server_options = False
            for line in fp:
                stripped = line.split("#", 1)[0].rstrip()
                if not stripped:
                    continue
                if not line.startswith((" ", "\t")):
                    in_server_options = stripped.rstrip(":") == "server_options"
                    continue
                if in_server_options and ":" in stripped:
                    key, _, value = stripped.strip().partition(":")
                    out[key.strip()] = value.strip()
    except OSError:
        return out
    return out


def _coerce_yaml_scalar(raw: str) -> str:
    """Strip quotes and turn YAML null sentinels into empty strings."""
    s = raw.strip()
    if s.lower() in ("null", "~", ""):
        return ""
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    return s

STATIC_DIR = pathlib.Path(os.environ.get("WEB_DIST", pathlib.Path(__file__).parent.parent / "frontend" / "dist"))


# ── State ─────────────────────────────────────────────────────────────────────

try:
    multidata = load_multidata(AP_FILE)
except Exception as e:
    log.error("=" * 78)
    log.error("COULD NOT READ %s AS A MULTIDATA FILE", AP_FILE)
    log.error("Reason: %s", e)
    log.error("It may be corrupt, truncated, or not actually a *.archipelago file,")
    log.error("try re-downloading it from the room/generation you're hosting.")
    log.error("=" * 78)
    raise SystemExit(1) from None
world = WorldState(
    multidata,
    items_file=pathlib.Path(ITEMS_FILE),
    tags_file=pathlib.Path(TAGS_FILE),
    allowed_tags=tag_ids(CONFIG),
)
_host_yaml_found = pathlib.Path(AP_HOST_YAML).is_file()
_server_opts = _read_server_options_from_host_yaml(AP_HOST_YAML) if _host_yaml_found else {}
try:
    _hc = int(_server_opts["hint_cost"])
    world.hint_cost = _hc
    log.info("hint_cost = %d%% (from %s)", _hc, AP_HOST_YAML)
except (KeyError, ValueError):
    log.warning("could not read hint_cost from %s; using default %d%%", AP_HOST_YAML, world.hint_cost)

# AP_HOST/AP_PORT/AP_PASSWORD: an explicit env override always wins. Otherwise,
# a host.yaml found next to the multiworld file means
# the multiworld is running locally — connect to localhost using its own port
# (and password, read above). No host.yaml means the multiworld runs elsewhere;
# fall back to [server.remote] in config.toml, since there's no local host.yaml
# to read a port/password from.
_remote = CONFIG["server"]["remote"]
if os.environ.get("AP_HOST") or os.environ.get("AP_PORT"):
    AP_HOST = _env_or(CONFIG["server"]["ap_host"], "AP_HOST")
    AP_PORT = int(_env_or(CONFIG["server"]["ap_port"], "AP_PORT", int))
    AP_PASSWORD = os.environ.get("AP_PASSWORD") or _coerce_yaml_scalar(_server_opts.get("password", ""))
    AP_SECURE = os.environ.get("AP_SECURE", "").lower() in ("1", "true", "yes")
elif _host_yaml_found:
    log.info("host.yaml found at %s; connecting to the local multiworld", AP_HOST_YAML)
    AP_HOST = CONFIG["server"]["ap_host"]
    try:
        AP_PORT = int(_server_opts["port"])
    except (KeyError, ValueError):
        AP_PORT = int(CONFIG["server"]["ap_port"])
    AP_PASSWORD = os.environ.get("AP_PASSWORD") or _coerce_yaml_scalar(_server_opts.get("password", ""))
    AP_SECURE = False
else:
    if not _remote.get("host"):
        raise RuntimeError(
            f"no host.yaml found at {AP_HOST_YAML} and no [server.remote].host set in "
            f"config.toml, either drop host.yaml next to your .archipelago file, or set "
            f"[server.remote] to the address of the remotely hosted multiworld"
        )
    log.info("no host.yaml at %s; connecting to remote multiworld at %s:%s", AP_HOST_YAML, _remote["host"], _remote["port"])
    AP_HOST = _remote["host"]
    AP_PORT = int(_remote["port"])
    AP_PASSWORD = os.environ.get("AP_PASSWORD") or _remote.get("password", "")
    # Public rooms (archipelago.gg and most hosted ones) are wss:// — a plain
    # ws:// client against a TLS port fails with a garbled handshake, which
    # shows up as "did not receive a valid HTTP response" on every slot.
    AP_SECURE = bool(_remote.get("tls", True))
if AP_PASSWORD:
    log.info("server password loaded (%d chars)", len(AP_PASSWORD))
log.info("connecting to %s:%s (%s)", AP_HOST, AP_PORT, "wss" if AP_SECURE else "ws")
world.set_server_status(AP_HOST, AP_PORT, False)
tracker = Tracker(
    world,
    host=AP_HOST,
    port=AP_PORT,
    password=AP_PASSWORD,
    secure=AP_SECURE,
    deaths_file=pathlib.Path(DEATHS_FILE),
    on_connection_change=lambda connected: world.set_server_status(AP_HOST, AP_PORT, connected),
)
sessions = SessionManager(host=AP_HOST, port=AP_PORT, multidata=multidata, secure=AP_SECURE)

app = FastAPI(title="Archipelago Web", version="0.1.0")


@app.on_event("startup")
async def _on_start() -> None:
    tracker.start()


@app.on_event("shutdown")
async def _on_stop() -> None:
    await tracker.stop()


# ── REST ──────────────────────────────────────────────────────────────────────

def _asset_url(name: str) -> str:
    """Resolve a branding image name to a servable URL.

    A host file dropped into ``assets_dir`` wins (served under /host/); otherwise
    the name is served from the bundled frontend at the site root. Absolute URLs
    and paths are passed through untouched.
    """
    if not name or name.startswith(("http://", "https://", "/")):
        return name
    if (ASSETS_DIR / name).is_file():
        return f"/host/{name}"
    return f"/{name}"


@app.get("/api/config")
async def api_config() -> dict[str, Any]:
    payload = public_config(CONFIG)
    payload["branding"]["hero_image"] = _asset_url(payload["branding"].get("hero_image", ""))
    return payload


@app.get("/api/hall_of_fame")
async def api_hall_of_fame() -> list[dict[str, Any]]:
    return load_hall_of_fame(HALL_OF_FAME_DIR)


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
    from collections import Counter
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


# ── Live updates ──────────────────────────────────────────────────────────────

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
    # the slot we last lit so we can both react to logout (session vanishes
    # while the socket stays open) and always release on disconnect.
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
                pass  # idle tick — fall through to re-check the session
            sync_presence()

    async def watch_disconnect() -> None:
        # Reading the socket is the only way to notice a client close promptly
        # when no world events are flowing;
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


# ── Auth + hints ──────────────────────────────────────────────────────────────

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
    # Tags live on a receiver's "For my world" hints, so only the receiving
    # slot may tag its own incoming items.
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


# ── Static frontend ───────────────────────────────────────────────────────────

# Host-droppable images (hero/border image, etc.) — served under /host/ so a
# host can swap branding assets without rebuilding the frontend.
if ASSETS_DIR.is_dir():
    app.mount("/host", StaticFiles(directory=ASSETS_DIR), name="host")

# Hall of Fame images — dropped by the host, described in entries.toml (see
# server/hall_of_fame.py), no rebuild needed.
if HALL_OF_FAME_DIR.is_dir():
    app.mount("/hall-of-fame", StaticFiles(directory=HALL_OF_FAME_DIR), name="hall_of_fame")

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        # Serve any real file at the top of dist/ (favicon.ico, robots.txt,
        # public assets like /games/<slug>.png, etc.) before falling back to the SPA shell.
        if full_path:
            candidate = (STATIC_DIR / full_path).resolve()
            try:
                candidate.relative_to(STATIC_DIR.resolve())
            except ValueError:
                candidate = None  # path traversal, refuse
            if candidate and candidate.is_file():
                return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        if not index.exists():
            return JSONResponse({"error": "frontend not built"}, status_code=503)
        return FileResponse(index)
