"""Duplicate items stay hintable until every unsent copy is hinted."""

from __future__ import annotations

from server.multidata import multidata_from_sanitized
from server.state import HintRecord, WorldState


def _state() -> WorldState:
    # Bob holds three Swords for Alice
    multidata = multidata_from_sanitized({
        "seed_name": "test-seed",
        "slot_info": {1: ("Alice", "GameA", 1, ()), 2: ("Bob", "GameB", 1, ())},
        "locations": {2: {200: (5000, 1, 0), 201: (5000, 1, 0), 202: (5000, 1, 0)}},
        "datapackage": {
            "GameA": {"item_name_to_id": {"Sword": 5000}, "location_name_to_id": {}},
            "GameB": {"item_name_to_id": {}, "location_name_to_id": {"A": 200, "B": 201, "C": 202}},
        },
        "slot_data": {1: {}, 2: {}},
        "games": {1: "GameA", 2: "GameB"},
    })
    return WorldState(multidata)


def _hint(loc: int, found: bool) -> HintRecord:
    return HintRecord(finding_slot=2, receiving_slot=1, item_id=5000, location_id=loc,
                      item_name="Sword", location_name="", found=found)


def test_found_hint_does_not_hide_an_unhinted_copy() -> None:
    state = _state()
    state.apply_slot_checks(2, [200], replace=True)
    state.hints = [_hint(200, found=True), _hint(201, found=False)]

    assert state.hintable_items_for(1) == ["Sword"]


def test_all_copies_hinted_leaves_nothing() -> None:
    state = _state()
    state.hints = [_hint(200, False), _hint(201, False), _hint(202, False)]

    assert state.hintable_items_for(1) == []
