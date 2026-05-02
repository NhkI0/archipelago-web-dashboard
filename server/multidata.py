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
    locations           : dict[int, dict[int, tuple]]  (recv_slot -> {loc_id: (item_id, sender_slot, flags)})
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
    raw: dict[str, Any]

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


def load_multidata(path: str) -> MultiData:
    with open(path, "rb") as fp:
        compressed = fp.read()
    payload = zlib.decompress(compressed)
    # Multidata is a regular pickle.  Trusted source (the server we control).
    data: dict[str, Any] = pickle.load(io.BytesIO(payload))

    games = {int(k): v for k, v in (data.get("games") or {}).items()}
    slots = _coerce_slot_info(data.get("slot_info") or data.get("slots"), games)

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

    return MultiData(
        seed_name=str(data.get("seed_name") or ""),
        slots=slots,
        locations=locations,
        games=games,
        datapackage=datapackage,
        raw=data,
    )
