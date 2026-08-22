"""
AP WebSocket trackers — one connection per real player slot.

AP's `RoomUpdate.checked_locations` is scoped to the slot the client connected
as, so to mirror the entire team's progress on the dashboard we open a separate
WS per slot (AP allows multiple clients to share a slot). The `Tracker` tag +
`items_handling=0` keeps each connection passive.

Each connection also subscribes to its own slot's hint + client-status data
store keys. AP replicates every hint into both the finder's and receiver's
store, so the union across all slot connections covers the whole team's hints
without depending on any single connection staying up.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import uuid
from typing import Callable

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
        on_status_change: Callable[[], None] | None = None,
    ) -> None:
        self.state = state
        self.uri = uri
        self.slot_num = slot_num
        self.slot_name = slot_name
        self.game = game
        self.password = password
        self.subscribe_hints = subscribe_hints
        self.on_status_change = on_status_change
        self.connected = False
        self._task: asyncio.Task | None = None
        self._ws: "websockets.WebSocketClientProtocol | None" = None

    def _set_connected(self, value: bool) -> None:
        if self.connected == value:
            return
        self.connected = value
        if self.on_status_change is not None:
            self.on_status_change()

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
                    # A successful handshake means the multiworld itself is
                    # reachable, regardless of whether login below is accepted.
                    self._set_connected(True)
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
            finally:
                self._set_connected(False)

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
        # Each slot subscribes to its OWN hint/status keys rather than funnelling
        # every slot's data through one connection. AP replicates each hint into
        # both the finder's and the receiver's `_read_hints_0_<slot>` store, so
        # the union across all slot connections (deduped in apply_hint_store)
        # still covers every hint — but now a single offline/refused slot can no
        # longer take down hints for the whole multiworld.
        keys = [
            f"_read_hints_0_{self.slot_num}",
            f"_read_client_status_0_{self.slot_num}",
        ]
        await ws.send(json.dumps([{"cmd": "Get", "keys": keys}]))
        await ws.send(json.dumps([{"cmd": "SetNotify", "keys": keys}]))

    async def _dispatch(self, packet: dict) -> None:
        cmd = packet.get("cmd")
        if cmd == "Connected":
            cl = packet.get("checked_locations") or []
            log.info("[%s] Connected, initial checks=%d", self.slot_name, len(cl) if isinstance(cl, list) else 0)
            if isinstance(cl, list):
                self.state.apply_slot_checks(self.slot_num, [int(x) for x in cl], replace=True)
            self.state.apply_room_update_meta(packet, owner_slot=self.slot_num)
            if self.subscribe_hints and self._ws is not None:
                await self._subscribe_to_hints(self._ws)
        elif cmd == "RoomUpdate":
            cl = packet.get("checked_locations")
            if isinstance(cl, list):
                self.state.apply_slot_checks(self.slot_num, [int(x) for x in cl], replace=False)
            self.state.apply_room_update_meta(packet, owner_slot=self.slot_num)
        elif cmd == "Retrieved":
            for key, value in (packet.get("keys") or {}).items():
                if key.startswith("_read_hints_"):
                    self.state.apply_hint_store(key, value)
                elif key.startswith("_read_client_status_"):
                    self.state.apply_client_status(key, value)
        elif cmd == "SetReply":
            key = packet.get("key")
            if key and key.startswith("_read_hints_"):
                self.state.apply_hint_store(key, packet.get("value"))
            elif key and key.startswith("_read_client_status_"):
                self.state.apply_client_status(key, packet.get("value"))
        elif cmd == "PrintJSON":
            self.state.apply_print_json(packet)
        elif cmd == "ConnectionRefused":
            log.error("[%s] refused: %s", self.slot_name, packet.get("errors"))


class DeathLinkClient:
    """Persistent passive WS that piggybacks on an existing player slot.

    Connects as a second client on a slot that already has DeathLink enabled
    (chosen by `Tracker._pick_deathlink_host`), listens for AP `Bounced`
    packets carrying the `DeathLink` tag, and maintains an in-memory
    `{player_name: death_count}` map persisted to `deaths_file` so counts
    survive restarts. AP routes Bounces per-connection, so this works even
    when the host slot is itself the source of a death.
    """

    def __init__(
        self,
        uri: str,
        slot_num: int,
        slot_name: str,
        game: str,
        password: str,
        deaths_file: pathlib.Path,
    ) -> None:
        self.uri = uri
        self.slot_num = slot_num
        self.slot_name = slot_name
        self.game = game
        self.password = password
        self.deaths_file = deaths_file
        self.counts: dict[str, int] = {}
        self._task: asyncio.Task | None = None
        self._stopped_permanently = False
        self._rehydrate()

    def _rehydrate(self) -> None:
        if not self.deaths_file.exists():
            return
        try:
            raw = json.loads(self.deaths_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("[%s] could not load %s: %s", self.slot_name, self.deaths_file, e)
            return
        if isinstance(raw, dict):
            for name, count in raw.items():
                try:
                    self.counts[str(name)] = int(count)
                except (TypeError, ValueError):
                    continue
        elif isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, dict) and "name" in entry and "deaths" in entry:
                    try:
                        self.counts[str(entry["name"])] = int(entry["deaths"])
                    except (TypeError, ValueError):
                        continue

    def _persist(self) -> None:
        tmp = self.deaths_file.with_suffix(self.deaths_file.suffix + ".tmp")
        try:
            self.deaths_file.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.counts, indent=2), encoding="utf-8")
            os.replace(tmp, self.deaths_file)
        except OSError as e:
            log.warning("[%s] could not persist %s: %s", self.slot_name, self.deaths_file, e)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name=f"ap-deathlink-{self.slot_name}")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def _run(self) -> None:
        delay = 5
        while not self._stopped_permanently:
            try:
                async with websockets.connect(self.uri, max_size=2**24) as ws:
                    await self._connect(ws)
                    delay = 5
                    async for raw in ws:
                        for packet in json.loads(raw):
                            await self._dispatch(packet)
                        if self._stopped_permanently:
                            return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if self._stopped_permanently:
                    return
                log.warning("[%s] disconnected (%s); retrying in %ds", self.slot_name, e, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _connect(self, ws: "websockets.WebSocketClientProtocol") -> None:
        await ws.recv()  # RoomInfo
        log.info("[%s] connecting (DeathLink subscriber, slot=%d game=%r)",
                 self.slot_name, self.slot_num, self.game)
        await ws.send(json.dumps([{
            "cmd": "Connect",
            "password": self.password,
            "game": self.game,
            "name": self.slot_name,
            "uuid": str(uuid.uuid4()),
            "tags": ["Tracker", "DeathLink"],
            "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
            "items_handling": 0,
        }]))

    async def _dispatch(self, packet: dict) -> None:
        cmd = packet.get("cmd")
        if cmd == "Connected":
            log.info("[%s] Connected", self.slot_name)
        elif cmd == "ConnectionRefused":
            log.error("[%s] refused: %s, DeathLink tracking disabled", self.slot_name, packet.get("errors"))
            self._stopped_permanently = True
        elif cmd == "Bounced" and "DeathLink" in (packet.get("tags") or []):
            data = packet.get("data") or {}
            who = str(data.get("source") or "unknown")
            self.counts[who] = self.counts.get(who, 0) + 1
            self._persist()


class Tracker:
    """Aggregates one `_SlotClient` per real player slot, plus a DeathLink client."""

    PREFERRED_DEATHLINK_HOST = "dopamine"

    def __init__(
        self,
        state: WorldState,
        *,
        host: str = "localhost",
        port: int = 38281,
        password: str = "",
        secure: bool = False,
        deaths_file: pathlib.Path | None = None,
        on_connection_change: Callable[[bool], None] | None = None,
    ) -> None:
        self.state = state
        self.uri = f"{'wss' if secure else 'ws'}://{host}:{port}"
        self.password = password
        self.deaths_file = deaths_file
        self._on_connection_change = on_connection_change
        self._connected = False
        self._clients: list[_SlotClient] = []
        self._death_client: DeathLinkClient | None = None

    def _notify_connection_change(self) -> None:
        now = any(c.connected for c in self._clients)
        if now == self._connected:
            return
        self._connected = now
        if self._on_connection_change is not None:
            self._on_connection_change(now)

    @property
    def connected(self) -> bool:
        """True once at least one slot connection has reached the multiworld."""
        return self._connected

    def _pick_deathlink_host(self):
        md = self.state.multidata
        slots = list(self.state.slots.values())
        preferred = next((s for s in slots if s.name == self.PREFERRED_DEATHLINK_HOST), None)
        if preferred and md.deathlink_enabled(preferred.slot):
            return preferred
        return next((s for s in slots if md.deathlink_enabled(s.slot)), None)

    def start(self) -> None:
        if self._clients:
            return
        for slot in self.state.slots.values():
            client = _SlotClient(
                state=self.state,
                uri=self.uri,
                slot_num=slot.slot,
                slot_name=slot.name,
                game=slot.game,
                password=self.password,
                # Every slot subscribes to its own hint/status keys; hints no
                # longer depend on one designated connection staying healthy.
                subscribe_hints=True,
                on_status_change=self._notify_connection_change,
            )
            client.start()
            self._clients.append(client)
        log.info("started %d slot trackers", len(self._clients))

        if self.deaths_file is not None:
            host = self._pick_deathlink_host()
            if host is None:
                log.warning("no DeathLink-enabled slot found; death leaderboard disabled")
            else:
                log.info("hosting DeathLink listener on slot %r (slot=%d)", host.name, host.slot)
                self._death_client = DeathLinkClient(
                    uri=self.uri,
                    slot_num=host.slot,
                    slot_name=host.name,
                    game=host.game,
                    password=self.password,
                    deaths_file=self.deaths_file,
                )
                self._death_client.start()

    async def stop(self) -> None:
        stops = [c.stop() for c in self._clients]
        if self._death_client is not None:
            stops.append(self._death_client.stop())
        await asyncio.gather(*stops, return_exceptions=True)
        self._clients.clear()
        self._death_client = None

    def death_rows(self) -> list[dict]:
        if self._death_client is None:
            return []
        rows = [{"name": n, "deaths": c} for n, c in self._death_client.counts.items()]
        rows.sort(key=lambda r: -r["deaths"])
        return rows

    def death_client_connected(self) -> bool:
        return self._death_client is not None and not self._death_client._stopped_permanently
