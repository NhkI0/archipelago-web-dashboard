"""Sandboxed execution of the untrusted .archipelago parse.

multidata.parse_untrusted() is the only function that unpickles hostile input, and the
allowlisted unpickler (see multidata.py) is meant to be a sufficient chokepoint on its own.
This module is defense in depth on top of that: run the parse in a child process with
OS-level isolation, so a bug in the allowlist (a class nobody anticipated, a stdlib import
path that slips through) still can't reach the network, the filesystem, or more than a
bounded amount of CPU/memory/wall-clock time.

Two execution paths, chosen automatically:

Linux, with systemd-run available: spawn a transient systemd service with PrivateNetwork=yes,
a memory ceiling, a wall-clock ceiling, NoNewPrivileges=yes/ProtectSystem=strict/ProtectHome=yes,
and LimitFSIZE=0 (the worker never needs to write a file). Pass user= to also run as a
dedicated unprivileged system account; set one up on the host before relying on this in
production. This is the only path considered an actual security boundary.

Anywhere else (dev machines, CI, Windows; systemd doesn't exist there): fall back to a plain
subprocess.run of the same worker. This gives process isolation only (a crash or hang can't
take the parent down) and is explicitly not a security boundary. Every call through this
fallback logs a warning so it can never look secure by accident.

Phase 1 is "testable entirely offline" for the parser itself; the actual isolation guarantees
of the systemd-run path can only be verified on the target VPS (see the hosted-dashboard-plan
memory's "Practically" note under multidata-unpickle-rce). Before relying on this in
production, run:

    systemd-run --pipe --property=PrivateNetwork=yes --property=MemoryMax=64M true

and confirm it succeeds on the actual host.
"""

from __future__ import annotations

import json
import logging
import pathlib
import shutil
import subprocess
import sys
from typing import Any

log = logging.getLogger("ap.sandbox")

DEFAULT_MEMORY_MAX = "512M"     # matches the Phase 1 sandbox reservation in the hosted plan
DEFAULT_RUNTIME_MAX_SEC = 30
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]  # parent of server/, so -m server.x resolves


class SandboxError(RuntimeError):
    """The sandboxed parse failed, timed out, or the child produced no usable output."""


def _systemd_run_available() -> bool:
    return sys.platform == "linux" and shutil.which("systemd-run") is not None


def _build_command(*, memory_max: str, runtime_max_sec: int, user: str | None) -> tuple[list[str], bool]:
    """Return (argv, is_sandboxed)."""
    worker = [sys.executable, "-m", "server.sandbox_worker"]

    if not _systemd_run_available():
        log.warning(
            "systemd-run not available on this platform (%s), running the untrusted "
            "multidata parse WITHOUT OS-level sandboxing. This is fine for local dev/tests "
            "but must never happen in production; see server/sandbox.py.",
            sys.platform,
        )
        return worker, False

    cmd = [
        "systemd-run",
        "--pipe",
        "--quiet",
        "--collect",
        "--wait",
        f"--property=RuntimeMaxSec={runtime_max_sec}",
        f"--property=MemoryMax={memory_max}",
        "--property=PrivateNetwork=yes",
        "--property=ProtectSystem=strict",
        "--property=ProtectHome=yes",
        "--property=NoNewPrivileges=yes",
        "--property=LimitFSIZE=0",
        f"--property=WorkingDirectory={_PROJECT_ROOT}",
    ]
    if user:
        cmd.append(f"--property=User={user}")
    cmd += worker
    return cmd, True


def run_sandboxed_parse(
    payload: bytes,
    *,
    memory_max: str = DEFAULT_MEMORY_MAX,
    runtime_max_sec: int = DEFAULT_RUNTIME_MAX_SEC,
    user: str | None = None,
) -> dict[str, Any]:
    """Parse untrusted .archipelago bytes to a sanitized dict, in a child process.

    Raises SandboxError if the child exits non-zero, times out, or produces
    output that isn't valid JSON. Never raises a pickle-related exception;
    the parent process never unpickles anything itself.
    """
    cmd, sandboxed = _build_command(memory_max=memory_max, runtime_max_sec=runtime_max_sec, user=user)
    try:
        result = subprocess.run(
            cmd,
            input=payload,
            capture_output=True,
            timeout=runtime_max_sec + 10,  # give systemd-run itself room to enforce its own tighter limit
            cwd=None if sandboxed else _PROJECT_ROOT,
        )
    except subprocess.TimeoutExpired as e:
        raise SandboxError("sandboxed multidata parse timed out") from e

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise SandboxError(f"sandboxed multidata parse failed: {stderr or f'exit {result.returncode}'}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise SandboxError("sandboxed multidata parse produced invalid JSON") from e
