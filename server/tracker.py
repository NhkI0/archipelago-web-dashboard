"""
AP WebSocket trackers — one connection per real player slot.

AP's `RoomUpdate.checked_locations` is scoped to the slot the client connected
as, so to mirror the entire team's progress on the dashboard we open a separate
WS per slot (AP allows multiple clients to share a slot). The `Tracker` tag +
`items_handling=0` keeps each connection passive.

The first connection that comes up also subscribes to the team's hint data
store keys, since hints are team-wide.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import websockets

from .state import WorldState

log = logging.getLogger("ap.tracker")


class _SlotClient:
    """One persistent WS connection scoped to a single slot."""

    def __init__(
        self,
        state: WorldState,
        uri: str,
        slot_num: int,
        slot_name: str,
        game: str,
        password: str,
        subscribe_hints: bool,
    ) -> None:
        self.state = state
        self.uri = uri
        self.slot_num = slot_num
        self.slot_name = slot_name
        self.game = game
        self.password = password
        self.subscribe_hints = subscribe_hints
        self._task: asyncio.Task | None = None
        self._ws: "websockets.WebSocketClientProtocol | None" = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name=f"ap-tracker-{self.slot_name}")

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
                    self._ws = ws
                    await self._connect(ws)
                    delay = 5
                    async for raw in ws:
                        for packet in json.loads(raw):
                            await self._dispatch(packet)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("[%s] disconnected (%s); retrying in %ds", self.slot_name, e, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _connect(self, ws: "websockets.WebSocketClientProtocol") -> None:
        await ws.recv()  # RoomInfo
        log.info("[%s] connecting (slot=%d game=%r)", self.slot_name, self.slot_num, self.game)
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

    async def _subscribe_to_hints(self, ws: "websockets.WebSocketClientProtocol") -> None:
        keys = [f"_read_hints_0_{slot}" for slot in self.state.slots]
        if not keys:
            return
        await ws.send(json.dumps([{"cmd": "Get", "keys": keys}]))
        await ws.send(json.dumps([{"cmd": "SetNotify", "keys": keys}]))

    async def _dispatch(self, packet: dict) -> None:
        cmd = packet.get("cmd")
        if cmd == "Connected":
            cl = packet.get("checked_locations") or []
            log.info("[%s] Connected, initial checks=%d", self.slot_name, len(cl) if isinstance(cl, list) else 0)
            if isinstance(cl, list):
                self.state.apply_slot_checks(self.slot_num, [int(x) for x in cl])
            if self.subscribe_hints and self._ws is not None:
                await self._subscribe_to_hints(self._ws)
        elif cmd == "RoomUpdate":
            cl = packet.get("checked_locations")
            if isinstance(cl, list):
                log.info("[%s] RoomUpdate checked=%d", self.slot_name, len(cl))
                self.state.apply_slot_checks(self.slot_num, [int(x) for x in cl])
            # Forward goal/online flips & hint_points (these are global).
            self.state.apply_room_update_meta(packet)
        elif cmd == "Retrieved":
            for key, value in (packet.get("keys") or {}).items():
                self.state.apply_hint_store(key, value)
        elif cmd == "SetReply":
            key = packet.get("key")
            if key and key.startswith("_read_hints_"):
                self.state.apply_hint_store(key, packet.get("value"))
        elif cmd == "PrintJSON":
            self.state.apply_print_json(packet)
        elif cmd == "ConnectionRefused":
            log.error("[%s] refused: %s", self.slot_name, packet.get("errors"))


class Tracker:
    """Aggregates one `_SlotClient` per real player slot in the multidata."""

    def __init__(
        self,
        state: WorldState,
        *,
        host: str = "localhost",
        port: int = 38281,
        slot_name: str = "",   # ignored — kept for API compat
        game: str = "",        # ignored — kept for API compat
        password: str = "",
    ) -> None:
        self.state = state
        self.uri = f"ws://{host}:{port}"
        self.password = password
        self._clients: list[_SlotClient] = []

    def start(self) -> None:
        if self._clients:
            return
        first = True
        for slot in self.state.slots.values():
            client = _SlotClient(
                state=self.state,
                uri=self.uri,
                slot_num=slot.slot,
                slot_name=slot.name,
                game=slot.game,
                password=self.password,
                subscribe_hints=first,
            )
            client.start()
            self._clients.append(client)
            first = False
        log.info("started %d slot trackers", len(self._clients))

    async def stop(self) -> None:
        await asyncio.gather(*(c.stop() for c in self._clients), return_exceptions=True)
        self._clients.clear()
