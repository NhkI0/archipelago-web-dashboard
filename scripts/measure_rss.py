"""Measure one room's process RSS: baseline, during a full connect, and settled.

Dev-only tool, not part of the shipped `server` package or its requirements.
Install its one extra dependency before running: pip install psutil

Usage (run from the `core/` directory, same env vars `python -m server`
understands — AP_FILE, AP_HOST/AP_PORT/AP_PASSWORD/AP_SECURE, AP_CONFIG, ...):

    AP_FILE=/path/to/big.archipelago AP_HOST=archipelago.gg AP_PORT=12345 \\
        python scripts/measure_rss.py

Point it at a real, deliberately large multiworld and a reachable AP server;
see the hosted-dashboard-plan memory for why (VPS sizing, the Windows
cross-process psutil quirk this works around via self-reporting over HTTP).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import psutil  # noqa: F401
except ImportError:
    print("this script needs psutil: pip install psutil", file=sys.stderr)
    raise SystemExit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.config import resolve_room_config  # noqa: E402
from server.multidata import load_multidata  # noqa: E402

CHILD_FLAG = "--child-serve-room"
CHILD_BARE_FLAG = "--child-serve-bare"


def _mount_self_report_route(app) -> None:
    """Add a debug-only route reporting the running process's own RSS."""
    import psutil as _psutil
    from fastapi import FastAPI

    assert isinstance(app, FastAPI)
    self_proc = _psutil.Process()

    @app.get("/_measure_rss")
    async def _measure_rss() -> dict:
        return {"rss_mb": self_proc.memory_info().rss / (1024 * 1024)}


def _run_child_room(port: int) -> None:
    """Build and serve the real room, like `python -m server`."""
    import uvicorn

    from server.main import build_app

    room = resolve_room_config()
    app = build_app(room)
    _mount_self_report_route(app)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def _run_child_bare(port: int) -> None:
    """An empty FastAPI app, for the fixed-overhead baseline."""
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI()
    _mount_self_report_route(app)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def _wait_for_http(url: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.1)
    raise TimeoutError(f"{url} never came up")


def _sample_rss_mb(port: int) -> float:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/_measure_rss", timeout=2) as resp:
        return json.loads(resp.read())["rss_mb"]


def _sample_peak_over(port: int, duration: float, interval: float = 0.05) -> float:
    peak = 0.0
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        try:
            peak = max(peak, _sample_rss_mb(port))
        except (urllib.error.URLError, OSError):
            break
        time.sleep(interval)
    return peak


def measure_bare_baseline(port: int) -> float:
    child = subprocess.Popen(
        [sys.executable, __file__, CHILD_BARE_FLAG, str(port)],
        cwd=Path(__file__).resolve().parent.parent,
    )
    try:
        _wait_for_http(f"http://127.0.0.1:{port}/_measure_rss")
        time.sleep(1.0)
        return _sample_rss_mb(port)
    finally:
        child.terminate()
        child.wait(timeout=10)


def measure_room(port: int) -> dict:
    child = subprocess.Popen(
        [sys.executable, __file__, CHILD_FLAG, str(port)],
        cwd=Path(__file__).resolve().parent.parent,
    )
    try:
        _wait_for_http(f"http://127.0.0.1:{port}/_measure_rss")
        time.sleep(1.0)
        baseline_mb = _sample_rss_mb(port)

        room = resolve_room_config()
        md = load_multidata(room.ap_file)
        slot = next(iter(md.slots.values()), None)
        if slot is None:
            raise RuntimeError("multidata has no slots to log in as")

        login_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/login",
            data=json.dumps({"slot": slot.name, "password": room.ap_password}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # Server-side login has its own internal 8s wait_for; the client
            # timeout here must stay comfortably larger or it races and loses.
            urllib.request.urlopen(login_req, timeout=20)
        except urllib.error.HTTPError as e:
            print(f"  (login returned {e.code}, continuing anyway - RSS during the attempt still counts)")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"  (login request failed: {e!r}, continuing anyway - RSS during the attempt still counts)")

        peak_mb = _sample_peak_over(port, duration=4.0)

        time.sleep(5.0)
        steady_mb = _sample_rss_mb(port)

        return {
            "slots": len(md.slots),
            "total_locations": sum(md.total_locations_for(s) for s in md.slots),
            "baseline_mb": baseline_mb,
            "peak_connect_mb": peak_mb,
            "steady_state_mb": steady_mb,
        }
    finally:
        child.terminate()
        child.wait(timeout=10)


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == CHILD_FLAG:
        _run_child_room(int(sys.argv[2]))
        return
    if len(sys.argv) >= 3 and sys.argv[1] == CHILD_BARE_FLAG:
        _run_child_bare(int(sys.argv[2]))
        return

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8123, help="port for the measured room process")
    parser.add_argument("--bare-port", type=int, default=8124, help="port for the fixed-overhead baseline process")
    args = parser.parse_args()

    print("== fixed overhead (empty FastAPI app, no multidata) ==")
    bare_mb = measure_bare_baseline(args.bare_port)
    print(f"  {bare_mb:.1f} MB")

    print("== room ==")
    result = measure_room(args.port)
    print(f"  slots={result['slots']} total_locations={result['total_locations']}")
    print(f"  baseline (loaded, no connections):  {result['baseline_mb']:.1f} MB")
    print(f"  peak during full connect:           {result['peak_connect_mb']:.1f} MB")
    print(f"  steady-state (5s after connect):    {result['steady_state_mb']:.1f} MB")
    print(f"  per-room cost over fixed overhead:  {result['peak_connect_mb'] - bare_mb:.1f} MB (peak)")


if __name__ == "__main__":
    main()
