"""
Per-browser AP WebSocket sessions.

When a player logs in via /api/login the backend opens a dedicated AP WS as
that slot, keeps it open, and returns a session id. /api/hint uses the open
socket to issue `!hint <item>` / `!hint_location <location>` chat commands;
the AP server charges them to the slot's hint points and broadcasts the
result, which the persistent Tracker connection picks up.

When `world` is given, this connection also feeds its own slot's checks and
received items into `WorldState` live, instead of waiting on RoomPoller's poll
cycle (a harmless no-op duplicate in self-hosted mode).
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

import websockets

from .hint_usage import HintUsageStore
from .multidata import MultiData
from .state import WorldState

log = logging.getLogger("ap.session")


def _render_print_json(parts: list[dict], md: "MultiData | None") -> str:
    """Resolve typed PrintJSON parts (player_id/item_id/location_id) to names."""
    out: list[str] = []
    for p in parts or []:
        ptype = p.get("type") or "text"
        text = p.get("text") or ""
        if md is None or ptype in ("text", "color"):
            out.append(text)
            continue
        try:
            num = int(text)
        except (TypeError, ValueError):
            out.append(text)
            continue
        if ptype == "player_id":
            slot = md.slots.get(num)
            out.append(slot.name if slot else text)
        elif ptype == "item_id":
            recv = int(p.get("player") or 0)
            out.append(md.item_name(recv, num))
        elif ptype == "location_id":
            send = int(p.get("player") or 0)
            out.append(md.location_name(send, num))
        else:
            out.append(text)
    return "".join(out)


@dataclass
class Session:
    sid: str
    slot: str
    ws: "websockets.WebSocketClientProtocol"
    inbox: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=64))
    hint_points: int = 0
    last_text: str = ""
    slot_num: int | None = None  # resolved at login; None if slot isn't in multidata

    async def close(self) -> None:
        try:
            await self.ws.close()
        except Exception:
            pass


class SessionManager:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 38281,
        multidata: "MultiData | None" = None,
        secure: bool = False,
        hint_usage: "HintUsageStore | None" = None,
        world: "WorldState | None" = None,
    ) -> None:
        self.uri = f"{'wss' if secure else 'ws'}://{host}:{port}"
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self.multidata = multidata
        # Only set for archipelago.gg-polled rooms
        # records a spend whenever a hint requested through this dashboard actually costs points,
        # so RoomPoller can estimate hint_points locally (see hint_usage.py).
        self.hint_usage = hint_usage
        self.world = world  # optional; see module docstring

    def get(self, sid: str) -> Session | None:
        return self._sessions.get(sid)

    async def login(self, slot: str, password: str = "", game: str = "") -> Session:
        try:
            ws = await websockets.connect(self.uri, max_size=2**24)
        except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException) as e:
            raise ConnectionError(f"AP server unreachable at {self.uri}: {e}") from e
        await ws.recv()  # RoomInfo

        await ws.send(json.dumps([{
            "cmd": "Connect",
            "password": password,
            "game": game or "Archipelago",
            "name": slot,
            "uuid": str(uuid.uuid4()),
            "tags": ["TextOnly"],
            "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
            "items_handling": 0b111,  # receive ReceivedItems (see _pump)
        }]))

        # Wait for Connected/Refused
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=8)
        except asyncio.TimeoutError:
            await ws.close()
            raise PermissionError("server did not reply to Connect")

        for packet in json.loads(raw):
            cmd = packet.get("cmd")
            if cmd == "Connected":
                sid = secrets.token_urlsafe(24)
                # hint_points sometimes ships on Connected; otherwise it lands
                # on the next RoomUpdate.
                hp = int(packet.get("hint_points", 0) or 0)
                slot_info = self.multidata.slot_by_name(slot) if self.multidata else None
                sess = Session(sid=sid, slot=slot, ws=ws, hint_points=hp,
                                slot_num=slot_info.slot if slot_info else None)
                self._sessions[sid] = sess
                if self.world is not None and sess.slot_num is not None:
                    cl = packet.get("checked_locations")
                    if isinstance(cl, list):
                        self.world.apply_slot_checks(sess.slot_num, [int(x) for x in cl], replace=True)
                asyncio.create_task(self._pump(sess), name=f"sess-{sid[:8]}")
                return sess
            if cmd == "ConnectionRefused":
                await ws.close()
                raise PermissionError(", ".join(packet.get("errors", []) or ["refused"]))

        await ws.close()
        raise PermissionError("unexpected reply from server")

    async def logout(self, sid: str) -> None:
        sess = self._sessions.pop(sid, None)
        if sess:
            await sess.close()

    async def send_hint(self, sid: str, kind: str, target: str) -> dict[str, Any]:
        sess = self._sessions.get(sid)
        if not sess:
            return {"ok": False, "error": "session expired"}
        if kind == "item":
            cmd = f"!hint {target}"
        elif kind == "location":
            cmd = f"!hint_location {target}"
        else:
            return {"ok": False, "error": f"unknown hint kind {kind!r}"}

        log.info("send_hint sid=%s slot=%s -> %r (hp=%d)", sid[:8], sess.slot, cmd, sess.hint_points)
        hint_points_before = sess.hint_points
        await sess.ws.send(json.dumps([{"cmd": "Say", "text": cmd}]))
        # Drain any replies that arrive within a window: AP often emits
        # several PrintJSON lines (chat echo, error, hint result).
        replies: list[str] = []
        deadline = asyncio.get_event_loop().time() + 4
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                replies.append(await asyncio.wait_for(sess.inbox.get(), timeout=remaining))
            except asyncio.TimeoutError:
                break
        log.info("send_hint sid=%s replies=%r", sid[:8], replies)

        # A real drop in the server-reported balance means the hint was
        # genuinely paid for (never inferred from reply text), record it so
        # RoomPoller can estimate hint_points for archipelago.gg-polled rooms.
        if self.hint_usage is not None and sess.hint_points < hint_points_before:
            slot_info = self.multidata.slot_by_name(sess.slot) if self.multidata else None
            if slot_info is not None:
                self.hint_usage.record_used(slot_info.slot)
        if not replies:
            return {"ok": True, "queued": True}
        return {"ok": True, "reply": replies[-1], "all": replies}

    async def _pump(self, sess: Session) -> None:
        try:
            async for raw in sess.ws:
                for packet in json.loads(raw):
                    cmd = packet.get("cmd")
                    if cmd == "RoomUpdate":
                        if "hint_points" in packet:
                            hp = packet["hint_points"]
                            if isinstance(hp, dict):
                                for v in hp.values():
                                    sess.hint_points = int(v)
                                    break
                            else:
                                try:
                                    sess.hint_points = int(hp)
                                except Exception:
                                    pass
                        if self.world is not None and sess.slot_num is not None:
                            cl = packet.get("checked_locations")
                            if isinstance(cl, list):
                                self.world.apply_slot_checks(sess.slot_num, [int(x) for x in cl], replace=False)
                    elif cmd == "ReceivedItems" and self.world is not None:
                        # `player` is the finder's slot, not us; marking their
                        # check feeds our received-items log for free.
                        for item in packet.get("items") or []:
                            try:
                                sender_slot = int(item["player"])
                                location_id = int(item["location"])
                            except (KeyError, TypeError, ValueError):
                                continue
                            self.world.apply_slot_checks(sender_slot, [location_id], replace=False)
                    elif cmd == "PrintJSON":
                        text = _render_print_json(packet.get("data") or [], self.multidata)
                        sess.last_text = text
                        log.info("session %s PrintJSON type=%s text=%r", sess.sid[:8], packet.get("type"), text)
                        try:
                            sess.inbox.put_nowait(text)
                        except asyncio.QueueFull:
                            pass
                        # Goal is room-wide; Hint only reaches us if our slot
                        # is the finder or receiver. Both reuse WorldState's
                        # existing PrintJSON handler.
                        if self.world is not None and packet.get("type") in ("Hint", "Goal"):
                            self.world.apply_print_json(packet)
                        # ItemSend is room-wide too: any check on the team
                        # reaches us, not just our own slot's.
                        if self.world is not None and packet.get("type") == "ItemSend":
                            item = packet.get("item") or {}
                            try:
                                finder_slot = int(item["player"])
                                location_id = int(item["location"])
                            except (KeyError, TypeError, ValueError):
                                pass
                            else:
                                self.world.apply_slot_checks(finder_slot, [location_id], replace=False)
                    else:
                        log.debug("session %s packet cmd=%s", sess.sid[:8], cmd)
        except Exception as e:
            log.info("session %s closed: %s", sess.sid[:8], e)
        finally:
            self._sessions.pop(sess.sid, None)
