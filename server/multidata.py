"""
Reader for Archipelago .archipelago multidata files.

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
    datapackage         : dict[str, GamePackage]        game -> {item_name_to_id, location_name_to_id, ...}
    games               : dict[int, str]                (slot -> game)
"""

from __future__ import annotations

import io
import json
import pathlib
import pickle
import zlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

# Crash prevention limits, should reasticaly never be reached

MAX_ARCHIPELAGO_FILE_BYTES = 32 * 1024 * 1024   # on-disk / uploaded file size
MAX_DECOMPRESSED_BYTES = 256 * 1024 * 1024      # unpacked pickle byte ceiling
MAX_DECOMPRESSION_RATIO = 300                    # output/input; catches zip bombs early
MAX_SANITIZE_DEPTH = 64                          # nested container depth ceiling

SANITIZED_FORMAT_VERSION = 1


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

    def deathlink_enabled(self, slot: int) -> bool:
        data = self.slot_data.get(slot)
        if not isinstance(data, dict):
            return False
        return bool(data.get("death_link"))

    # derived helpers

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


def _coerce_slot_type(raw: Any) -> int:
    """SlotType is a pickled IntEnum; after sanitizing it may already be a
    plain int, or (via the stub-class path) a single-element list wrapping
    its underlying value. Unwrap either shape, defaulting to "player"."""
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else 1
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 1


def _coerce_slot_info(raw_slots: Any, games: dict[int, str]) -> dict[int, SlotInfo]:
    out: dict[int, SlotInfo] = {}
    if not raw_slots:
        return out
    for slot_num, info in raw_slots.items():
        slot_num = int(slot_num)
        if isinstance(info, (tuple, list)):
            name = info[0] if len(info) > 0 else ""
            game = info[1] if len(info) > 1 else games.get(slot_num, "")
            stype = _coerce_slot_type(info[2]) if len(info) > 2 else 1
            members = tuple(info[3]) if len(info) > 3 else ()
            out[slot_num] = SlotInfo(slot_num, name or "", game or "", stype, members)
        elif isinstance(info, dict):
            out[slot_num] = SlotInfo(
                slot=slot_num,
                name=info.get("name", ""),
                game=info.get("game", games.get(slot_num, "")),
                type=_coerce_slot_type(info.get("type", 1)),
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
    """Inert stand-in for any pickled class we don't explicitly trust.

    Inherits tuple so NamedTuple-based AP classes (NetworkSlot, SlotType, Hint, ...) reconstruct
    correctly via tuple.__new__(cls, args) during unpickling, and so __reduce__/REDUCE-driven
    construction can never do anything beyond building a plain tuple: there is no __init__,
    __call__, or side-effecting method for a hostile pickle to reach.
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


_SAFE_REAL_CLASSES: dict[tuple[str, str], type] = {
    ("collections", "OrderedDict"): OrderedDict,
    ("builtins", "set"): set,
    ("builtins", "frozenset"): frozenset,
    ("builtins", "dict"): dict,
    ("builtins", "list"): list,
    ("builtins", "tuple"): tuple,
}

_stub_class_cache: dict[tuple[str, str], type] = {}


def _stub_class_for(module: str, name: str) -> type:
    key = (module, name)
    cls = _stub_class_cache.get(key)
    if cls is None:
        cls = type(name, (_StubClass,), {"_ap_class_name": f"{module}.{name}"})
        _stub_class_cache[key] = cls
    return cls


class _AllowlistUnpickler(pickle.Unpickler):
    """Resolve pickled classes through a strict allowlist.

    find_class is pickle's only route to naming a callable, so this is the correct and
    sufficient chokepoint. Only _SAFE_REAL_CLASSES entries resolve to a real, callable class;
    every other (module, name), known AP classes as much as unexpected/hostile ones, resolves
    to the inert _StubClass. The real Unpickler.find_class() is never called.
    """

    def find_class(self, module: str, name: str):
        real = _SAFE_REAL_CLASSES.get((module, name))
        if real is not None:
            return real
        return _stub_class_for(module, name)


def _bounded_decompress(
    payload: bytes,
    *,
    max_bytes: int = MAX_DECOMPRESSED_BYTES,
    max_ratio: int = MAX_DECOMPRESSION_RATIO,
) -> bytes:
    """Zlib-decompress payload with an absolute output cap and a ratio cap.

    Checked incrementally (1 MiB at a time) so a zip bomb would be caught after a bounded
    amount of wasted work, not after fully expanding into memory.
    """
    decompressor = zlib.decompressobj()
    out = bytearray()
    pending = payload
    chunk_limit = 1 << 20

    def _check() -> None:
        if len(out) > max_bytes:
            raise ValueError(f"decompressed multidata exceeds {max_bytes} bytes")
        if payload and len(out) > max_ratio * len(payload):
            raise ValueError(f"decompression ratio exceeds {max_ratio}x safety ceiling")

    while True:
        chunk = decompressor.decompress(pending, chunk_limit)
        pending = decompressor.unconsumed_tail
        out.extend(chunk)
        _check()
        if not chunk and not pending:
            break

    out.extend(decompressor.flush())
    _check()
    return bytes(out)


def _to_jsonable(obj: Any, *, depth: int = 0) -> Any:
    """Recursively flatten an unpickled object graph to JSON-safe primitives.

    This is the actual sanitization step: whatever came out of the allowlisted unpickler
    (dicts, lists, tuples, _StubClass instances, the handful of real safe classes) is reduced
    here to nothing but dict/list/str/int/float/bool/None. No object identity, custom class, or
    reference to executable code survives this call; what goes in a sanitized JSON file (or is
    later re-parsed) can never resume being a pickle.
    """
    if depth > MAX_SANITIZE_DEPTH:
        raise ValueError(f"multidata nesting exceeds depth {MAX_SANITIZE_DEPTH}")
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return obj.hex()
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v, depth=depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_to_jsonable(v, depth=depth + 1) for v in obj]
    # Anything else (an object type outside what the allowlist can produce, which should not
    # happen but must never crash or smuggle an object through); fall back to its repr rather
    # than raising.
    return repr(obj)


def parse_untrusted(payload: bytes) -> dict[str, Any]:
    """Parse raw .archipelago bytes into a sanitized, safe, JSON dict.

    This is the only function in the module that unpickles. payload must
    be treated as attacker-controlled: enforce the byte cap on it before calling this (e.g. at
    the HTTP upload boundary), and run it inside the process sandbox (server.sandbox) for
    anything not already trusted.
    """
    if len(payload) > MAX_ARCHIPELAGO_FILE_BYTES:
        raise ValueError(f"multidata file exceeds {MAX_ARCHIPELAGO_FILE_BYTES} bytes")

    # .archipelago files start with a 1-byte multidata format version;
    # AP's own loader skips it. Try both forms for older files.
    try:
        decompressed = _bounded_decompress(payload[1:])
    except zlib.error:
        decompressed = _bounded_decompress(payload)

    raw: dict[str, Any] = _AllowlistUnpickler(io.BytesIO(decompressed)).load()
    sanitized = _to_jsonable(raw)
    if not isinstance(sanitized, dict):
        raise ValueError("multidata root is not a mapping")
    sanitized["format_version"] = SANITIZED_FORMAT_VERSION
    return sanitized


def multidata_from_sanitized(data: dict[str, Any]) -> MultiData:
    """Build a MultiData from an already-sanitized dict (never unpickles)."""
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
    )


def save_sanitized(data: dict[str, Any], path: str | pathlib.Path) -> None:
    """Persist a sanitized dict to disk, compactly."""
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, separators=(",", ":"))


def load_sanitized(path: str | pathlib.Path) -> MultiData:
    """Load a previously sanitized JSON file."""
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    return multidata_from_sanitized(data)


def load_multidata(path: str) -> MultiData:
    """Self-hosted convenience: parse a .archipelago file straight to MultiData.

    Still goes through the hardened parse_untrusted() pipeline, the file
    comes from the host's own machine, but hardening it costs nothing and keeps a single code
    path with the hosted upload flow.
    """
    size = pathlib.Path(path).stat().st_size
    if size > MAX_ARCHIPELAGO_FILE_BYTES:
        raise ValueError(f"multidata file exceeds {MAX_ARCHIPELAGO_FILE_BYTES} bytes")
    with open(path, "rb") as fp:
        raw = fp.read()
    sanitized = parse_untrusted(raw)
    return multidata_from_sanitized(sanitized)
