"""Hostile-fixture tests for the Phase 1 hardened multidata parser.

Each test crafts a .archipelago-shaped payload designed to defeat one specific guard in
server/multidata.py and asserts the guard rejects it. The real sample multiworlds in
core/multiworld/ are exercised elsewhere (test_build_app.py, and manually via load_multidata)
to confirm the hardening doesn't break legitimate files.
"""

from __future__ import annotations

import io
import os
import pathlib
import pickle
import zlib

import pytest

from server import multidata


def _pack(obj) -> bytes:
    """Build a .archipelago-shaped payload: 1-byte version + zlib(pickle)."""
    return b"\x03" + zlib.compress(pickle.dumps(obj))


# --- byte cap ------------------------------------------------------------


def test_oversized_file_rejected(monkeypatch):
    payload = _pack({"seed_name": "x" * 1000})
    monkeypatch.setattr(multidata, "MAX_ARCHIPELAGO_FILE_BYTES", len(payload) - 1)
    with pytest.raises(ValueError, match="exceeds"):
        multidata.parse_untrusted(payload)


def test_oversized_file_on_disk_rejected(monkeypatch, tmp_path: pathlib.Path):
    payload = _pack({"seed_name": "x" * 1000})
    monkeypatch.setattr(multidata, "MAX_ARCHIPELAGO_FILE_BYTES", len(payload) - 1)
    f = tmp_path / "big.archipelago"
    f.write_bytes(payload)
    with pytest.raises(ValueError, match="exceeds"):
        multidata.load_multidata(str(f))


# --- decompression bomb ---------------------------------------------------


def test_decompression_output_cap_rejected(monkeypatch):
    monkeypatch.setattr(multidata, "MAX_ARCHIPELAGO_FILE_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr(multidata, "MAX_DECOMPRESSED_BYTES", 1024)
    # Highly compressible payload: expands far past the 1 KiB cap.
    huge = pickle.dumps({"seed_name": "a" * 200_000})
    payload = b"\x03" + zlib.compress(huge)
    assert len(payload) < 5000  # tiny on the wire
    with pytest.raises(ValueError, match="exceeds"):
        multidata.parse_untrusted(payload)


def test_decompression_ratio_cap_rejected(monkeypatch):
    monkeypatch.setattr(multidata, "MAX_ARCHIPELAGO_FILE_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr(multidata, "MAX_DECOMPRESSED_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr(multidata, "MAX_DECOMPRESSION_RATIO", 5)
    huge = pickle.dumps({"seed_name": "a" * 200_000})
    payload = b"\x03" + zlib.compress(huge)
    # Well under the absolute cap, but far past a 5x ratio vs the compressed size.
    assert len(huge) > 5 * len(payload)
    with pytest.raises(ValueError, match="ratio"):
        multidata.parse_untrusted(payload)


# --- malicious pickle opcodes ---------------------------------------------


class _EvilReduce:
    """Object whose __reduce__ tells pickle to call os.system on load."""

    def __reduce__(self):
        return (os.system, ("echo pwned",))


def test_reduce_calling_os_system_is_neutered(monkeypatch):
    # Pack first, while os.system is still the real function — __reduce__ pickles
    # it by (module, qualname) reference, same as a genuine hostile file would.
    payload = _pack({"seed_name": "x", "evil": _EvilReduce()})
    calls = []
    monkeypatch.setattr(os, "system", lambda cmd: calls.append(cmd))
    # find_class("os", "system") is never in the allowlist, so REDUCE resolves
    # to the inert stub instead of the real os.system — it just builds a stub
    # tuple out of the args, it never calls anything.
    sanitized = multidata.parse_untrusted(payload)
    assert calls == []  # os.system was never invoked
    # The evil field survived only as inert data: a plain list, not a live object.
    assert sanitized["evil"] == ["echo pwned"]


def test_eval_global_is_neutered():
    """A pickle GLOBAL opcode naming builtins.eval must never resolve to the real eval."""
    buf = io.BytesIO()
    pickle.dump({"seed_name": "x"}, buf)
    # Manually splice in a STACK_GLOBAL-style reference by round-tripping through
    # the unpickler directly rather than hand-crafting opcodes: exercise find_class
    # the way the real Unpickler would for a hostile module/name pair.
    resolved = multidata._AllowlistUnpickler(io.BytesIO(b"")).find_class("builtins", "eval")
    assert resolved is not eval
    assert issubclass(resolved, multidata._StubClass)


def test_os_system_global_is_neutered():
    resolved = multidata._AllowlistUnpickler(io.BytesIO(b"")).find_class("os", "system")
    assert resolved is not os.system
    assert issubclass(resolved, multidata._StubClass)


def test_subprocess_popen_global_is_neutered():
    resolved = multidata._AllowlistUnpickler(io.BytesIO(b"")).find_class("subprocess", "Popen")
    assert issubclass(resolved, multidata._StubClass)


# --- unknown-but-benign AP classes still stub correctly --------------------


class _FakeNetworkSlot(tuple):
    """Stand-in for NetUtils.NetworkSlot: a namedtuple-shaped (name, game, type, group_members)."""

    def __new__(cls, name, game, type_, group_members):
        return tuple.__new__(cls, (name, game, type_, group_members))

    def __reduce__(self):
        # Pickled the way a real NamedTuple subclass would be: module/qualname
        # the unpickling environment can't import, so it must hit the stub path.
        return (_reconstruct_fake_slot, (tuple(self),))


def _reconstruct_fake_slot(args):
    return _FakeNetworkSlot(*args)


def test_unknown_ap_class_stubs_and_still_round_trips(monkeypatch):
    # Simulate "NetUtils.NetworkSlot" by pickling a class whose module path
    # find_class will be asked to resolve as ("tests_fake", "NetworkSlot") —
    # not in the allowlist, so it must come back as the inert stub, and the
    # stub's tuple contents must still be usable by _coerce_slot_info.
    class FakeModule:
        pass

    # We can't easily fabricate an arbitrary unimportable module/name pair
    # through pickle.dumps of a real object without a real class existing,
    # so exercise the unpickler's find_class directly for the known AP names
    # referenced in the docstring/allowlist comment.
    for mod, name in [("NetUtils", "NetworkSlot"), ("NetUtils", "SlotType"), ("NetUtils", "Hint")]:
        cls = multidata._AllowlistUnpickler(io.BytesIO(b"")).find_class(mod, name)
        assert issubclass(cls, multidata._StubClass)
        instance = cls("Alice", "TestGame", 1, ())
        assert instance.name == "Alice"
        assert instance.game == "TestGame"


# --- depth guard ------------------------------------------------------------


def test_deeply_nested_structure_rejected():
    nested: object = "leaf"
    for _ in range(multidata.MAX_SANITIZE_DEPTH + 50):
        nested = [nested]
    payload = _pack({"seed_name": "x", "deep": nested})
    with pytest.raises(ValueError, match="depth"):
        multidata.parse_untrusted(payload)


# --- safe real classes still resolve for real -------------------------------


def test_ordered_dict_resolves_to_real_class():
    from collections import OrderedDict

    payload = _pack({"seed_name": "x", "slot_data": {1: OrderedDict(a=1, b=2)}})
    sanitized = multidata.parse_untrusted(payload)
    assert sanitized["slot_data"]["1"] == {"a": 1, "b": 2}


# --- corpus sanity (small, hand-built — the real files are exercised separately) --


def test_well_formed_multidata_round_trips_through_sanitized_form(tmp_path: pathlib.Path):
    data = {
        "seed_name": "hardening-test-seed",
        "slot_info": {1: ("Alice", "TestGame", 1, ())},
        "locations": {1: {100: (5000, 1, 0)}},
        "datapackage": {
            "TestGame": {
                "item_name_to_id": {"Sword": 5000},
                "location_name_to_id": {"Chest": 100},
            }
        },
        "slot_data": {1: {"death_link": True}},
        "games": {1: "TestGame"},
    }
    payload = _pack(data)
    sanitized = multidata.parse_untrusted(payload)

    json_path = tmp_path / "room.json"
    multidata.save_sanitized(sanitized, json_path)
    md = multidata.load_sanitized(json_path)

    assert md.seed_name == "hardening-test-seed"
    assert md.slots[1].name == "Alice"
    assert md.location_name(1, 100) == "Chest"
    assert md.item_name(1, 5000) == "Sword"
    assert md.deathlink_enabled(1) is True
