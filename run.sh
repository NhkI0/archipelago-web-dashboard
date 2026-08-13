#!/usr/bin/env bash
# Archipelago Web Dashboard, one-command launcher (macOS / Linux).
#
#   1. Edit config.toml
#   2. Drop your generated *.archipelago into ./multiworld/
#   3. ./run.sh
#
# Creates a local Python virtualenv on first run, installs dependencies, then
# serves the (prebuilt) dashboard on the port from config.toml.
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || { echo "!! Python 3.11+ is required but was not found."; exit 1; }

# config.toml is optional, but if it exists it must be valid TOML — a syntax
# error (e.g. a duplicate key) makes the whole file silently fall back to
# built-in defaults, which is confusing unless we call it out loudly here.
if [ -f config.toml ] && ! "$PY" - <<'PY' 2>/dev/null
import tomllib
with open("config.toml", "rb") as f:
    tomllib.load(f)
PY
then
    echo "!!"
    echo "!! WARNING: config.toml has invalid TOML syntax and is being IGNORED."
    echo "!!          The dashboard will start with built-in defaults instead of"
    echo "!!          your settings. Fix config.toml and restart to apply them."
    echo "!!"
fi

if [ ! -d .venv ]; then
    echo "==> Creating virtual environment (.venv)…"
    "$PY" -m venv .venv
fi

# venv layout differs between POSIX (bin/) and Git-Bash-on-Windows (Scripts/)
VENV_PY=.venv/bin/python
[ -x "$VENV_PY" ] || VENV_PY=.venv/Scripts/python.exe

echo "==> Installing dependencies…"
"$VENV_PY" -m pip install -q --upgrade pip
"$VENV_PY" -m pip install -q -r server/requirements.txt

echo "==> Starting dashboard (Ctrl-C to stop)…"
exec "$VENV_PY" -m server
