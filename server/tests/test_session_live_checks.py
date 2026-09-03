"""SessionManager should feed a logged-in player's checks, received items,
hints, and goal status into WorldState live instead of waiting on RoomPoller's
poll cycle. Must be a no-op when no WorldState is given (world=None, default)."""

from __future__ import annotations

import asyncio
import json

import pytest

from server.multidata import multidata_from_sanitized
from server.session import Session, SessionManager
from server.state import WorldState


def _fixture_state() -> WorldState:
    multidata = multidata_from_sanitized({
        "seed_name": "test-seed",
        "slot_info": {1: ("Alice", "GameA", 1, ()), 2: ("Bob", "GameB", 1, ())},
        # locations is keyed by the FINDING slot: Alice (1) has two locations
        # sending to herself; Bob (2) has one location sending to Alice (1).
        "locations": {
            1: {100: (5000, 1, 0), 101: (5001, 1, 0)},
            2: {200: (6000, 1, 0)},
        },
        "datapackage": {
            # item_name looks up the RECEIVING slot's game (see WorldState.received_for),
            # so Potion (sent to Alice/GameA by Bob's location) lives in GameA's package.
            "GameA": {"item_name_to_id": {"Sword": 5000, "Shield": 5001, "Potion": 6000},
                      "location_name_to_id": {"Chest": 100, "Box": 101}},
            "GameB": {"item_name_to_id": {}, "location_name_to_id": {"Jar": 200}},
        },
        "slot_data": {1: {}, 2: {}},
        "games": {1: "GameA", 2: "GameB"},
    })
    return WorldState(multidata)


class _FakeWsStream:
    """Async-iterable stand-in for the real websocket, feeding preset raw
    frames to _pump - each frame is a JSON-encoded list of packets, exactly
    like the real AP wire format."""

    def __init__(self, frames: list[str]):
        self._frames = list(frames)

    async def send(self, _payload: str) -> None:
        pass

    def __aiter__(self) -> "_FakeWsStream":
        return self

    async def __anext__(self) -> str:
        if not self._frames:
            raise StopAsyncIteration
        return self._frames.pop(0)


class _FakeLoginWs:
    """Stand-in for the websocket returned by websockets.connect() in login()."""

    def __init__(self, recv_frames: list[str]):
        self._frames = list(recv_frames)

    async def recv(self) -> str:
        return self._frames.pop(0)

    async def send(self, _payload: str) -> None:
        pass

    async def close(self) -> None:
        pass

    def __aiter__(self) -> "_FakeLoginWs":
        return self

    async def __anext__(self) -> str:
        raise StopAsyncIteration


def test_pump_feeds_checked_locations_into_world_live() -> None:
    state = _fixture_state()
    mgr = SessionManager(multidata=state.multidata, world=state)
    frame = json.dumps([{"cmd": "RoomUpdate", "checked_locations": [100]}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))

    assert state.slots[1].checked == {100}


def test_pump_ignores_checked_locations_without_a_world() -> None:
    mgr = SessionManager(multidata=None, world=None)
    frame = json.dumps([{"cmd": "RoomUpdate", "checked_locations": [100]}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))  # must not raise with world=None


def test_pump_updates_hint_points_and_checks_from_the_same_packet() -> None:
    state = _fixture_state()
    mgr = SessionManager(multidata=state.multidata, world=state)
    frame = json.dumps([{"cmd": "RoomUpdate", "checked_locations": [100, 101], "hint_points": 7}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))

    assert state.slots[1].checked == {100, 101}
    assert sess.hint_points == 7


def test_pump_feeds_received_items_into_worlds_sender_slot() -> None:
    state = _fixture_state()
    mgr = SessionManager(multidata=state.multidata, world=state)
    # Alice is logged in; Bob (slot 2) found the location that sends her Potion.
    frame = json.dumps([{"cmd": "ReceivedItems", "index": 0,
                          "items": [{"item": 6000, "location": 200, "player": 2, "flags": 0}]}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))

    assert state.slots[2].checked == {200}
    received = state.received_for(1)
    assert len(received) == 1
    assert received[0]["item_name"] == "Potion"


def test_pump_ignores_received_items_without_a_world() -> None:
    mgr = SessionManager(multidata=None, world=None)
    frame = json.dumps([{"cmd": "ReceivedItems", "index": 0,
                          "items": [{"item": 6000, "location": 200, "player": 2, "flags": 0}]}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))  # must not raise with world=None


def test_pump_feeds_hint_printjson_into_world() -> None:
    state = _fixture_state()
    mgr = SessionManager(multidata=state.multidata, world=state)
    # Bob (2) found the location that hints Alice (1) their Potion.
    frame = json.dumps([{"cmd": "PrintJSON", "type": "Hint", "data": [],
                          "receiving": 1, "item": {"player": 2, "item": 6000, "location": 200},
                          "found": False}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))

    assert len(state.hints) == 1
    assert (state.hints[0].finding_slot, state.hints[0].receiving_slot) == (2, 1)


def test_pump_feeds_goal_printjson_into_world() -> None:
    state = _fixture_state()
    mgr = SessionManager(multidata=state.multidata, world=state)
    frame = json.dumps([{"cmd": "PrintJSON", "type": "Goal", "data": [], "slot": 2}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))

    assert state.slots[2].goal_completed is True


def test_pump_feeds_itemsend_printjson_for_any_slot() -> None:
    state = _fixture_state()
    mgr = SessionManager(multidata=state.multidata, world=state)
    # Alice is logged in, but the check is Bob's (2) - a teammate's check
    # should still go live via ItemSend's room-wide broadcast.
    frame = json.dumps([{"cmd": "PrintJSON", "type": "ItemSend", "data": [],
                          "receiving": 1, "item": {"player": 2, "item": 6000, "location": 200, "flags": 0}}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))

    assert state.slots[2].checked == {200}


def test_pump_ignores_hint_and_goal_printjson_without_a_world() -> None:
    mgr = SessionManager(multidata=None, world=None)
    frame = json.dumps([{"cmd": "PrintJSON", "type": "Goal", "data": [], "slot": 2}])
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([frame]), slot_num=1)

    asyncio.run(mgr._pump(sess))  # must not raise with world=None


def test_login_seeds_initial_checks_into_world(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _fixture_state()
    mgr = SessionManager(multidata=state.multidata, world=state)
    connected_frame = json.dumps([{"cmd": "Connected", "hint_points": 5, "checked_locations": [100]}])
    fake_ws = _FakeLoginWs(["<roominfo>", connected_frame])

    async def fake_connect(_uri: str, **_kwargs) -> _FakeLoginWs:
        return fake_ws

    monkeypatch.setattr("server.session.websockets.connect", fake_connect)

    async def do_login() -> Session:
        sess = await mgr.login("Alice")
        await asyncio.sleep(0)  # let the just-spawned _pump task run once
        return sess

    sess = asyncio.run(do_login())

    assert state.slots[1].checked == {100}
    assert sess.slot_num == 1
    assert sess.hint_points == 5
