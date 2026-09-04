"""Tests for the self-hosted single-observer Tracker (server/tracker.py):
the observer's own slot works as before, but ItemSend/Retrieved/SetReply now
cover every slot in the room, not just the one the observer is connected as.
_baseline_sweep (the one-shot per-slot seed/refresh) is tested against a fake
websocket, same approach as test_session_live_checks.py's _FakeLoginWs."""

from __future__ import annotations

import asyncio
import json

from server.multidata import multidata_from_sanitized
from server.state import WorldState
from server.tracker import Tracker, _ObserverClient, _baseline_sweep, pick_deathlink_host


def _fixture_state() -> WorldState:
    multidata = multidata_from_sanitized({
        "seed_name": "test-seed",
        "slot_info": {1: ("Alice", "GameA", 1, ()), 2: ("Bob", "GameB", 1, ())},
        "locations": {
            1: {100: (5000, 2, 0), 101: (5001, 2, 0)},
            2: {200: (6000, 1, 0)},
        },
        "datapackage": {
            "GameA": {"item_name_to_id": {"Sword": 5000, "Shield": 5001},
                      "location_name_to_id": {"Chest": 100, "Box": 101}},
            "GameB": {"item_name_to_id": {"Potion": 6000}, "location_name_to_id": {"Jar": 200}},
        },
        "slot_data": {1: {}, 2: {}},
        "games": {1: "GameA", 2: "GameB"},
    })
    return WorldState(multidata)


def _observer(state: WorldState) -> _ObserverClient:
    return _ObserverClient(state, "ws://fake", slot_num=1, slot_name="Alice", game="GameA", password="")


def test_dispatch_itemsend_marks_other_slots_check() -> None:
    state = _fixture_state()
    observer = _observer(state)
    packet = {"cmd": "PrintJSON", "type": "ItemSend", "data": [],
              "item": {"player": 2, "item": 6000, "location": 200, "flags": 0}}

    asyncio.run(observer._dispatch(packet))

    assert state.slots[2].checked == {200}


def test_dispatch_retrieved_updates_other_slots_hints_and_status() -> None:
    state = _fixture_state()
    observer = _observer(state)
    packet = {
        "cmd": "Retrieved",
        "keys": {
            "_read_hints_0_2": [[1, 2, 200, 6000, False, "Entrance", 0, 0]],
            "_read_client_status_0_2": 30,
        },
    }

    asyncio.run(observer._dispatch(packet))

    assert len(state.hints) == 1
    assert (state.hints[0].finding_slot, state.hints[0].receiving_slot) == (2, 1)
    assert state.slots[2].goal_completed is True


def test_dispatch_setreply_updates_other_slot_status() -> None:
    state = _fixture_state()
    observer = _observer(state)
    packet = {"cmd": "SetReply", "key": "_read_client_status_0_2", "value": 30}

    asyncio.run(observer._dispatch(packet))

    assert state.slots[2].goal_completed is True


def test_dispatch_connected_seeds_own_slot_and_subscribes_every_slot() -> None:
    state = _fixture_state()
    observer = _observer(state)

    sent: list[str] = []

    class _FakeWs:
        async def send(self, payload: str) -> None:
            sent.append(payload)

    observer._ws = _FakeWs()
    packet = {"cmd": "Connected", "checked_locations": [100], "hint_cost": 10}

    asyncio.run(observer._dispatch(packet))

    assert state.slots[1].checked == {100}
    assert state.hint_cost == 10
    # Both Get and SetNotify cover every slot's hint/status keys, not just ours.
    assert len(sent) == 2
    for frame in sent:
        [msg] = json.loads(frame)
        assert set(msg["keys"]) == {
            "_read_hints_0_1", "_read_client_status_0_1",
            "_read_hints_0_2", "_read_client_status_0_2",
        }


def test_dispatch_roomupdate_updates_own_slot_incrementally() -> None:
    state = _fixture_state()
    observer = _observer(state)
    packet = {"cmd": "RoomUpdate", "checked_locations": [100], "hint_points": 7}

    asyncio.run(observer._dispatch(packet))

    assert state.slots[1].checked == {100}
    assert state.slots[1].hint_points == 7


class _FakeBaselineWs:
    """Stand-in for the websocket returned by websockets.connect() during a
    baseline fetch: two recv()s, RoomInfo then Connected, per slot."""

    def __init__(self, checked_locations: list[int]):
        self._frames = ["<roominfo>", json.dumps([{"cmd": "Connected", "checked_locations": checked_locations}])]

    async def recv(self) -> str:
        return self._frames.pop(0)

    async def send(self, _payload: str) -> None:
        pass

    async def __aenter__(self) -> "_FakeBaselineWs":
        return self

    async def __aexit__(self, *exc) -> None:
        pass


def test_baseline_sweep_seeds_multiple_slots(monkeypatch) -> None:
    state = _fixture_state()
    # websockets.connect() is called once per slot, in state.slots order (1, 2).
    responses = [[100], [200]]

    def fake_connect(_uri: str, **_kwargs):
        return _FakeBaselineWs(responses.pop(0))

    monkeypatch.setattr("server.tracker.websockets.connect", fake_connect)

    asyncio.run(_baseline_sweep(state, "ws://fake", ""))

    assert state.slots[1].checked == {100}
    assert state.slots[2].checked == {200}


def test_pick_deathlink_host_no_preference() -> None:
    state = _fixture_state()
    state.multidata.slot_data[2]["death_link"] = True
    host = pick_deathlink_host(state)
    assert host is not None and host.slot == 2


def test_pick_deathlink_host_first_enabled_wins_regardless_of_name() -> None:
    state = _fixture_state()  # slot 1 is named "Alice", not the old preferred "dopamine"
    state.multidata.slot_data[2]["death_link"] = True
    host = pick_deathlink_host(state)
    assert host is not None and host.name == "Bob"


def test_pick_deathlink_host_none_when_nobody_enabled() -> None:
    state = _fixture_state()
    assert pick_deathlink_host(state) is None


def _tracker(state: WorldState, **kwargs) -> Tracker:
    return Tracker(state, host="fake", port=1, **kwargs)


def test_pick_default_slot_uses_configured_name() -> None:
    state = _fixture_state()
    tracker = _tracker(state, default_slot="Bob")
    assert tracker._pick_default_slot().name == "Bob"


def test_pick_default_slot_falls_back_to_first_when_name_invalid() -> None:
    state = _fixture_state()
    tracker = _tracker(state, default_slot="Nobody")
    assert tracker._pick_default_slot().name == "Alice"


def test_pick_default_slot_goaled_without_deathlink_does_not_win() -> None:
    # A goaled slot with no DeathLink is no longer specially preferred - it
    # falls through to plain "first slot" (tier order: goaled+deathlink ->
    # configured name -> first deathlink -> first slot).
    state = _fixture_state()
    state.slots[2].goal_completed = True
    tracker = _tracker(state)
    assert tracker._pick_default_slot().name == "Alice"


def test_pick_default_slot_goaled_and_deathlink_beats_configured_name() -> None:
    state = _fixture_state()
    state.slots[2].goal_completed = True
    state.multidata.slot_data[2]["death_link"] = True
    tracker = _tracker(state, default_slot="Alice")
    assert tracker._pick_default_slot().name == "Bob"


def test_pick_default_slot_deathlink_only_beats_plain_first() -> None:
    state = _fixture_state()
    state.multidata.slot_data[2]["death_link"] = True  # not goaled, no config
    tracker = _tracker(state)
    assert tracker._pick_default_slot().name == "Bob"


def test_pick_default_slot_plain_first_when_nothing_else_applies() -> None:
    state = _fixture_state()
    tracker = _tracker(state)
    assert tracker._pick_default_slot().name == "Alice"


def test_try_claim_observer_stops_anchor_and_reports_connected() -> None:
    state = _fixture_state()
    tracker = _tracker(state)

    async def run() -> None:
        tracker._start_observer_connection()
        assert tracker._observer is not None
        assert await tracker.try_claim_observer() is True
        assert tracker._observer is None
        assert tracker.connected is True
        assert await tracker.try_claim_observer() is False  # already held

    asyncio.run(run())


def test_release_observer_restarts_the_anchor() -> None:
    state = _fixture_state()
    tracker = _tracker(state)

    async def run() -> None:
        await tracker.try_claim_observer()
        await tracker.release_observer()
        assert tracker._observer is not None
        assert tracker._observer.slot_num == 1  # falls back to first slot
        await tracker._observer.stop()

    asyncio.run(run())


def test_start_observer_connection_merges_deathlink_onto_same_slot(tmp_path) -> None:
    state = _fixture_state()
    state.multidata.slot_data[2]["death_link"] = True  # picked as default slot too
    tracker = _tracker(state, deaths_file=tmp_path / "deaths.json")

    async def run() -> None:
        tracker._start_observer_connection()
        assert tracker._observer is not None
        assert tracker._observer.slot_num == 2
        assert tracker._observer.death_counter is not None
        tracker._start_deathlink_if_needed()  # no-op: already merged
        assert tracker._death_client is None
        await tracker._observer.stop()

    asyncio.run(run())


def test_start_deathlink_if_needed_starts_standalone_when_claimed(tmp_path) -> None:
    # No anchor exists while a session holds observer duty; DeathLink still
    # needs a standalone connection in that case.
    state = _fixture_state()
    state.multidata.slot_data[2]["death_link"] = True
    tracker = _tracker(state, deaths_file=tmp_path / "deaths.json")

    async def run() -> None:
        tracker._observer_claimed = True
        tracker._start_deathlink_if_needed()
        assert tracker._death_client is not None
        assert tracker._death_client.slot_num == 2
        await tracker._death_client.stop()

    asyncio.run(run())


def test_configured_slot_without_deathlink_opts_out_of_standalone(tmp_path) -> None:
    # The host explicitly picked Alice (no DeathLink) as default_slot - that's
    # respected as an opt-out, not silently worked around with an extra connection.
    state = _fixture_state()
    state.multidata.slot_data[2]["death_link"] = True
    tracker = _tracker(state, default_slot="Alice", deaths_file=tmp_path / "deaths.json")

    async def run() -> None:
        tracker._start_observer_connection()
        assert tracker._observer is not None
        assert tracker._observer.slot_num == 1
        assert tracker._observer.death_counter is None
        tracker._start_deathlink_if_needed()
        assert tracker._death_client is None
        await tracker._observer.stop()

    asyncio.run(run())


def test_claim_starts_standalone_deathlink_when_anchor_was_merged(tmp_path) -> None:
    state = _fixture_state()
    state.multidata.slot_data[2]["death_link"] = True
    tracker = _tracker(state, deaths_file=tmp_path / "deaths.json")

    async def run() -> None:
        tracker._start_observer_connection()
        assert tracker._observer.death_counter is not None  # merged onto Bob
        assert await tracker.try_claim_observer() is True
        assert tracker._observer is None
        assert tracker._death_client is not None  # death tracking survives the handoff
        assert tracker._death_client.slot_num == 2
        await tracker._death_client.stop()

    asyncio.run(run())


def test_release_merges_back_and_stops_the_standalone(tmp_path) -> None:
    state = _fixture_state()
    state.multidata.slot_data[2]["death_link"] = True
    tracker = _tracker(state, deaths_file=tmp_path / "deaths.json")

    async def run() -> None:
        tracker._start_observer_connection()
        await tracker.try_claim_observer()
        standalone = tracker._death_client
        assert standalone is not None

        await tracker.release_observer()

        assert tracker._observer is not None
        assert tracker._observer.death_counter is not None  # re-merged onto Bob
        assert tracker._death_client is None  # standalone was stopped, no duplicate
        await tracker._observer.stop()

    asyncio.run(run())
