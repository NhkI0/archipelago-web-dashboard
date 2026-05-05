"""
Long-lived AP WebSocket client connected as a passive Tracker.

We use the `Tracker` tag (and `items_handling = 0`) so the AP server doesn't
expect the slot to actually receive items. The dedicated `DeathTracker` slot
already created for `archipelago_ui.py` is reused — the server allows multiple
clients on the same slot.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import websockets

from .state import WorldState

log = logging.getLogger("ap.tracker")


class Tracker:
    def __init__(
        self,
        state: WorldState,
        *,
        host: str = "localhost",
        port: int = 38281,
        slot_name: str = "DeathTracker",
        game: str = "Archipelago",
        password: str = "",
    ) -> None:
        self.state = state
        self.uri = f"ws://{host}:{port}"
        self.slot_name = slot_name
        self.game = game
        self.password = password
        self._task: asyncio.Task | None = None
        self._ws: "websockets.WebSocketClientProtocol | None" = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="ap-tracker")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def _run(self) -> None:
        delay = 5
        while True:
            try:
                async with websockets.connect(self.uri, max_size=2**24) as ws:
                    await self._connect(ws)
                    delay = 5
                    async for raw in ws:
                        for packet in json.loads(raw):
                            await self._dispatch(packet)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("tracker disconnected (%s); retrying in %ds", e, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _connect(self, ws: "websockets.WebSocketClientProtocol") -> None:
        await ws.recv()  # RoomInfo
        await ws.send(json.dumps([{
            "cmd": "Connect",
            "password": self.password,
            "game": self.game,
            "name": self.slot_name,
            "uuid": str(uuid.uuid4()),
            "tags": ["Tracker"],
            "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
            "items_handling": 0,
        }]))
        self._ws = ws

    async def _subscribe_to_hints(self, ws: "websockets.WebSocketClientProtocol") -> None:
        """Pull initial hints + subscribe for updates via the AP data store."""
        keys = [f"_read_hints_0_{slot}" for slot in self.state.slots]
        if not keys:
            return
        await ws.send(json.dumps([{"cmd": "Get", "keys": keys}]))
        await ws.send(json.dumps([{"cmd": "SetNotify", "keys": keys}]))

    async def _dispatch(self, packet: dict) -> None:
        cmd = packet.get("cmd")
        if cmd == "Connected":
            self.state.apply_room_update(packet)
            if self._ws is not None:
                await self._subscribe_to_hints(self._ws)
        elif cmd == "RoomUpdate":
            self.state.apply_room_update(packet)
        elif cmd == "Retrieved":
            for key, value in (packet.get("keys") or {}).items():
                self.state.apply_hint_store(key, value)
        elif cmd == "SetReply":
            key = packet.get("key")
            if key and key.startswith("_read_hints_"):
                self.state.apply_hint_store(key, packet.get("value"))
        elif cmd == "PrintJSON":
            log.info("PrintJSON type=%s keys=%s", packet.get("type"), list(packet.keys()))
            self.state.apply_print_json(packet)
        elif cmd == "ConnectionRefused":
            log.error("tracker refused: %s", packet.get("errors"))
        else:
            log.debug("packet cmd=%s", cmd)
