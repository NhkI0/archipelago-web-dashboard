"""Shared DeathLink death counter for archipelago.gg-polled rooms.

RoomPoller has no persistent websocket (see its module docstring), so unlike
self-hosted's always-on DeathLinkClient, deaths are only caught while a
dashboard user is logged in as a DeathLink-enabled slot: SessionManager tags
that login's Connect with "DeathLink" and feeds Bounces into this counter
(session.py). RoomPoller only reads from it (death_rows/death_client_connected).

Multiple logged-in DeathLink sessions all get the same Bounce broadcast, so
`record()` dedupes by (source, time) within a short window.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from typing import Any

log = logging.getLogger("ap.deathlink")

_DEDUP_WINDOW_SEC = 10.0


class DeathLinkCounter:
    """In-memory `{player_name: death_count}` map persisted to `deaths_file`,
    plus a live count of currently logged-in DeathLink-tagged sessions."""

    def __init__(self, deaths_file: pathlib.Path) -> None:
        self.deaths_file = deaths_file
        self.counts: dict[str, int] = {}
        self.active_sessions = 0
        self._recent: dict[tuple[str, Any], float] = {}
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

    def record(self, source: str, event_time: Any = None) -> bool:
        """Record one death. Returns False if (source, event_time) was already
        seen within the dedup window (a duplicate delivery), else True."""
        now = time.monotonic()
        self._recent = {k: v for k, v in self._recent.items() if now - v < _DEDUP_WINDOW_SEC}
        key = (source, event_time)
        if key in self._recent:
            return False
        self._recent[key] = now
        self.counts[source] = self.counts.get(source, 0) + 1
        self._persist()
        return True

    def note_session_open(self) -> None:
        self.active_sessions += 1

    def note_session_close(self) -> None:
        self.active_sessions = max(0, self.active_sessions - 1)

    @property
    def is_active(self) -> bool:
        """True while at least one DeathLink-enabled slot is logged in."""
        return self.active_sessions > 0

    def rows(self) -> list[dict]:
        rows = [{"name": n, "deaths": c} for n, c in self.counts.items()]
        rows.sort(key=lambda r: -r["deaths"])
        return rows
