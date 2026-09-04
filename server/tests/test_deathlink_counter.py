"""DeathLinkCounter: persistence + the dedup guard against double-counting
a death when two DeathLink sessions get the same Bounce broadcast."""

from __future__ import annotations

import json

from server.deathlink import DeathLinkCounter


def test_record_increments_and_persists(tmp_path) -> None:
    path = tmp_path / "deaths.json"
    counter = DeathLinkCounter(path)

    assert counter.record("Alice", event_time=1) is True
    assert counter.record("Bob", event_time=1) is True
    assert counter.counts == {"Alice": 1, "Bob": 1}
    assert json.loads(path.read_text()) == {"Alice": 1, "Bob": 1}


def test_record_dedupes_the_same_event_delivered_twice(tmp_path) -> None:
    counter = DeathLinkCounter(tmp_path / "deaths.json")

    # Same (source, time) - two sessions receiving the same broadcast.
    assert counter.record("Alice", event_time=100) is True
    assert counter.record("Alice", event_time=100) is False
    assert counter.counts == {"Alice": 1}


def test_record_counts_distinct_events_for_the_same_source(tmp_path) -> None:
    counter = DeathLinkCounter(tmp_path / "deaths.json")

    counter.record("Alice", event_time=100)
    counter.record("Alice", event_time=200)

    assert counter.counts == {"Alice": 2}


def test_rehydrates_existing_counts_from_disk(tmp_path) -> None:
    path = tmp_path / "deaths.json"
    path.write_text(json.dumps({"Alice": 3}))

    counter = DeathLinkCounter(path)

    assert counter.counts == {"Alice": 3}
    counter.record("Alice", event_time=1)
    assert counter.counts == {"Alice": 4}


def test_active_sessions_tracks_open_and_close() -> None:
    counter = DeathLinkCounter.__new__(DeathLinkCounter)  # avoid touching disk
    counter.active_sessions = 0

    assert counter.is_active is False
    counter.note_session_open()
    counter.note_session_open()
    assert counter.is_active is True
    assert counter.active_sessions == 2
    counter.note_session_close()
    assert counter.is_active is True
    counter.note_session_close()
    assert counter.is_active is False
    # Never goes negative on a stray extra close.
    counter.note_session_close()
    assert counter.active_sessions == 0


def test_rows_sorted_by_deaths_descending(tmp_path) -> None:
    counter = DeathLinkCounter(tmp_path / "deaths.json")
    counter.record("Alice", event_time=1)
    counter.record("Bob", event_time=1)
    counter.record("Bob", event_time=2)

    assert counter.rows() == [{"name": "Bob", "deaths": 2}, {"name": "Alice", "deaths": 1}]
