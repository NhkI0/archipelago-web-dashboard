"""
WorldState — the single in-memory snapshot the dashboard exposes.

It is built from a MultiData (totals, names) plus live updates from a Tracker
WebSocket connection (checked locations, hints, online status, goal flips).
Mutations enqueue deltas onto subscriber asyncio.Queues so the FastAPI WS
relay can push them to browsers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

from .multidata import MultiData

log = logging.getLogger("ap.state")


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
        # Refcount of open dashboard WebSockets per slot; drives `online`.
        self._presence: dict[int, int] = {}
        self._init_from_multidata()

    # Slots that exist for tooling and should never appear on the public
    # dashboard. Empty today; kept for future tooling-slot needs.
    HIDDEN_SLOT_NAMES: set[str] = set()

    def _init_from_multidata(self) -> None:
        for slot_num, info in self.multidata.slots.items():
            if info.type != 1:           # only real player slots
                continue
            if info.name in self.HIDDEN_SLOT_NAMES:
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

    # ── presence (called by the /ws/live relay in main.py) ────────────────────

    def add_presence(self, slot_num: int) -> None:
        """Register an open dashboard WS for `slot_num`; light the dot if first."""
        if slot_num not in self.slots:
            return
        self._presence[slot_num] = self._presence.get(slot_num, 0) + 1
        slot = self.slots[slot_num]
        if not slot.online:
            slot.online = True
            self._emit({"type": "room_update", "snapshot": self.snapshot()})

    def remove_presence(self, slot_num: int) -> None:
        """Drop one open dashboard WS for `slot_num`; dim the dot if it was last."""
        if slot_num not in self.slots:
            return
        remaining = self._presence.get(slot_num, 0) - 1
        if remaining > 0:
            self._presence[slot_num] = remaining
            return
        self._presence.pop(slot_num, None)
        slot = self.slots[slot_num]
        if slot.online:
            slot.online = False
            self._emit({"type": "room_update", "snapshot": self.snapshot()})

    # ── mutators (called by tracker.py) ───────────────────────────────────────

    def apply_slot_checks(self, slot_num: int, location_ids: list[int], *, replace: bool) -> None:
        """Update one slot's checked set.

        Connected packets carry the *full* current set (replace=True).
        RoomUpdate packets carry *new* checks only — and AP broadcasts those
        team-wide, so we filter to IDs that actually belong to this slot's
        location pool before unioning (replace=False).
        """
        slot = self.slots.get(slot_num)
        if slot is None:
            return
        ids = set(int(x) for x in location_ids)
        if replace:
            new_set = ids
        else:
            valid = set(self.multidata.locations.get(slot_num, {}).keys())
            new_set = slot.checked | (ids & valid)
        if new_set != slot.checked:
            slot.checked = new_set
            self._emit({"type": "room_update", "snapshot": self.snapshot()})

    def apply_room_update_meta(self, payload: dict[str, Any], *, owner_slot: int | None = None) -> None:
        """Apply non-check RoomUpdate fields (hint_cost, hint_points).

        `owner_slot` identifies whose connection produced this packet, used to
        attribute single-int `hint_points` (AP sends it as the connected slot's
        balance, not a per-slot map).
        """
        changed = False

        if "hint_cost" in payload:
            try:
                hc = int(payload["hint_cost"])
                if hc != self.hint_cost:
                    self.hint_cost = hc
                    changed = True
            except (TypeError, ValueError):
                pass

        # NB: we intentionally ignore AP's RoomUpdate.players for `online`.
        # The backend opens one passive Tracker WS per slot (see tracker.py),
        # so every slot is permanently "connected" from AP's point of view and
        # that signal can't tell a real player apart from our own tracker.
        # `online` is instead driven by dashboard presence (add/remove_presence).

        if "hint_points" in payload:
            hp = payload["hint_points"]
            if isinstance(hp, dict):
                for s, v in hp.items():
                    s = int(s)
                    if s in self.slots:
                        try:
                            new_hp = int(v)
                        except (TypeError, ValueError):
                            continue
                        if self.slots[s].hint_points != new_hp:
                            self.slots[s].hint_points = new_hp
                            changed = True
            elif owner_slot is not None and owner_slot in self.slots:
                try:
                    new_hp = int(hp)
                except (TypeError, ValueError):
                    new_hp = None
                if new_hp is not None and self.slots[owner_slot].hint_points != new_hp:
                    self.slots[owner_slot].hint_points = new_hp
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

    def apply_client_status(self, key: str, value: Any) -> None:
        """Seed `goal_completed` from `_read_client_status_0_<slot>` data store entry.

        AP exposes each slot's ClientStatus enum in the team-wide data store;
        a value of 30 (`CLIENT_GOAL`) means the slot has goaled. Reading this
        on (re)connect lets us recover goal flags across server restarts and
        catch goals that happened while the bridge was offline.
        """
        if not key.startswith("_read_client_status_"):
            return
        try:
            slot_num = int(key.rsplit("_", 1)[-1])
            status = int(value)
        except (TypeError, ValueError):
            return
        slot = self.slots.get(slot_num)
        if slot is None:
            return
        goaled = status >= 30
        if goaled and not slot.goal_completed:
            slot.goal_completed = True
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
        for raw in value:
            # AP's data store ships hints as `Hint` NamedTuples, which JSON-
            # encode to lists like [recv, find, loc, item, found, entrance,
            # flags, status]. Older / patched servers may send dicts; accept
            # both shapes.
            if isinstance(raw, dict):
                recv = int(raw.get("receiving_player", 0))
                send = int(raw.get("finding_player", 0))
                item_id = int(raw.get("item", 0))
                location_id = int(raw.get("location", 0))
                found = bool(raw.get("found", False))
            elif isinstance(raw, (list, tuple)) and len(raw) >= 5:
                recv = int(raw[0])
                send = int(raw[1])
                location_id = int(raw[2])
                item_id = int(raw[3])
                found = bool(raw[4])
            else:
                continue
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
        self._recount_open_hints()
        log.info("apply_hint_store key=%s parsed %d hints", key, sum(
            1 for h in self.hints if h.finding_slot == slot_num or h.receiving_slot == slot_num
        ))
        self._emit({"type": "hints_replaced", "snapshot": self.snapshot()})

    def _recount_open_hints(self) -> None:
        per_slot: dict[int, int] = {}
        for h in self.hints:
            if not h.found:
                per_slot[h.finding_slot] = per_slot.get(h.finding_slot, 0) + 1
        for slot in self.slots.values():
            slot.open_hints = per_slot.get(slot.slot, 0)
