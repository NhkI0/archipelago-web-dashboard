"""
Tracks an archipelago.gg-hosted multiworld by polling its public JSON tracker
API instead of opening one websocket per player slot (see server/tracker.py
for the self-hosted equivalent).

archipelago.gg exposes two unauthenticated, server-cached endpoints:
  - GET /api/room_status/<room_id>  - cheap gatekeeper: tracker id, last_port,
    last_activity. Polled often; hits the DB directly so isn't itself cached.
  - GET /api/tracker/<tracker_id>   - the real payload (server-memoized 60s):
    player_checks_done, player_status, hints, connection_timers for every
    slot at once.

DeathLink still needs a real websocket (no live Bounce events in the API), but
only starts once its host slot has connected at least once (see
`_maybe_start_deathlink`).

Only fetched when `last_activity` has actually advanced, mirroring the pattern
an existing open-source poller (wrjones104/ap-tracker) already runs in
production against this same API.

`RoomPoller` mirrors just enough of `Tracker`'s public surface (start/stop/
connected/death_rows/death_client_connected) that main.py only needs one
if/else at construction time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
from typing import Any, Awaitable, Callable

import aiohttp
import websockets

from .hint_usage import HintUsageStore
from .state import WorldState
from .tracker import DeathLinkClient, pick_deathlink_host

log = logging.getLogger("ap.room_poller")

HttpGet = Callable[[str], Awaitable[dict[str, Any]]]


class RoomPoller:
    def __init__(
        self,
        state: WorldState,
        *,
        hostname: str,
        room_id: str,
        password: str = "",
        secure: bool = True,
        deaths_file: pathlib.Path | None = None,
        hint_usage: HintUsageStore | None = None,
        on_connection_change: Callable[[bool], None] | None = None,
        poll_interval: float = 15.0,
        http_get: HttpGet | None = None,
    ) -> None:
        self.state = state
        self.hostname = hostname
        self.room_id = room_id
        self.password = password
        self.secure = secure
        self.deaths_file = deaths_file
        self.hint_usage = hint_usage
        self._on_connection_change = on_connection_change
        self.poll_interval = poll_interval
        # Injectable for tests; defaults to a real aiohttp GET in production so
        # tests never need to mock aiohttp itself.
        self._http_get = http_get or self._aiohttp_get
        self._session: "aiohttp.ClientSession | None" = None
        self._task: asyncio.Task | None = None
        self._connected = False
        self._death_client: DeathLinkClient | None = None
        # See _maybe_start_deathlink: gates the first connection on host-slot presence.
        self._deathlink_ever_started = False
        self._connected_slots: set[int] = set()
        self._last_port: int | None = None
        self._last_activity: str | None = None
        self._location_check_points = 1
        self.hint_cost_pct: int | None = None
        # archipelago.gg's tracker API can't tell a paid hint from a free one,
        # so hint_points here are a local estimate (see hint_usage.py).
        state.hint_points_estimated = True

    # ── public surface (mirrors Tracker) ────────────────────────────────────

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="ap-room-poller")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._death_client is not None:
            await self._death_client.stop()
            self._death_client = None
        if self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def connected(self) -> bool:
        """True once the last poll to archipelago.gg's status API succeeded."""
        return self._connected

    def death_rows(self) -> list[dict]:
        if self._death_client is None:
            return []
        rows = [{"name": n, "deaths": c} for n, c in self._death_client.counts.items()]
        rows.sort(key=lambda r: -r["deaths"])
        return rows

    def death_client_connected(self) -> bool:
        return self._death_client is not None and self._death_client.active

    # ── HTTP ─────────────────────────────────────────────────────────────────

    async def _aiohttp_get(self, url: str) -> dict[str, Any]:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    def _base_url(self) -> str:
        return f"https://{self.hostname}"

    def _set_connected(self, value: bool) -> None:
        if self._connected == value:
            return
        self._connected = value
        if self._on_connection_change is not None:
            self._on_connection_change(value)

    # ── poll loop ────────────────────────────────────────────────────────────

    async def _run(self) -> None:
        delay = self.poll_interval
        while True:
            try:
                await self._poll_once()
                self._set_connected(True)
                delay = self.poll_interval
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._set_connected(False)
                log.warning("room_status poll failed (%s); retrying in %ds", e, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def _poll_once(self) -> None:
        """One gatekeeper check, fetching the full tracker payload only when
        `last_activity` actually advanced. Split out from `_run` so tests can
        drive individual ticks without waiting on `poll_interval` sleeps."""
        status = await self._http_get(f"{self._base_url()}/api/room_status/{self.room_id}")

        last_port = status.get("last_port")
        if last_port is not None and last_port != self._last_port:
            self._last_port = int(last_port)
            await self._on_port_change(self._last_port)

        last_activity = status.get("last_activity")
        if last_activity != self._last_activity:
            self._last_activity = last_activity
            tracker_id = status.get("tracker") or self.room_id
            payload = await self._http_get(f"{self._base_url()}/api/tracker/{tracker_id}")
            self._apply(payload)
            await self._maybe_start_deathlink()

    async def _on_port_change(self, port: int) -> None:
        await self._peek_room_info(port)
        if self._death_client is not None or self._deathlink_ever_started:
            await self._rebuild_deathlink(port)

    async def _peek_room_info(self, port: int) -> None:
        """One-shot connect-read-close purely to read `hint_cost` and
        `location_check_points` off the very first `RoomInfo` packet - sent
        before `Connect`/auth, so this needs no persistent socket or login."""
        uri = f"{'wss' if self.secure else 'ws'}://{self.hostname}:{port}"
        try:
            async with websockets.connect(uri, max_size=2**24, open_timeout=10) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                for packet in json.loads(raw):
                    if packet.get("cmd") == "RoomInfo":
                        self.hint_cost_pct = int(packet.get("hint_cost") or 0)
                        self._location_check_points = int(packet.get("location_check_points") or 1)
                        self.state.apply_room_update_meta({"hint_cost": self.hint_cost_pct})
        except Exception as e:
            log.warning("could not read RoomInfo from %s: %s", uri, e)

    async def _maybe_start_deathlink(self) -> None:
        """Start DeathLink once its host slot has connected at least once.

        `connection_timers` is a last-connected timestamp, not a live
        "connected now" flag, so this is a one-time gate: once true, DeathLink
        stays running rather than flapping on each disconnect/reconnect.
        """
        if self._death_client is not None or self._deathlink_ever_started:
            return
        if self.deaths_file is None or self._last_port is None:
            return
        host = pick_deathlink_host(self.state)
        if host is None or host.slot not in self._connected_slots:
            return
        await self._rebuild_deathlink(self._last_port)

    async def _rebuild_deathlink(self, port: int) -> None:
        if self._death_client is not None:
            await self._death_client.stop()
            self._death_client = None
        if self.deaths_file is None:
            return
        host = pick_deathlink_host(self.state)
        if host is None:
            return
        uri = f"{'wss' if self.secure else 'ws'}://{self.hostname}:{port}"
        self._death_client = DeathLinkClient(
            uri=uri, slot_num=host.slot, slot_name=host.name, game=host.game,
            password=self.password, deaths_file=self.deaths_file,
        )
        self._death_client.start()
        self._deathlink_ever_started = True

    # ── mapping ──────────────────────────────────────────────────────────────

    def _hint_cost_per_hint(self, slot_num: int) -> int:
        """AP's own get_hint_cost formula, reproduced exactly (MultiServer.py)."""
        if not self.hint_cost_pct:
            return 0
        total = self.state.multidata.total_locations_for(slot_num)
        return max(1, int(self.hint_cost_pct * 0.01 * total))

    def _apply(self, payload: dict[str, Any]) -> None:
        # A non-null `time` here means this slot has connected at least once
        # (ever, not "right now") - see `_maybe_start_deathlink`.
        self._connected_slots = {
            int(e["player"])
            for e in payload.get("connection_timers") or []
            if e.get("team") == 0 and e.get("time")
        }

        checks_done: dict[int, int] = {}

        for entry in payload.get("player_checks_done") or []:
            if entry.get("team") != 0:
                continue
            slot_num = int(entry["player"])
            locations = list(entry.get("locations") or [])
            checks_done[slot_num] = len(locations)
            self.state.apply_slot_checks(slot_num, locations, replace=True)

        for entry in payload.get("player_status") or []:
            if entry.get("team") != 0:
                continue
            key = f"_read_client_status_0_{int(entry['player'])}"
            self.state.apply_client_status(key, entry.get("status"))

        for entry in payload.get("hints") or []:
            if entry.get("team") != 0:
                continue
            key = f"_read_hints_0_{int(entry['player'])}"
            self.state.apply_hint_store(key, entry.get("hints") or [])

        # hint_points estimate - only once we actually know hint_cost (from the
        # RoomInfo peek); until then leave the AP-default display untouched.
        if self.hint_cost_pct is not None:
            hint_points = {
                str(slot_num): (
                    self._location_check_points * done
                    - self._hint_cost_per_hint(slot_num)
                    * (self.hint_usage.used_count(slot_num) if self.hint_usage else 0)
                )
                for slot_num, done in checks_done.items()
            }
            self.state.apply_room_update_meta({"hint_points": hint_points})
