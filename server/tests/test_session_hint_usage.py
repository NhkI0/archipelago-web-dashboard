"""SessionManager.send_hint should record a spend in HintUsageStore only when
the server-reported hint_points balance actually drops - never from guessing
at reply text, and never when no HintUsageStore is configured (self-hosted /
non-polling rooms don't need this at all)."""

from __future__ import annotations

import asyncio
import pathlib

import pytest

from server.hint_usage import HintUsageStore
from server.multidata import multidata_from_sanitized
from server.session import Session, SessionManager


def _fixture_multidata():
    return multidata_from_sanitized({
        "seed_name": "test-seed",
        "slot_info": {1: ("Alice", "GameA", 1, ())},
        "locations": {1: {}},
        "datapackage": {},
        "slot_data": {1: {}},
        "games": {1: "GameA"},
    })


class _FakeWs:
    """Stands in for the real websocket."""

    _on_send = None

    async def send(self, _payload: str) -> None:
        if self._on_send is not None:
            self._on_send()


def _manager_with_session(
    hint_points_before: int, drop_to: int | None, hint_usage: HintUsageStore | None = None,
) -> tuple[SessionManager, Session]:
    """`drop_to` simulates whatever server-side effect a real `!hint` command
    would eventually cause - `None` means the balance doesn't change."""
    mgr = SessionManager(multidata=_fixture_multidata(), hint_usage=hint_usage)
    sess = Session(sid="sid1", slot="Alice", ws=_FakeWs(), hint_points=hint_points_before)
    if drop_to is not None:
        sess.ws._on_send = lambda: setattr(sess, "hint_points", drop_to)
    mgr._sessions["sid1"] = sess
    return mgr, sess


def _run_send_hint(mgr: SessionManager, monkeypatch: pytest.MonkeyPatch) -> None:
    # The real drain loop waits up to 4s for extra PrintJSON replies; speed it
    # up the same way test_build_app.py does for its idle-tick test - capture
    # the real wait_for first so the replacement doesn't recurse into itself.
    real_wait_for = asyncio.wait_for

    async def fast_wait_for(aw, timeout):
        return await real_wait_for(aw, timeout=0.01)

    monkeypatch.setattr("server.session.asyncio.wait_for", fast_wait_for)
    asyncio.run(mgr.send_hint("sid1", "item", "Sword"))


def test_records_spend_when_hint_points_drops(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    hint_usage = HintUsageStore(tmp_path / "hints_used.json")
    mgr, _sess = _manager_with_session(hint_points_before=10, drop_to=9, hint_usage=hint_usage)
    _run_send_hint(mgr, monkeypatch)
    assert hint_usage.used_count(1) == 1


def test_does_not_record_when_hint_points_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    hint_usage = HintUsageStore(tmp_path / "hints_used.json")
    mgr, _sess = _manager_with_session(hint_points_before=10, drop_to=None, hint_usage=hint_usage)
    _run_send_hint(mgr, monkeypatch)
    assert hint_usage.used_count(1) == 0


def test_noop_without_a_hint_usage_store(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr, _sess = _manager_with_session(hint_points_before=10, drop_to=9, hint_usage=None)
    _run_send_hint(mgr, monkeypatch)  # must not raise with hint_usage=None
