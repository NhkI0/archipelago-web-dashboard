"""``python -m server`` — launch the dashboard using config.toml.

Reads the bind address and port from config so the run.sh / run.bat wrappers don't need to parse TOML themselves.
Environment variables still override (see server/config.py's resolve_room_config()).
"""

from __future__ import annotations

import logging
import os

import uvicorn

from .config import resolve_room_config
from .main import build_app

log = logging.getLogger("ap.web")


def main() -> None:
    try:
        room = resolve_room_config()
    except FileNotFoundError as e:
        log.error("=" * 80)
        log.error("NO MULTIWORLD FOUND")
        log.error(str(e))
        log.error("=" * 80)
        raise SystemExit(1) from None
    except RuntimeError as e:
        log.error("=" * 80)
        log.error(str(e))
        log.error("=" * 80)
        raise SystemExit(1) from None

    try:
        app = build_app(room)
    except Exception:
        raise SystemExit(1) from None

    host = os.environ.get("WEB_BIND") or room.config["server"]["bind"]
    port = int(os.environ.get("WEB_PORT") or room.config["server"]["web_port"])
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
