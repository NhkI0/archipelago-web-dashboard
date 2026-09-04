"""SessionManager hands Tracker's observer duty to a real login connection:
first login claims it, a second doesn't re-claim, losing the observer session
reassigns duty to another login or releases it back to Tracker.

Assertions run inside the async test bodies: asyncio.run()'s shutdown cancels
the still-open fake sockets, whose `finally` would reassign duty early."""

from __future__ import annotations

import asyncio
import json

from server.multidata import multidata_from_sanitized
from server.session import SessionManager
from server.state import WorldState


def _fixture_state() -> WorldState:
    multidata = multidata_from_sanitized({
        "seed_name": "test-seed",
        "slot_info": {1: ("Alice", "GameA", 1, ()), 2: ("Bob", "GameB", 1, ())},
        "locations": {1: {}, 2: {}},
        "datapackage": {},
        "slot_data": {1: {}, 2: {}},
        "games": {1: "GameA", 2: "GameB"},
    })
    return WorldState(multidata)


class _FakeTracker:
    """Stub for server.tracker.Tracker exposing only the two methods
    SessionManager actually calls, so these tests never touch a real
    websocket-based Tracker."""

    def __init__(self) -> None:
        self.claimed = False
        self.release_calls = 0

    async def try_claim_observer(self) -> bool:
        if self.claimed:
            return False
        self.claimed = True
        return True

    async def release_observer(self) -> None:
        self.claimed = False
        self.release_calls += 1


class _FakeLoginWs:
    """Stand-in for the websocket returned by websockets.connect() in login();
    records every frame sent so tests can check for the broad subscription."""

    def __init__(self, slot: str):
        self._frames = ["<roominfo>", json.dumps([{"cmd": "Connected", "hint_points": 0}])]
        self.sent: list[dict] = []
        self.slot = slot

    async def recv(self) -> str:
        return self._frames.pop(0)

    async def send(self, payload: str) -> None:
        [msg] = json.loads(payload)
        self.sent.append(msg)

    async def close(self) -> None:
        pass

    def __aiter__(self) -> "_FakeLoginWs":
        return self

    async def __anext__(self) -> str:
        # Never yields another frame or ends - simulates a still-open socket.
        await asyncio.Future()
        raise AssertionError("unreachable")


def _fake_connect_returning(ws_or_queue):
    """Builds an async replacement for websockets.connect() returning either a
    single fake ws every time, or popping one off a queue per call."""
    async def fake_connect(_uri: str, **_kwargs):
        if isinstance(ws_or_queue, list):
            return ws_or_queue.pop(0)
        return ws_or_queue
    return fake_connect


def test_first_login_claims_observer_and_subscribes(monkeypatch) -> None:
    state = _fixture_state()
    tracker = _FakeTracker()
    mgr = SessionManager(multidata=state.multidata, world=state, tracker=tracker)
    ws = _FakeLoginWs("Alice")
    monkeypatch.setattr("server.session.websockets.connect", _fake_connect_returning(ws))

    async def do() -> None:
        await mgr.login("Alice")
        await asyncio.sleep(0)

        assert tracker.claimed is True
        get_calls = [m for m in ws.sent if m["cmd"] == "Get"]
        setnotify_calls = [m for m in ws.sent if m["cmd"] == "SetNotify"]
        assert len(get_calls) == 1 and len(setnotify_calls) == 1
        assert set(get_calls[0]["keys"]) == {
            "_read_hints_0_1", "_read_client_status_0_1",
            "_read_hints_0_2", "_read_client_status_0_2",
        }

    asyncio.run(do())


def test_second_login_does_not_reclaim(monkeypatch) -> None:
    state = _fixture_state()
    tracker = _FakeTracker()
    mgr = SessionManager(multidata=state.multidata, world=state, tracker=tracker)
    ws_a, ws_b = _FakeLoginWs("Alice"), _FakeLoginWs("Bob")
    monkeypatch.setattr("server.session.websockets.connect", _fake_connect_returning([ws_a, ws_b]))

    async def do() -> None:
        await mgr.login("Alice")
        await asyncio.sleep(0)
        await mgr.login("Bob")
        await asyncio.sleep(0)

        assert not any(m["cmd"] == "Get" for m in ws_b.sent)

    asyncio.run(do())


def test_logout_of_observer_promotes_remaining_session(monkeypatch) -> None:
    state = _fixture_state()
    tracker = _FakeTracker()
    mgr = SessionManager(multidata=state.multidata, world=state, tracker=tracker)
    ws_a, ws_b = _FakeLoginWs("Alice"), _FakeLoginWs("Bob")
    monkeypatch.setattr("server.session.websockets.connect", _fake_connect_returning([ws_a, ws_b]))

    async def do() -> None:
        sess_a = await mgr.login("Alice")
        await asyncio.sleep(0)
        await mgr.login("Bob")
        await asyncio.sleep(0)
        await mgr.logout(sess_a.sid)

        assert tracker.release_calls == 0  # Bob took over, Tracker was never asked
        assert any(m["cmd"] == "Get" for m in ws_b.sent)

    asyncio.run(do())


def test_logout_of_last_session_releases_to_tracker(monkeypatch) -> None:
    state = _fixture_state()
    tracker = _FakeTracker()
    mgr = SessionManager(multidata=state.multidata, world=state, tracker=tracker)
    ws = _FakeLoginWs("Alice")
    monkeypatch.setattr("server.session.websockets.connect", _fake_connect_returning(ws))

    async def do() -> None:
        sess = await mgr.login("Alice")
        await asyncio.sleep(0)
        await mgr.logout(sess.sid)

        assert tracker.release_calls == 1
        assert tracker.claimed is False

    asyncio.run(do())


def test_login_without_a_tracker_does_not_claim(monkeypatch) -> None:
    state = _fixture_state()
    mgr = SessionManager(multidata=state.multidata, world=state, tracker=None)
    ws = _FakeLoginWs("Alice")
    monkeypatch.setattr("server.session.websockets.connect", _fake_connect_returning(ws))

    async def do() -> None:
        await mgr.login("Alice")  # must not raise with tracker=None
        await asyncio.sleep(0)

        assert not any(m["cmd"] == "Get" for m in ws.sent)

    asyncio.run(do())
