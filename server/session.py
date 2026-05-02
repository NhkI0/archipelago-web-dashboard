"""
Per-browser AP WebSocket sessions.

When a player logs in via /api/login the backend opens a dedicated AP WS as
that slot, keeps it open, and returns a session id. /api/hint uses the open
socket to issue `!hint <item>` / `!hint_location <location>` chat commands —
the AP server charges them to the slot's hint points and broadcasts the
result, which the persistent Tracker connection picks up.
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

log = logging.getLogger("ap.session")


@dataclass
class Session:
    sid: str
    slot: str
    ws: "websockets.WebSocketClientProtocol"
    inbox: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=64))
    hint_points: int = 0
    last_text: str = ""

    async def close(self) -> None:
        try:
            await self.ws.close()
        except Exception:
            pass


class SessionManager:
    def __init__(self, host: str = "localhost", port: int = 38281) -> None:
        self.uri = f"ws://{host}:{port}"
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    def get(self, sid: str) -> Session | None:
        return self._sessions.get(sid)

    async def login(self, slot: str, password: str = "", game: str = "") -> Session:
        ws = await websockets.connect(self.uri, max_size=2**24)
        await ws.recv()  # RoomInfo

        await ws.send(json.dumps([{
            "cmd": "Connect",
            "password": password,
            "game": game or "Archipelago",
            "name": slot,
            "uuid": str(uuid.uuid4()),
            "tags": ["TextOnly"],
            "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
            "items_handling": 0,
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
                hp = 0
                slot_info = packet.get("slot_info") or {}
                # hint_points sometimes ships on Connected; otherwise it lands
                # on the next RoomUpdate.
                hp = int(packet.get("hint_points", 0) or 0)
                sess = Session(sid=sid, slot=slot, ws=ws, hint_points=hp)
                self._sessions[sid] = sess
                asyncio.create_task(self._pump(sess), name=f"sess-{sid[:8]}")
                _ = slot_info  # currently unused
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

        await sess.ws.send(json.dumps([{"cmd": "Say", "text": cmd}]))
        # Wait briefly for a PrintJSON reply addressed to us.
        try:
            reply = await asyncio.wait_for(sess.inbox.get(), timeout=4)
        except asyncio.TimeoutError:
            return {"ok": True, "queued": True}
        return {"ok": True, "reply": reply}

    async def _pump(self, sess: Session) -> None:
        try:
            async for raw in sess.ws:
                for packet in json.loads(raw):
                    cmd = packet.get("cmd")
                    if cmd == "RoomUpdate" and "hint_points" in packet:
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
                    elif cmd == "PrintJSON":
                        text = "".join(
                            (p.get("text") or "")
                            for p in (packet.get("data") or [])
                        )
                        sess.last_text = text
                        try:
                            sess.inbox.put_nowait(text)
                        except asyncio.QueueFull:
                            pass
        except Exception as e:
            log.info("session %s closed: %s", sess.sid[:8], e)
        finally:
            self._sessions.pop(sess.sid, None)
