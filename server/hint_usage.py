"""
Local hint-spend counter, used only for archipelago.gg-polled rooms.

archipelago.gg's public tracker API (see room_poller.py) has no way to tell a
paid `!hint` from a free/automatic one, so it can't expose a real hint_points
balance. Instead we track spends locally: SessionManager already opens a real,
authenticated-as-that-slot WebSocket whenever someone requests a hint through
this dashboard, and observes the server's own RoomUpdate.hint_points drop when
a hint is actually paid for. `RoomPoller` combines that persisted count with
the poll data (checks done, hint_cost) to estimate hint_points using AP's own
formula. This is exact for any slot whose hints are ONLY ever requested from
this dashboard - a hint redeemed via the player's own client or another tool
is invisible to it and will make the estimate read too high.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib

log = logging.getLogger("ap.hint_usage")


class HintUsageStore:
    """Persisted `{slot_num: count}` of hints paid for through this dashboard."""

    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        self._counts: dict[int, int] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("could not load %s: %s", self.path, e)
            return
        if isinstance(raw, dict):
            for k, v in raw.items():
                try:
                    self._counts[int(k)] = int(v)
                except (TypeError, ValueError):
                    continue

    def _persist(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps({str(k): v for k, v in self._counts.items()}, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("could not persist %s: %s", self.path, e)

    def record_used(self, slot_num: int) -> None:
        self._counts[slot_num] = self._counts.get(slot_num, 0) + 1
        self._persist()

    def used_count(self, slot_num: int) -> int:
        return self._counts.get(slot_num, 0)
