"""Tests for RoomPoller: mapping archipelago.gg's public JSON tracker API onto
WorldState, and the room_status/tracker gatekeeper logic - without ever touching
a real HTTP client or websocket (see server/room_poller.py's http_get injection
point, and _poll_once's split from _run, both added specifically for this)."""

from __future__ import annotations

import asyncio
import pathlib

from server.deathlink import DeathLinkCounter
from server.hint_usage import HintUsageStore
from server.multidata import multidata_from_sanitized
from server.room_poller import RoomPoller
from server.state import WorldState


def _fixture_state(death_link_slot: int | None = None) -> WorldState:
    slot_data = {1: {}, 2: {}}
    if death_link_slot is not None:
        slot_data[death_link_slot] = {"death_link": True}
    data = {
        "seed_name": "test-seed",
        "slot_info": {
            1: ("Alice", "GameA", 1, ()),
            2: ("Bob", "GameB", 1, ()),
        },
        # locations is keyed by the FINDING slot: Alice (1) has two locations
        # that send items to Bob (2); Bob (2) has one location sending to Alice (1).
        "locations": {
            1: {100: (5000, 2, 0), 101: (5001, 2, 0)},
            2: {200: (6000, 1, 0)},
        },
        "datapackage": {
            "GameA": {"item_name_to_id": {"Sword": 5000, "Shield": 5001}, "location_name_to_id": {"Chest": 100, "Box": 101}},
            "GameB": {"item_name_to_id": {"Potion": 6000}, "location_name_to_id": {"Jar": 200}},
        },
        "slot_data": slot_data,
        "games": {1: "GameA", 2: "GameB"},
    }
    multidata = multidata_from_sanitized(data)
    return WorldState(multidata)


def _poller(state: WorldState, hint_usage: HintUsageStore | None = None) -> RoomPoller:
    poller = RoomPoller(
        state, hostname="archipelago.gg", room_id="fake-room", hint_usage=hint_usage,
    )
    # Skip the real-websocket RoomInfo peek entirely for these tests -
    # hint_cost/location_check_points are set directly instead.
    poller._last_port = 12345
    return poller


def test_apply_maps_checks_status_and_hints() -> None:
    state = _fixture_state()
    poller = _poller(state)

    payload = {
        "player_checks_done": [
            {"team": 0, "player": 1, "locations": [100]},
            {"team": 0, "player": 2, "locations": []},
        ],
        "player_status": [
            {"team": 0, "player": 1, "status": 30},  # CLIENT_GOAL
        ],
        "hints": [
            {"team": 0, "player": 2, "hints": [[1, 2, 200, 6000, False, "Entrance", 0, 0]]},
        ],
    }
    poller._apply(payload)

    assert state.slots[1].checked == {100}
    assert state.slots[1].goal_completed is True
    assert state.slots[2].checked == set()
    assert len(state.hints) == 1
    hint = state.hints[0]
    assert (hint.finding_slot, hint.receiving_slot, hint.location_id, hint.item_id) == (2, 1, 200, 6000)


def test_apply_ignores_other_teams() -> None:
    state = _fixture_state()
    poller = _poller(state)
    poller._apply({
        "player_checks_done": [{"team": 1, "player": 1, "locations": [100]}],
        "player_status": [],
        "hints": [],
    })
    assert state.slots[1].checked == set()


def test_hint_points_estimate_uses_local_usage_count() -> None:
    state = _fixture_state()
    hint_usage = HintUsageStore(pathlib.Path("/nonexistent/does-not-matter.json"))
    poller = _poller(state, hint_usage=hint_usage)
    poller.hint_cost_pct = 10  # AP's get_hint_cost: max(1, int(0.10 * total_locations))
    poller._location_check_points = 1

    # Alice (slot 1) has 2 total locations -> hint cost = max(1, int(0.1*2)) = 1.
    hint_usage._counts[1] = 3  # pretend 3 hints already paid for through this dashboard

    poller._apply({
        "player_checks_done": [{"team": 0, "player": 1, "locations": [100, 101]}],
        "player_status": [],
        "hints": [],
    })

    # 1 point/check * 2 checks - 1 point/hint * 3 hints used = -1
    assert state.slots[1].hint_points == -1


def test_hint_points_not_touched_before_hint_cost_known() -> None:
    state = _fixture_state()
    poller = _poller(state)
    before = state.slots[1].hint_points
    poller._apply({
        "player_checks_done": [{"team": 0, "player": 1, "locations": [100]}],
        "player_status": [],
        "hints": [],
    })
    assert state.slots[1].hint_points == before


def test_poll_once_skips_tracker_fetch_when_activity_unchanged() -> None:
    state = _fixture_state()
    calls: list[str] = []

    async def fake_get(url: str) -> dict:
        calls.append(url)
        if "room_status" in url:
            return {"tracker": "tok", "last_port": 12345, "last_activity": "same"}
        return {"player_checks_done": [], "player_status": [], "hints": []}

    poller = RoomPoller(state, hostname="archipelago.gg", room_id="fake-room", http_get=fake_get)
    poller._last_port = 12345  # avoid the real-websocket RoomInfo peek

    asyncio.run(poller._poll_once())
    assert any("api/tracker" in c for c in calls)

    calls.clear()
    asyncio.run(poller._poll_once())  # last_activity unchanged -> gatekeeper should skip
    assert not any("api/tracker" in c for c in calls)
    assert any("room_status" in c for c in calls)


def test_poll_once_refetches_tracker_when_activity_changes() -> None:
    state = _fixture_state()
    activity = ["first", "second"]

    async def fake_get(url: str) -> dict:
        if "room_status" in url:
            return {"tracker": "tok", "last_port": 12345, "last_activity": activity.pop(0)}
        return {"player_checks_done": [{"team": 0, "player": 1, "locations": [100]}], "player_status": [], "hints": []}

    poller = RoomPoller(state, hostname="archipelago.gg", room_id="fake-room", http_get=fake_get)
    poller._last_port = 12345

    asyncio.run(poller._poll_once())
    asyncio.run(poller._poll_once())
    assert state.slots[1].checked == {100}


def test_death_rows_and_connected_reflect_shared_counter(tmp_path: pathlib.Path) -> None:
    """RoomPoller just reads the shared DeathLinkCounter now (session.py owns it)."""
    state = _fixture_state(death_link_slot=1)
    poller = _poller(state)
    assert poller.death_rows() == []
    assert poller.death_client_connected() is False

    counter = DeathLinkCounter(tmp_path / "deaths.json")
    poller.deathlink = counter
    assert poller.death_rows() == []
    assert poller.death_client_connected() is False

    counter.note_session_open()
    assert poller.death_client_connected() is True

    # Distinct event_time -> two genuinely separate deaths.
    counter.record("Alice", event_time=1)
    counter.record("Alice", event_time=2)
    assert poller.death_rows() == [{"name": "Alice", "deaths": 2}]

    counter.note_session_close()
    assert poller.death_client_connected() is False
    # Rows persist after logout; only "connected" tracks live presence.
    assert poller.death_rows() == [{"name": "Alice", "deaths": 2}]
