"""Sandboxed execution of the untrusted .archipelago parse.

Defense in depth on top of multidata.py's allowlisted unpickler: runs the parse in a
child process so a bug in the allowlist can't reach the network, filesystem, or more
than a bounded amount of CPU/memory/time.

On Linux with systemd-run available, the parse runs in a transient systemd service
with PrivateNetwork, memory/time ceilings, and no filesystem write access; this is
the only path that is an actual security boundary. Everywhere else it falls back to
a plain subprocess, which only isolates crashes/hangs and logs a warning each time.
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
