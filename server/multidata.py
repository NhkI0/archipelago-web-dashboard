"""
Reader for Archipelago `.archipelago` multidata files.

Format (as of AP 0.6.x):
    The file on disk is a zlib-compressed pickle of a dict. The schema has
    evolved across versions; we only consume the fields we need and tolerate
    missing keys.

Fields consumed:
    seed_name           : str
    slot_data           : dict[int, dict]              (per-slot game settings)
    slot_info           : dict[int, NetworkSlot|tuple] (slot -> (name, game, type, group_members))
    locations           : dict[int, dict[int, tuple]]  (finder_slot -> {loc_id: (item_id, recv_slot, flags)})
    connect_names       : dict[str, tuple]             (player name -> (team, slot))
    datapackage         : dict[str, GamePackage]       game -> {item_name_to_id, location_name_to_id, ...}
    games               : dict[int, str]               (slot -> game)
"""

from __future__ import annotations

import io
import pickle
import zlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SlotInfo:
    slot: int
    name: str
    game: str
    type: int = 1               # 0 spectator, 1 player, 2 group
    group_members: tuple = ()


@dataclass
class GamePackage:
    item_id_to_name: dict[int, str] = field(default_factory=dict)
    location_id_to_name: dict[int, str] = field(default_factory=dict)


@dataclass
class MultiData:
    seed_name: str
    slots: dict[int, SlotInfo]                       # slot num -> SlotInfo
    locations: dict[int, dict[int, tuple[int, int, int]]]  # recv_slot -> {loc_id: (item_id, sender_slot, flags)}
    games: dict[int, str]                            # slot -> game
    datapackage: dict[str, GamePackage]              # game -> package
    slot_data: dict[int, dict[str, Any]]             # slot -> per-slot game options
    raw: dict[str, Any]

    def deathlink_enabled(self, slot: int) -> bool:
        data = self.slot_data.get(slot)
        if not isinstance(data, dict):
            return False
        return bool(data.get("death_link"))

    # ── derived helpers ───────────────────────────────────────────────────────

    def total_locations_for(self, slot: int) -> int:
        """Total checks the player at this slot has to find."""
        return len(self.locations.get(slot, {}))

    def slot_by_name(self, name: str) -> SlotInfo | None:
        for s in self.slots.values():
            if s.name == name:
                return s
        return None

    def location_name(self, slot: int, loc_id: int) -> str:
        game = self.games.get(slot, "")
        pkg = self.datapackage.get(game)
        if pkg:
            return pkg.location_id_to_name.get(loc_id, f"loc#{loc_id}")
        return f"loc#{loc_id}"

    def item_name(self, slot: int, item_id: int) -> str:
        game = self.games.get(slot, "")
        pkg = self.datapackage.get(game)
        if pkg:
            return pkg.item_id_to_name.get(item_id, f"item#{item_id}")
        return f"item#{item_id}"


def _coerce_slot_info(raw_slots: Any, games: dict[int, str]) -> dict[int, SlotInfo]:
    out: dict[int, SlotInfo] = {}
    if not raw_slots:
        return out
    for slot_num, info in raw_slots.items():
        slot_num = int(slot_num)
        if hasattr(info, "name"):
            out[slot_num] = SlotInfo(
                slot=slot_num,
                name=getattr(info, "name", "") or "",
                game=getattr(info, "game", games.get(slot_num, "")) or "",
                type=int(getattr(info, "type", 1)),
                group_members=tuple(getattr(info, "group_members", ()) or ()),
            )
        elif isinstance(info, (tuple, list)):
            name = info[0] if len(info) > 0 else ""
            game = info[1] if len(info) > 1 else games.get(slot_num, "")
            stype = int(info[2]) if len(info) > 2 else 1
            members = tuple(info[3]) if len(info) > 3 else ()
            out[slot_num] = SlotInfo(slot_num, name or "", game or "", stype, members)
        elif isinstance(info, dict):
            out[slot_num] = SlotInfo(
                slot=slot_num,
                name=info.get("name", ""),
                game=info.get("game", games.get(slot_num, "")),
                type=int(info.get("type", 1)),
                group_members=tuple(info.get("group_members", ())),
            )
    return out


def _coerce_datapackage(raw_dp: Any) -> dict[str, GamePackage]:
    out: dict[str, GamePackage] = {}
    if not raw_dp:
        return out
    games = raw_dp.get("games") if isinstance(raw_dp, dict) and "games" in raw_dp else raw_dp
    if not isinstance(games, dict):
        return out
    for game, pkg in games.items():
        if not isinstance(pkg, dict):
            continue
        item_map = pkg.get("item_name_to_id") or {}
        loc_map = pkg.get("location_name_to_id") or {}
        out[game] = GamePackage(
            item_id_to_name={int(v): k for k, v in item_map.items()},
            location_id_to_name={int(v): k for k, v in loc_map.items()},
        )
    return out


class _StubClass(tuple):
    """Generic stand-in for AP-specific classes (NetworkSlot, SlotType, etc.).

    Inherits tuple so NamedTuple-based AP classes reconstruct correctly via
    `tuple.__new__(cls, args)` during unpickling. Exposes the NetworkSlot
    field names as properties so `_coerce_slot_info` can read them.
    """
    _ap_class_name = ""

    def __new__(cls, *args):
        return tuple.__new__(cls, args)

    def __setstate__(self, state):
        # Tuple subclasses can grow a __dict__, so this is harmless if state is a dict.
        if isinstance(state, dict):
            for k, v in state.items():
                try:
                    object.__setattr__(self, k, v)
                except AttributeError:
                    pass

    @property
    def name(self) -> str:
        return self[0] if len(self) > 0 else ""

    @property
    def game(self) -> str:
        return self[1] if len(self) > 1 else ""

    @property
    def type(self) -> int:
        if len(self) <= 2:
            return 1
        try:
            return int(self[2])
        except (TypeError, ValueError):
            # SlotType stub: peek at its underlying tuple value if any.
            inner = self[2]
            try:
                return int(inner[0])
            except Exception:
                return 1

    @property
    def group_members(self) -> tuple:
        return tuple(self[3]) if len(self) > 3 else ()


class _PermissiveUnpickler(pickle.Unpickler):
    """Resolve unknown classes (NetUtils.NetworkSlot, BaseClasses.MultiWorld, …) to stubs."""

    def find_class(self, module: str, name: str):
        try:
            return super().find_class(module, name)
        except (ImportError, AttributeError):
            stub = type(name, (_StubClass,), {"_ap_class_name": f"{module}.{name}"})
            return stub


def load_multidata(path: str) -> MultiData:
    with open(path, "rb") as fp:
        raw = fp.read()
    # `.archipelago` files start with a 1-byte multidata format version;
    # AP's own loader skips it. Try both forms for older files.
    try:
        payload = zlib.decompress(raw[1:])
    except zlib.error:
        payload = zlib.decompress(raw)
    # Multidata is a regular pickle. Trusted source (the server we control).
    data: dict[str, Any] = _PermissiveUnpickler(io.BytesIO(payload)).load()

    games = {int(k): v for k, v in (data.get("games") or {}).items()}
    slots = _coerce_slot_info(data.get("slot_info") or data.get("slots"), games)
    # If the multidata doesn't ship a top-level games map, derive it from slot_info.
    if not games:
        games = {s.slot: s.game for s in slots.values() if s.game}

    raw_locations = data.get("locations") or {}
    locations: dict[int, dict[int, tuple[int, int, int]]] = {}
    for recv_slot, table in raw_locations.items():
        recv_slot = int(recv_slot)
        slot_table: dict[int, tuple[int, int, int]] = {}
        if isinstance(table, dict):
            for loc_id, entry in table.items():
                if isinstance(entry, (tuple, list)) and len(entry) >= 2:
                    item_id = int(entry[0])
                    sender = int(entry[1])
                    flags = int(entry[2]) if len(entry) > 2 else 0
                    slot_table[int(loc_id)] = (item_id, sender, flags)
        locations[recv_slot] = slot_table

    datapackage = _coerce_datapackage(data.get("datapackage"))

    raw_slot_data = data.get("slot_data") or {}
    slot_data: dict[int, dict[str, Any]] = {}
    if isinstance(raw_slot_data, dict):
        for k, v in raw_slot_data.items():
            try:
                slot_data[int(k)] = v if isinstance(v, dict) else {}
            except (TypeError, ValueError):
                continue

    return MultiData(
        seed_name=str(data.get("seed_name") or ""),
        slots=slots,
        locations=locations,
        games=games,
        datapackage=datapackage,
        slot_data=slot_data,
        raw=data,
    )
