"""DeathLink for archipelago.gg-polled rooms is caught through SessionManager:
a login as a DeathLink-enabled slot tags its Connect with "DeathLink" and
feeds Bounces into the shared DeathLinkCounter (see deathlink.py/session.py)."""

from __future__ import annotations

import asyncio
import json

import pytest

from server.deathlink import DeathLinkCounter
from server.multidata import multidata_from_sanitized
from server.session import Session, SessionManager


def _fixture_multidata(death_link_slot: int | None = 1):
    slot_data = {1: {}, 2: {}}
    if death_link_slot is not None:
        slot_data[death_link_slot] = {"death_link": True}
    return multidata_from_sanitized({
        "seed_name": "test-seed",
        "slot_info": {1: ("Alice", "GameA", 1, ()), 2: ("Bob", "GameB", 1, ())},
        "locations": {1: {}, 2: {}},
        "datapackage": {
            "GameA": {"item_name_to_id": {}, "location_name_to_id": {}},
            "GameB": {"item_name_to_id": {}, "location_name_to_id": {}},
        },
        "slot_data": slot_data,
        "games": {1: "GameA", 2: "GameB"},
    })


class _FakeWsStream:
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
    def __init__(self, recv_frames: list[str]):
        self._frames = list(recv_frames)
        self.sent: list[dict] = []

    async def recv(self) -> str:
        return self._frames.pop(0)

    async def send(self, payload: str) -> None:
        self.sent.extend(json.loads(payload))

    async def close(self) -> None:
        pass

    def __aiter__(self) -> "_FakeLoginWs":
        return self

    async def __anext__(self) -> str:
        raise StopAsyncIteration


def _bounced_frame(source: str, event_time: object = None) -> str:
    return json.dumps([{
        "cmd": "Bounced", "tags": ["DeathLink"],
        "data": {"source": source, "time": event_time},
    }])


def test_pump_records_deathlink_bounce_when_session_is_tagged(tmp_path) -> None:
    counter = DeathLinkCounter(tmp_path / "deaths.json")
    mgr = SessionManager(deathlink=counter)
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([_bounced_frame("Alice", 1)]),
                   deathlink=True)

    asyncio.run(mgr._pump(sess))

    assert counter.rows() == [{"name": "Alice", "deaths": 1}]


def test_pump_ignores_deathlink_bounce_when_session_is_not_tagged(tmp_path) -> None:
    counter = DeathLinkCounter(tmp_path / "deaths.json")
    mgr = SessionManager(deathlink=counter)
    # sess.deathlink is a defensive backstop; AP wouldn't send this without the tag.
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([_bounced_frame("Alice", 1)]),
                   deathlink=False)

    asyncio.run(mgr._pump(sess))

    assert counter.rows() == []


def test_pump_ignores_deathlink_bounce_without_a_counter() -> None:
    mgr = SessionManager(deathlink=None)
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([_bounced_frame("Alice", 1)]),
                   deathlink=True)

    asyncio.run(mgr._pump(sess))  # must not raise with deathlink=None


def test_session_close_decrements_active_sessions_exactly_once(tmp_path) -> None:
    """_pump()'s finally block and an explicit logout() both call the same
    idempotent helper - only the one that runs first should decrement."""
    counter = DeathLinkCounter(tmp_path / "deaths.json")
    mgr = SessionManager(deathlink=counter)
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWsStream([]), deathlink=True)
    counter.note_session_open()
    assert counter.is_active is True

    asyncio.run(mgr._pump(sess))  # no frames -> closes immediately
    assert counter.is_active is False
    assert sess.deathlink is False

    # logout() afterwards must not decrement a second time.
    mgr._sessions[sess.sid] = sess
    asyncio.run(mgr.logout(sess.sid))
    assert counter.active_sessions == 0


def test_login_tags_deathlink_connect_for_a_deathlink_enabled_slot(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    multidata = _fixture_multidata(death_link_slot=1)
    counter = DeathLinkCounter(tmp_path / "deaths.json")
    mgr = SessionManager(multidata=multidata, deathlink=counter)
    connected_frame = json.dumps([{"cmd": "Connected", "hint_points": 0, "checked_locations": []}])
    fake_ws = _FakeLoginWs(["<roominfo>", connected_frame])

    async def fake_connect(_uri: str, **_kwargs) -> _FakeLoginWs:
        return fake_ws

    monkeypatch.setattr("server.session.websockets.connect", fake_connect)

    # Asserted inside the coroutine: asyncio.run()'s shutdown cancels the
    # spawned _pump task, which would otherwise flip sess.deathlink back off.
    async def do_login() -> tuple[Session, list, bool, int]:
        sess = await mgr.login("Alice")
        return sess, fake_ws.sent[0]["tags"], sess.deathlink, counter.active_sessions

    sess, tags, deathlink_flag, active = asyncio.run(do_login())

    assert "DeathLink" in tags
    assert deathlink_flag is True
    assert active == 1


def test_login_does_not_tag_deathlink_for_a_non_deathlink_slot(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    multidata = _fixture_multidata(death_link_slot=1)  # Bob (slot 2) has no DeathLink
    counter = DeathLinkCounter(tmp_path / "deaths.json")
    mgr = SessionManager(multidata=multidata, deathlink=counter)
    connected_frame = json.dumps([{"cmd": "Connected", "hint_points": 0, "checked_locations": []}])
    fake_ws = _FakeLoginWs(["<roominfo>", connected_frame])

    async def fake_connect(_uri: str, **_kwargs) -> _FakeLoginWs:
        return fake_ws

    monkeypatch.setattr("server.session.websockets.connect", fake_connect)

    async def do_login() -> tuple[list, bool, int]:
        sess = await mgr.login("Bob")
        return fake_ws.sent[0]["tags"], sess.deathlink, counter.active_sessions

    tags, deathlink_flag, active = asyncio.run(do_login())

    assert "DeathLink" not in tags
    assert deathlink_flag is False
    assert active == 0


def test_login_does_not_tag_deathlink_without_a_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Self-hosted rooms never pass `deathlink=` (Tracker already has its own
    always-on DeathLinkClient) - SessionManager must stay inert here."""
    multidata = _fixture_multidata(death_link_slot=1)
    mgr = SessionManager(multidata=multidata, deathlink=None)
    connected_frame = json.dumps([{"cmd": "Connected", "hint_points": 0, "checked_locations": []}])
    fake_ws = _FakeLoginWs(["<roominfo>", connected_frame])

    async def fake_connect(_uri: str, **_kwargs) -> _FakeLoginWs:
        return fake_ws

    monkeypatch.setattr("server.session.websockets.connect", fake_connect)

    async def do_login() -> tuple[list, bool]:
        sess = await mgr.login("Alice")
        return fake_ws.sent[0]["tags"], sess.deathlink

    tags, deathlink_flag = asyncio.run(do_login())

    assert "DeathLink" not in tags
    assert deathlink_flag is False
