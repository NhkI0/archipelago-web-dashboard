"""Tests for the archipelago.gg room_url parsing/fetching helpers in config.py."""

from __future__ import annotations

import pytest

from server.config import _fetch_room_status, _parse_room_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://archipelago.gg/room/AbCdEfGhIjKl", ("archipelago.gg", "AbCdEfGhIjKl")),
        ("http://archipelago.gg/room/AbC-def_123", ("archipelago.gg", "AbC-def_123")),
        # Scheme-less paste still works; defaults to https.
        ("archipelago.gg/room/AbCdEfGhIjKl", ("archipelago.gg", "AbCdEfGhIjKl")),
        # Trailing slash / whitespace tolerated.
        ("  https://archipelago.gg/room/AbCdEfGhIjKl/  ", ("archipelago.gg", "AbCdEfGhIjKl")),
    ],
)
def test_parse_room_url_accepts_valid_urls(url: str, expected: tuple[str, str]) -> None:
    assert _parse_room_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "not a url at all",
        "https://archipelago.gg/",  # missing /room/<id>
        "https://archipelago.gg/room/",  # missing id
        "https://archipelago.gg/tracker/AbCdEfGhIjKl",  # wrong path shape
        "ftp://archipelago.gg/room/AbCdEfGhIjKl",  # wrong scheme
        "https://archipelago.gg/room/has spaces",  # invalid token chars
    ],
)
def test_parse_room_url_rejects_malformed_urls(url: str) -> None:
    with pytest.raises(RuntimeError, match="room_url"):
        _parse_room_url(url)


def test_fetch_room_status_raises_actionable_error_when_unreachable() -> None:
    # Port 1 is a well-known reserved port nothing listens on; this should
    # fail fast rather than hang, and surface a clear message.
    with pytest.raises(RuntimeError, match="could not reach"):
        _fetch_room_status("127.0.0.1:1", "fake-room")
