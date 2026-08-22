"""Tests for the child-process wrapper around the untrusted parse.

Runs against whatever _build_command picks for the current platform: on a systemd-less dev/CI
box (Windows, most CI images) that's the unsandboxed subprocess fallback, which is exactly
what these tests are meant to exercise. The plumbing (argv construction, stdin/stdout wiring,
error propagation) works the same regardless of which path executes it. The systemd-run path
itself can only be verified on a real Linux host; see server/sandbox.py.
"""

from __future__ import annotations

import pathlib

import pytest

from server.sandbox import SandboxError, run_sandboxed_parse


def test_run_sandboxed_parse_on_real_corpus_file():
    corpus = sorted(pathlib.Path(__file__).resolve().parents[2].glob("multiworld/*.archipelago"))
    assert corpus, "expected sample .archipelago files in core/multiworld/"
    payload = corpus[0].read_bytes()
    sanitized = run_sandboxed_parse(payload)
    assert sanitized["format_version"] == 1
    assert "slot_info" in sanitized


def test_run_sandboxed_parse_rejects_garbage():
    with pytest.raises(SandboxError):
        run_sandboxed_parse(b"not a real multidata file")
