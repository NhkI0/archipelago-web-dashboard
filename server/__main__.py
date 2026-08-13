"""``python -m server`` — launch the dashboard using config.toml.

Reads the bind address and port from config so the run.sh / run.bat wrappers
don't need to parse TOML themselves. Environment variables still override (see
server/main.py).
"""

from __future__ import annotations

import os

import uvicorn

from .config import load_config


def main() -> None:
    cfg = load_config()
    host = os.environ.get("WEB_BIND") or cfg["server"]["bind"]
    port = int(os.environ.get("WEB_PORT") or cfg["server"]["web_port"])
    uvicorn.run("server.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
