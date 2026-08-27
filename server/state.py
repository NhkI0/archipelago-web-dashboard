"""
WorldState: the single in-memory snapshot the dashboard exposes.

It is built from a MultiData (totals, names) plus live updates from a Tracker
WebSocket connection (checked locations, hints, online status, goal flips).
Mutations enqueue deltas onto subscriber asyncio.Queues so the FastAPI WS
relay can push them to browsers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import time
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
class ReceivedItem:
    """An item that has landed in a slot's game.

    Identified by the finder location that produced it `(finder_slot,
    location_id)`: each location is checked once and yields exactly one item
    to one recipient, so that pair is a stable dedupe key across restarts.
    `ts` is the wall-clock time the bridge first observed the check, or None
    for the historical backlog that existed before timestamp tracking began
    (AP itself carries no timestamps).
    """
    recv_slot: int
    finder_slot: int
    location_id: int
    item_id: int
    ts: float | None = None


# Default tags a receiving player can pin on a hint for an item they're waiting
# on. The empty string is the implicit "untagged" state and is never stored.
# Hosts override the active set via config.toml (see WorldState.allowed_tags).
HINT_TAGS: set[str] = {"bked", "mandatory", "comfort"}


@dataclass
class HintRecord:
    finding_slot: int           # who can find it
    receiving_slot: int         # who receives it
    item_id: int
    location_id: int
    item_name: str
    location_name: str
    found: bool = False
    tag: str = ""               # one of HINT_TAGS, or "" for untagged

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorldState:
    def __init__(
        self,
        multidata: MultiData,
        *,
        items_file: pathlib.Path | None = None,
        tags_file: pathlib.Path | None = None,
        allowed_tags: list[str] | None = None,
    ) -> None:
        self.multidata = multidata
        self.seed_name = multidata.seed_name
        # Active hint-tag ids (from config.toml); falls back to the built-ins.
        self.allowed_tags: set[str] = set(allowed_tags) if allowed_tags is not None else set(HINT_TAGS)
        self.slots: dict[int, SlotState] = {}
        self.hints: list[HintRecord] = []
        self.hint_cost: int = 10            # AP default; updated from RoomInfo / RoomUpdate
        # Reachability of the multiworld server itself, as opposed to any single
        # slot's login state, set by main.py from AP_HOST/AP_PORT and kept live
        # by Tracker's connection callback.
        self.server_status: dict[str, Any] = {"host": "", "port": 0, "connected": False}
        self._subscribers: set[asyncio.Queue] = set()
        # Refcount of open dashboard WebSockets per slot; drives `online`.
        self._presence: dict[int, int] = {}
        # Received-item log, keyed by (finder_slot, location_id). Persisted to
        # `items_file` so observed timestamps survive restarts.
        self._items_file = items_file
        self._received: dict[tuple[int, int], ReceivedItem] = {}
        # Player-assigned hint tags, keyed by the hint's stable identity
        # (finding_slot, receiving_slot, item_id, location_id). Kept separate
        # from HintRecord because hints are rebuilt wholesale from AP's data
        # store; the tags outlive those rebuilds and restarts via `tags_file`.
        self._tags_file = tags_file
        self._hint_tags: dict[tuple[int, int, int, int], str] = {}
        # Slots whose initial (replace=True) check snapshot we've already
        # processed; lets us distinguish the first bulk load from live checks.
        self._initial_loaded: set[int] = set()
        self._init_from_multidata()
        # If a same-seed log already exists, checks we discover that aren't in
        # it happened while the bridge was down and get stamped "now". With no
        # usable file (fresh install, or a log left over from another seed) the
        # entire initial snapshot is undated backlog. `_load_items` sets this
        # True only when it actually loads records for the current seed.
        self._had_persisted = False
        self._load_items()
        self._load_tags()

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

    # ── received-item log ──────────────────────────────────────────────────────

    def _load_items(self) -> None:
        if not self._items_file or not self._items_file.exists():
            return
        try:
            raw = json.loads(self._items_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("could not load %s: %s", self._items_file, e)
            return
        if not isinstance(raw, dict):
            return
        # The log is seed-scoped: a file left over from a previous multiworld
        # must not bleed its received items into the new seed's slots. Discard
        # anything whose stamped seed doesn't match the loaded multidata (this
        # also rejects the older, unstamped flat format).
        if raw.get("seed") != self.seed_name:
            log.info("received-items log is for a different seed (%r != %r); starting fresh",
                     raw.get("seed"), self.seed_name)
            return
        items = raw.get("items")
        if not isinstance(items, dict):
            return
        for key, rec in items.items():
            try:
                finder, loc = (int(x) for x in str(key).split(":", 1))
                ts = rec.get("ts")
                self._received[(finder, loc)] = ReceivedItem(
                    recv_slot=int(rec["recv"]),
                    finder_slot=finder,
                    location_id=loc,
                    item_id=int(rec["item"]),
                    ts=float(ts) if ts is not None else None,
                )
            except (TypeError, ValueError, KeyError, AttributeError):
                continue
        self._had_persisted = True
        log.info("loaded %d received-item records from %s", len(self._received), self._items_file)

    def _persist_items(self) -> None:
        if not self._items_file:
            return
        payload = {
            "seed": self.seed_name,
            "items": {
                f"{r.finder_slot}:{r.location_id}": {"recv": r.recv_slot, "item": r.item_id, "ts": r.ts}
                for r in self._received.values()
            },
        }
        tmp = self._items_file.with_suffix(self._items_file.suffix + ".tmp")
        try:
            self._items_file.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, self._items_file)
        except OSError as e:
            log.warning("could not persist %s: %s", self._items_file, e)

    def _record_received(self, finder_slot: int, new_loc_ids: set[int], *, backfill: bool) -> None:
        """Log items produced by newly-checked locations in `finder_slot`."""
        table = self.multidata.locations.get(finder_slot, {})
        now = time.time()
        changed = False
        for loc_id in new_loc_ids:
            entry = table.get(loc_id)
            if entry is None:
                continue
            key = (finder_slot, loc_id)
            if key in self._received:
                continue
            item_id, recv_slot, _flags = entry
            self._received[key] = ReceivedItem(
                recv_slot=recv_slot,
                finder_slot=finder_slot,
                location_id=loc_id,
                item_id=item_id,
                ts=None if backfill else now,
            )
            changed = True
        if changed:
            self._persist_items()

    def received_for(self, slot_num: int) -> list[dict[str, Any]]:
        """Items this slot has received, most recent first (undated last)."""
        rows = [
            {
                "item_name": self.multidata.item_name(r.recv_slot, r.item_id),
                "location_name": self.multidata.location_name(r.finder_slot, r.location_id),
                "sender": self.slots[r.finder_slot].name if r.finder_slot in self.slots else f"slot#{r.finder_slot}",
                "timestamp": r.ts,
            }
            for r in self._received.values()
            if r.recv_slot == slot_num
        ]
        rows.sort(key=lambda x: (x["timestamp"] is not None, x["timestamp"] or 0.0), reverse=True)
        return rows

    # ── hint tags ──────────────────────────────────────────────────────────────

    @staticmethod
    def _tag_key(rec: HintRecord) -> tuple[int, int, int, int]:
        return (rec.finding_slot, rec.receiving_slot, rec.item_id, rec.location_id)

    def _apply_tag(self, rec: HintRecord) -> None:
        """Stamp a freshly-built hint with its persisted tag, if any."""
        rec.tag = self._hint_tags.get(self._tag_key(rec), "")

    def _load_tags(self) -> None:
        if not self._tags_file or not self._tags_file.exists():
            return
        try:
            raw = json.loads(self._tags_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("could not load %s: %s", self._tags_file, e)
            return
        if not isinstance(raw, dict) or raw.get("seed") != self.seed_name:
            # Seed-scoped like the received-item log: tags from another
            # multiworld must not bleed onto this seed's hints.
            return
        tags = raw.get("tags")
        if not isinstance(tags, dict):
            return
        for key, tag in tags.items():
            if tag not in self.allowed_tags:
                continue
            try:
                find, recv, item, loc = (int(x) for x in str(key).split(":", 3))
            except (TypeError, ValueError):
                continue
            self._hint_tags[(find, recv, item, loc)] = tag
        log.info("loaded %d hint tags from %s", len(self._hint_tags), self._tags_file)

    def _persist_tags(self) -> None:
        if not self._tags_file:
            return
        payload = {
            "seed": self.seed_name,
            "tags": {f"{f}:{r}:{i}:{l}": tag for (f, r, i, l), tag in self._hint_tags.items()},
        }
        tmp = self._tags_file.with_suffix(self._tags_file.suffix + ".tmp")
        try:
            self._tags_file.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, self._tags_file)
        except OSError as e:
            log.warning("could not persist %s: %s", self._tags_file, e)

    def set_hint_tag(
        self, finding_slot: int, receiving_slot: int, item_id: int, location_id: int, tag: str
    ) -> bool:
        """Set (or clear, with tag="") the tag on one hint. Returns True if the
        hint exists in the current seed and the change was applied."""
        tag = tag or ""
        if tag and tag not in self.allowed_tags:
            raise ValueError(f"unknown hint tag {tag!r}")
        key = (finding_slot, receiving_slot, item_id, location_id)
        rec = next((h for h in self.hints if self._tag_key(h) == key), None)
        if rec is None:
            return False
        if tag:
            self._hint_tags[key] = tag
        else:
            self._hint_tags.pop(key, None)
        rec.tag = tag
        self._persist_tags()
        self._emit({"type": "hints_replaced", "snapshot": self.snapshot()})
        return True

    def set_server_status(self, host: str, port: int, connected: bool) -> None:
        """Update the multiworld's reachability; emits only when it actually changes."""
        prev = self.server_status
        if prev.get("host") == host and prev.get("port") == port and prev.get("connected") == connected:
            return
        self.server_status = {"host": host, "port": port, "connected": connected}
        self._emit({"type": "server_status", "snapshot": self.snapshot()})

    # ── snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        return {
            "seed_name": self.seed_name,
            "slots": [s.to_dict() for s in self.slots.values()],
            "hints": [h.to_dict() for h in self.hints],
            "hint_cost": self.hint_cost,
            "server": dict(self.server_status),
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
        RoomUpdate packets carry *new* checks only, and AP broadcasts those
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
            added = new_set - slot.checked
            slot.checked = new_set
            if added:
                # The first bulk snapshot of a never-seen slot is undated backlog
                # (unless we already had a persisted log to compare against).
                backfill = replace and slot_num not in self._initial_loaded and not self._had_persisted
                self._record_received(slot_num, added, backfill=backfill)
            self._emit({"type": "room_update", "snapshot": self.snapshot()})
        if replace:
            self._initial_loaded.add(slot_num)

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

    def _hint_belongs_to_seed(
        self, finding_slot: int, location_id: int, item_id: int, receiving_slot: int
    ) -> bool:
        """True iff this hint matches the loaded multidata's actual placement.

        AP location/item IDs are game-global, not seed-specific, so a hint left
        over from a previous multiworld can still resolve to real-looking names
        against a new seed while pointing at the wrong placement. The multidata
        is ground truth: `locations[finder][loc]` is exactly `(item, recv, flags)`
        for the current seed, and every genuine hint references a real placement,
        so a mismatch means the hint came from another seed and must be dropped.
        """
        entry = self.multidata.locations.get(finding_slot, {}).get(location_id)
        if entry is None:
            return False
        md_item, md_recv, _flags = entry
        return md_item == item_id and md_recv == receiving_slot

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
            if not self._hint_belongs_to_seed(send, location_id, item_id, recv):
                log.info("dropping hint not in current seed: find=%d loc=%d item=%d recv=%d",
                         send, location_id, item_id, recv)
                return
            rec = HintRecord(
                finding_slot=send,
                receiving_slot=recv,
                item_id=item_id,
                location_id=location_id,
                item_name=self.multidata.item_name(recv, item_id),
                location_name=self.multidata.location_name(send, location_id),
                found=found,
            )
            self._apply_tag(rec)
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
        if not key.startswith("_read_hints_"):
            return
        try:
            slot_num = int(key.rsplit("_", 1)[-1])
        except ValueError:
            return

        # A slot with no hints in the current seed comes back as `None` (unset
        # data-store key), not an empty list. Treat that as "no hints" and fall
        # through to clear any stale ones rather than early-returning.
        raw_hints = value if isinstance(value, list) else []

        # Drop existing hints owned by this slot, then re-add from the store.
        self.hints = [
            h for h in self.hints
            if h.finding_slot != slot_num and h.receiving_slot != slot_num
        ]
        for raw in raw_hints:
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
            if not self._hint_belongs_to_seed(send, location_id, item_id, recv):
                # Stale hint from a previous seed still lingering in AP's data
                # store; its IDs may resolve to real names here but point at the
                # wrong placement, so skip it.
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
            self._apply_tag(rec)
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
