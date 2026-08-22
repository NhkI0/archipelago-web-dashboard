"""Sandbox child entrypoint: python -m server.sandbox_worker.

Reads a raw .archipelago payload from stdin, runs the untrusted parse, and writes the
sanitized JSON result to stdout. Never touches the filesystem or network: everything it needs
arrives on stdin, everything it produces goes to stdout. Invoked by
server.sandbox.run_sandboxed_parse(), normally inside a systemd-run transient unit (see that
module's docstring for why).

Exit code 0 + sanitized JSON on stdout means success. Any failure (bad multidata, a safety
limit tripped, an unexpected exception) prints a message to stderr and exits non-zero; it
never partially writes to stdout.
"""

from __future__ import annotations

import json
import sys

from server.multidata import parse_untrusted


def main() -> int:
    payload = sys.stdin.buffer.read()
    try:
        sanitized = parse_untrusted(payload)
    except Exception as e:  # noqa: BLE001 - report and exit, don't leak a traceback shape as a signal
        print(f"sandbox_worker: rejected multidata: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(sanitized, separators=(",", ":")))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
