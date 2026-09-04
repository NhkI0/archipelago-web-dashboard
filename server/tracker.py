"""
AP WebSocket tracker: one persistent "observer" connection for the whole room.

`ItemSend`/`Goal` PrintJSON broadcast to every client on the team, and hint/status
DataStorage keys aren't restricted to the reading connection's own slot. So one
connection sees the whole room's checks, hints, and goals live.

Gap: `hint_points` only arrives via a slot's own `RoomUpdate`. `_baseline_sweep`
(brief one-shot connects, once at startup) seeds it and `checked_locations` for
every slot; after that, a slot's hint_points only updates again if it logs in.
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


def _connect_packet(password: str, game: str, name: str, tags: list[str]) -> str:
    return json.dumps([{
        "cmd": "Connect",
        "password": password,
        "game": game,
        "name": name,
        "uuid": str(uuid.uuid4()),
        "tags": tags,
        "version": {"major": 0, "minor": 6, "build": 7, "class": "Version"},
        "items_handling": 0,
    }])


async def _fetch_slot_baseline(
    state: WorldState, uri: str, slot_num: int, slot_name: str, game: str, password: str,
) -> None:
    """One-shot connect-read-close to seed a slot's checked_locations/hint_points."""
    try:
        async with websockets.connect(uri, max_size=2**24, open_timeout=10) as ws:
            await ws.recv()  # RoomInfo
            await ws.send(_connect_packet(password, game, slot_name, ["Tracker"]))
            raw = await asyncio.wait_for(ws.recv(), timeout=8)
            for packet in json.loads(raw):
                if packet.get("cmd") == "Connected":
                    cl = packet.get("checked_locations") or []
                    if isinstance(cl, list):
                        state.apply_slot_checks(slot_num, [int(x) for x in cl], replace=True)
                    state.apply_room_update_meta(packet, owner_slot=slot_num)
                elif packet.get("cmd") == "ConnectionRefused":
                    log.warning("[%s] baseline refused: %s", slot_name, packet.get("errors"))
    except Exception as e:
        log.warning("[%s] baseline fetch failed: %s", slot_name, e)


async def _baseline_sweep(state: WorldState, uri: str, password: str) -> None:
    for slot in list(state.slots.values()):
        await _fetch_slot_baseline(state, uri, slot.slot, slot.name, slot.game, password)


class _ObserverClient:
    """The single persistent WS connection that tracks the whole room."""

    def __init__(
        self,
        state: WorldState,
        uri: str,
        slot_num: int,
        slot_name: str,
        game: str,
        password: str,
        on_status_change: Callable[[], None] | None = None,
        deaths_file: pathlib.Path | None = None,
    ) -> None:
        self.state = state
        self.uri = uri
        self.slot_num = slot_num
        self.slot_name = slot_name
        self.game = game
        self.password = password
        self.on_status_change = on_status_change
        self.connected = False
        # Set only when this slot is also the DeathLink host (merges DeathLink
        # duty onto this connection instead of a separate DeathLinkClient).
        self.death_counter = _DeathLinkCounter(deaths_file) if deaths_file is not None else None
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
            self._task = asyncio.create_task(self._run(), name="ap-tracker-observer")

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
                    self._set_connected(True)
                    await self._connect(ws)
                    delay = 5
                    async for raw in ws:
                        for packet in json.loads(raw):
                            await self._dispatch(packet)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("observer disconnected (%s); retrying in %ds", e, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            finally:
                self._set_connected(False)

    async def _connect(self, ws: "websockets.WebSocketClientProtocol") -> None:
        await ws.recv()  # RoomInfo
        log.info("observer connecting as %r (slot=%d)", self.slot_name, self.slot_num)
        tags = ["Tracker", "DeathLink"] if self.death_counter is not None else ["Tracker"]
        await ws.send(_connect_packet(self.password, self.game, self.slot_name, tags))

    async def _subscribe_all_hints(self, ws: "websockets.WebSocketClientProtocol") -> None:
        # Not restricted to our own slot: any connection can Get/SetNotify any
        # slot's hint/status keys, so one subscription covers the whole room.
        keys = []
        for slot in self.state.slots.values():
            keys.append(f"_read_hints_0_{slot.slot}")
            keys.append(f"_read_client_status_0_{slot.slot}")
        await ws.send(json.dumps([{"cmd": "Get", "keys": keys}]))
        await ws.send(json.dumps([{"cmd": "SetNotify", "keys": keys}]))

    async def _dispatch(self, packet: dict) -> None:
        cmd = packet.get("cmd")
        if cmd == "Connected":
            cl = packet.get("checked_locations") or []
            log.info("observer Connected, initial checks=%d", len(cl) if isinstance(cl, list) else 0)
            if isinstance(cl, list):
                self.state.apply_slot_checks(self.slot_num, [int(x) for x in cl], replace=True)
            self.state.apply_room_update_meta(packet, owner_slot=self.slot_num)
            if self._ws is not None:
                await self._subscribe_all_hints(self._ws)
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
            if packet.get("type") == "ItemSend":
                item = packet.get("item") or {}
                try:
                    finder_slot = int(item["player"])
                    location_id = int(item["location"])
                except (KeyError, TypeError, ValueError):
                    pass
                else:
                    self.state.apply_slot_checks(finder_slot, [location_id], replace=False)
            self.state.apply_print_json(packet)
        elif cmd == "ConnectionRefused":
            log.error("observer refused: %s", packet.get("errors"))
        elif cmd == "Bounced" and self.death_counter is not None:
            self.death_counter.record_bounce(packet)


class _DeathLinkCounter:
    """`{player_name: death_count}` bookkeeping, persisted to `deaths_file`.
    Shared by `DeathLinkClient` and a merged `_ObserverClient`."""

    def __init__(self, deaths_file: pathlib.Path) -> None:
        self.deaths_file = deaths_file
        self.counts: dict[str, int] = {}
        self._rehydrate()

    def _rehydrate(self) -> None:
        if not self.deaths_file.exists():
            return
        try:
            raw = json.loads(self.deaths_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("could not load %s: %s", self.deaths_file, e)
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
            log.warning("could not persist %s: %s", self.deaths_file, e)

    def record_bounce(self, packet: dict) -> None:
        if "DeathLink" not in (packet.get("tags") or []):
            return
        data = packet.get("data") or {}
        who = str(data.get("source") or "unknown")
        self.counts[who] = self.counts.get(who, 0) + 1
        self._persist()


class DeathLinkClient:
    """Persistent passive WS that piggybacks on an existing player slot.

    Connects as a second client on a slot that already has DeathLink enabled
    (chosen by `pick_deathlink_host`), listens for AP `Bounced`
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
        self.counter = _DeathLinkCounter(deaths_file)
        self.counts = self.counter.counts  # same dict object, kept for existing readers
        self._task: asyncio.Task | None = None
        self._stopped_permanently = False

    @property
    def active(self) -> bool:
        return not self._stopped_permanently

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
        await ws.send(_connect_packet(self.password, self.game, self.slot_name, ["Tracker", "DeathLink"]))

    async def _dispatch(self, packet: dict) -> None:
        cmd = packet.get("cmd")
        if cmd == "Connected":
            log.info("[%s] Connected", self.slot_name)
        elif cmd == "ConnectionRefused":
            log.error("[%s] refused: %s, DeathLink tracking disabled", self.slot_name, packet.get("errors"))
            self._stopped_permanently = True
        elif cmd == "Bounced":
            self.counter.record_bounce(packet)


def pick_deathlink_host(state: WorldState):
    """First slot (in `state.slots` order) with DeathLink enabled, or None.
    Shared by both `Tracker` and `RoomPoller`."""
    md = state.multidata
    return next((s for s in state.slots.values() if md.deathlink_enabled(s.slot)), None)


class Tracker:
    """One observer connection for the whole room, plus a DeathLink client.

    The observer is a placeholder for when nobody's watching: a real login
    (see `SessionManager.try_claim_observer` in session.py) takes over instead.
    """

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
        default_slot: str = "",
    ) -> None:
        self.state = state
        self.uri = f"{'wss' if secure else 'ws'}://{host}:{port}"
        self.password = password
        self.deaths_file = deaths_file
        self._on_connection_change = on_connection_change
        self.default_slot = default_slot
        self._observer: _ObserverClient | None = None
        self._observer_claimed = False
        self._death_client: DeathLinkClient | None = None
        self._baseline_task: asyncio.Task | None = None

    def _notify_connection_change(self) -> None:
        if self._on_connection_change is not None:
            self._on_connection_change(self.connected)

    @property
    def connected(self) -> bool:
        """True once the observer (or a session standing in for it) is live."""
        if self._observer_claimed:
            return True
        return self._observer.connected if self._observer is not None else False

    def _pick_default_slot(self):
        """Order: goaled+DeathLink slot, configured name, DeathLink slot, first slot."""
        slots = list(self.state.slots.values())
        md = self.state.multidata
        goaled_deathlink = next((s for s in slots if s.goal_completed and md.deathlink_enabled(s.slot)), None)
        if goaled_deathlink is not None:
            return goaled_deathlink
        if self.default_slot:
            match = next((s for s in slots if s.name == self.default_slot), None)
            if match is not None:
                return match
        deathlink = pick_deathlink_host(self.state)
        if deathlink is not None:
            return deathlink
        return next(iter(slots), None)

    def _start_observer_connection(self) -> None:
        if self._observer is not None or self._observer_claimed:
            return
        slot = self._pick_default_slot()
        if slot is None:
            log.warning("no player slots found; tracker not starting")
            return
        # Merge DeathLink duty onto this connection if this slot is the host.
        deathlink_host = pick_deathlink_host(self.state) if self.deaths_file is not None else None
        merged_deaths_file = self.deaths_file if deathlink_host is not None and deathlink_host.slot == slot.slot else None
        self._observer = _ObserverClient(
            state=self.state,
            uri=self.uri,
            slot_num=slot.slot,
            slot_name=slot.name,
            game=slot.game,
            password=self.password,
            on_status_change=self._notify_connection_change,
            deaths_file=merged_deaths_file,
        )
        self._observer.start()

    def _configured_slot_lacks_deathlink(self) -> bool:
        """True if the host explicitly named a default_slot and it has no
        DeathLink - respected as an opt-out, no standalone connection started."""
        if not self.default_slot:
            return False
        slot = next((s for s in self.state.slots.values() if s.name == self.default_slot), None)
        return slot is not None and not self.state.multidata.deathlink_enabled(slot.slot)

    def _start_deathlink_if_needed(self) -> None:
        """Start a standalone DeathLink connection, unless the anchor merged it."""
        if self.deaths_file is None or self._death_client is not None:
            return
        if self._configured_slot_lacks_deathlink():
            return
        host = pick_deathlink_host(self.state)
        if host is None:
            log.warning("no DeathLink-enabled slot found; death leaderboard disabled")
            return
        if self._observer is not None and self._observer.slot_num == host.slot:
            return  # merged onto the observer connection instead
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

    def start(self) -> None:
        if self._baseline_task is not None:
            return
        self._start_observer_connection()
        # One-shot, not repeated: hint_points for a slot that never logs in
        # just stays whatever it was seeded as here.
        self._baseline_task = asyncio.create_task(
            _baseline_sweep(self.state, self.uri, self.password), name="ap-baseline-sweep",
        )
        self._start_deathlink_if_needed()

    async def try_claim_observer(self) -> bool:
        """A logged-in session wants to take over observer duty. Returns False
        if someone already holds it."""
        if self._observer_claimed:
            return False
        self._observer_claimed = True
        if self._observer is not None:
            await self._observer.stop()
            self._observer = None
        # Sessions never do DeathLink themselves; a standalone must take over.
        self._start_deathlink_if_needed()
        self._notify_connection_change()
        return True

    async def release_observer(self) -> None:
        """Nobody's left to hold observer duty; bring the anchor back."""
        self._observer_claimed = False
        self._start_observer_connection()
        # Redundant now if the anchor re-merged onto the standalone's slot.
        if (self._observer is not None and self._death_client is not None
                and self._observer.slot_num == self._death_client.slot_num):
            await self._death_client.stop()
            self._death_client = None
        self._notify_connection_change()

    async def stop(self) -> None:
        if self._baseline_task is not None:
            self._baseline_task.cancel()
            try:
                await self._baseline_task
            except (asyncio.CancelledError, Exception):
                pass
            self._baseline_task = None
        stops = []
        if self._observer is not None:
            stops.append(self._observer.stop())
        if self._death_client is not None:
            stops.append(self._death_client.stop())
        await asyncio.gather(*stops, return_exceptions=True)
        self._observer = None
        self._observer_claimed = False
        self._death_client = None

    def _death_counts(self) -> dict[str, int]:
        if self._death_client is not None:
            return self._death_client.counts
        if self._observer is not None and self._observer.death_counter is not None:
            return self._observer.death_counter.counts
        return {}

    def death_rows(self) -> list[dict]:
        rows = [{"name": n, "deaths": c} for n, c in self._death_counts().items()]
        rows.sort(key=lambda r: -r["deaths"])
        return rows

    def death_client_connected(self) -> bool:
        if self._death_client is not None:
            return self._death_client.active
        if self._observer is not None and self._observer.death_counter is not None:
            return self._observer.connected
        return False
