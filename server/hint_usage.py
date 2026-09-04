"""
Local hint-spend counter, used only for archipelago.gg-polled rooms.

archipelago.gg's public tracker API can't tell a paid `!hint` from a free one,
so SessionManager tracks spends itself (a RoomUpdate.hint_points drop) and
RoomPoller combines that count with poll data to estimate hint_points. Exact
only if hints are always requested through this dashboard.
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
