"""
WorldState — the single in-memory snapshot the dashboard exposes.

It is built from a MultiData (totals, names) plus live updates from a Tracker
WebSocket connection (checked locations, hints, online status, goal flips).
Mutations enqueue deltas onto subscriber asyncio.Queues so the FastAPI WS
relay can push them to browsers.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field, asdict
from typing import Any

from .multidata import MultiData


@dataclass
class SlotState:
    slot: int
    name: str
    game: str
    total: int
    checked: set[int] = field(default_factory=set)
    online: bool = False
    hint_points: int = 0
    goal_completed: bool = False
    open_hints: int = 0   # hints whose item is in this slot's world but hasn't been checked yet

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot": self.slot,
            "name": self.name,
            "game": self.game,
            "total": self.total,
            "checked": len(self.checked),
            "remaining": max(0, self.total - len(self.checked)),
            "percent": (100.0 * len(self.checked) / self.total) if self.total else 0.0,
            "online": self.online,
            "hint_points": self.hint_points,
            "goal_completed": self.goal_completed,
            "open_hints": self.open_hints,
        }


@dataclass
class HintRecord:
    finding_slot: int           # who can find it
    receiving_slot: int         # who receives it
    item_id: int
    location_id: int
    item_name: str
    location_name: str
    found: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorldState:
    def __init__(self, multidata: MultiData) -> None:
        self.multidata = multidata
        self.seed_name = multidata.seed_name
        self.slots: dict[int, SlotState] = {}
        self.hints: list[HintRecord] = []
        self.hint_cost: int = 10            # AP default; updated from RoomInfo / RoomUpdate
        self._subscribers: set[asyncio.Queue] = set()
        self._init_from_multidata()

    def _init_from_multidata(self) -> None:
        for slot_num, info in self.multidata.slots.items():
            if info.type != 1:           # only real player slots
                continue
            self.slots[slot_num] = SlotState(
                slot=slot_num,
                name=info.name,
                game=info.game,
                total=self.multidata.total_locations_for(slot_num),
            )

    # ── snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed_name": self.seed_name,
            "slots": [s.to_dict() for s in self.slots.values()],
            "hints": [h.to_dict() for h in self.hints],
            "hint_cost": self.hint_cost,
            "totals": {
                "total_locations": sum(s.total for s in self.slots.values()),
                "total_checked": sum(len(s.checked) for s in self.slots.values()),
            },
        }

    # ── pub/sub ───────────────────────────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _emit(self, event: dict[str, Any]) -> None:
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    # ── mutators (called by tracker.py) ───────────────────────────────────────

    def apply_room_update(self, payload: dict[str, Any]) -> None:
        """RoomUpdate from AP — covers checked_locations, hint_points, players."""
        changed = False

        if "hint_cost" in payload:
            try:
                hc = int(payload["hint_cost"])
                if hc != self.hint_cost:
                    self.hint_cost = hc
                    changed = True
            except (TypeError, ValueError):
                pass

        # `checked_locations` arrives as a list[int] for the server view in some
        # versions; in others it is broken down per slot via `players` updates.
        # We accept both: a flat list applies to every slot via membership check.
        if "checked_locations" in payload:
            cl = payload["checked_locations"]
            if isinstance(cl, list):
                flat = set(int(x) for x in cl)
                for slot in self.slots.values():
                    valid = set(self.multidata.locations.get(slot.slot, {}).keys())
                    new_checked = flat & valid
                    if new_checked != slot.checked:
                        slot.checked = new_checked
                        changed = True
            elif isinstance(cl, dict):
                for s, ids in cl.items():
                    s = int(s)
                    if s in self.slots:
                        self.slots[s].checked = set(int(x) for x in ids)
                        changed = True

        for p in payload.get("players", []) or []:
            slot_num = int(p.get("slot", 0))
            if slot_num in self.slots:
                self.slots[slot_num].online = bool(p.get("status", 0)) or p.get("connected", True) is True
                changed = True

        if "hint_points" in payload:
            hp = payload["hint_points"]
            if isinstance(hp, dict):
                for s, v in hp.items():
                    s = int(s)
                    if s in self.slots:
                        self.slots[s].hint_points = int(v)
                        changed = True

        if changed:
            self._emit({"type": "room_update", "snapshot": self.snapshot()})

    def apply_print_json(self, payload: dict[str, Any]) -> None:
        """Surface hint and goal-completion events to the frontend log."""
        msg_type = payload.get("type", "")
        if msg_type == "Hint":
            item = payload.get("item") or {}
            recv = int(payload.get("receiving") or 0)
            send = int(item.get("player") or 0)
            item_id = int(item.get("item") or 0)
            location_id = int(item.get("location") or 0)
            found = bool(payload.get("found"))
            rec = HintRecord(
                finding_slot=send,
                receiving_slot=recv,
                item_id=item_id,
                location_id=location_id,
                item_name=self.multidata.item_name(recv, item_id),
                location_name=self.multidata.location_name(send, location_id),
                found=found,
            )
            # de-dupe by (send, recv, item_id, location_id)
            key = (rec.finding_slot, rec.receiving_slot, rec.item_id, rec.location_id)
            existing = next(
                (h for h in self.hints
                 if (h.finding_slot, h.receiving_slot, h.item_id, h.location_id) == key),
                None,
            )
            if existing is None:
                self.hints.append(rec)
            else:
                existing.found = existing.found or rec.found
            self._recount_open_hints()
            self._emit({"type": "hint", "hint": rec.to_dict()})
        elif msg_type == "Goal":
            slot_num = int(payload.get("slot") or 0)
            if slot_num in self.slots:
                self.slots[slot_num].goal_completed = True
                self._emit({"type": "goal", "slot": slot_num})

    def apply_hint_store(self, key: str, value: Any) -> None:
        """Replace hints for one slot from `_read_hints_0_<slot>` data store entry."""
        if not key.startswith("_read_hints_") or not isinstance(value, list):
            return
        try:
            slot_num = int(key.rsplit("_", 1)[-1])
        except ValueError:
            return

        # Drop existing hints owned by this slot, then re-add from the store.
        self.hints = [
            h for h in self.hints
            if h.finding_slot != slot_num and h.receiving_slot != slot_num
        ]
        added = 0
        for raw in value:
            if not isinstance(raw, dict):
                continue
            recv = int(raw.get("receiving_player", 0))
            send = int(raw.get("finding_player", 0))
            item_id = int(raw.get("item", 0))
            location_id = int(raw.get("location", 0))
            found = bool(raw.get("found", False))
            rec = HintRecord(
                finding_slot=send,
                receiving_slot=recv,
                item_id=item_id,
                location_id=location_id,
                item_name=self.multidata.item_name(recv, item_id),
                location_name=self.multidata.location_name(send, location_id),
                found=found,
            )
            key_t = (rec.finding_slot, rec.receiving_slot, rec.item_id, rec.location_id)
            if not any((h.finding_slot, h.receiving_slot, h.item_id, h.location_id) == key_t for h in self.hints):
                self.hints.append(rec)
                added += 1
        self._recount_open_hints()
        self._emit({"type": "hints_replaced", "snapshot": self.snapshot()})

    def _recount_open_hints(self) -> None:
        per_slot: dict[int, int] = {}
        for h in self.hints:
            if not h.found:
                per_slot[h.finding_slot] = per_slot.get(h.finding_slot, 0) + 1
        for slot in self.slots.values():
            slot.open_hints = per_slot.get(slot.slot, 0)


def to_json(obj: Any) -> str:
    return json.dumps(obj, default=lambda o: list(o) if isinstance(o, set) else str(o))
