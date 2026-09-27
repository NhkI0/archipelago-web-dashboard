"""Check bursts must not drop a /ws/live subscriber."""

from __future__ import annotations

import asyncio

from server.state import coalesce_events, drain_queue
from server.tests.test_session_live_checks import _fixture_state


def test_burst_of_checks_keeps_subscriber_and_every_check() -> None:
    state = _fixture_state()
    q = state.subscribe()
    # Mirrors apply_slot_checks' emits.
    for i in range(q.maxsize):
        state._emit({"type": "check", "checks": [{"n": i}]})
        state._emit({"type": "room_update", "snapshot": state.snapshot()})

    assert q in state._subscribers
    events = drain_queue(q)
    checks = [e["checks"][0]["n"] for e in events if e["type"] == "check"]
    assert checks[-1] == q.maxsize - 1
    assert events[-1]["type"] == "room_update"


def test_hopeless_backlog_resyncs_with_snapshot() -> None:
    state = _fixture_state()
    q = state.subscribe()
    for i in range(q.maxsize + 1):
        state._emit({"type": "check", "checks": [{"n": i}]})

    assert q in state._subscribers
    assert drain_queue(q)[0]["type"] == "snapshot"


def test_coalesce_keeps_only_last_snapshot_in_place() -> None:
    a = {"type": "room_update", "snapshot": 1}
    c1 = {"type": "check"}
    b = {"type": "hints_replaced", "snapshot": 2}
    c2 = {"type": "check"}
    assert coalesce_events([a, c1, b, c2]) == [c1, b, c2]


def test_drain_queue_empties_without_blocking() -> None:
    q: asyncio.Queue = asyncio.Queue()
    q.put_nowait(1)
    q.put_nowait(2)
    assert drain_queue(q) == [1, 2]
    assert q.empty()
