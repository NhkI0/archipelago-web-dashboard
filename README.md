# Archipelago Web Dashboard

Public-facing player dashboard + hint manager for the self-hosted Archipelago
server. Reads a generated `*.archipelago` for totals/names and stays connected
to the server WebSocket as a passive `Tracker` to receive live `RoomUpdate` /
`PrintJSON` events for every slot.

## Quick start (drop-and-run)

No build tools required — grab a packaged release (the release zip bundles a
prebuilt `frontend/dist`), then:

1. **Edit `config.toml`** — brand, footer, which tags exist, which features to
   show (see [Configuration](#configuration)).
2. **Drop your generated `*.archipelago`** into the `multiworld/` folder.
   - **Hosting the multiworld yourself?** Put the matching `host.yaml`
     alongside it — the dashboard detects it and connects to `localhost`,
     reading the port / hint cost / password straight from it.
   - **Watching someone else's multiworld?** No local `host.yaml` means there's
     nothing to read a port/password from, so set `[server.remote]` in
     `config.toml` to that server's address instead.
3. **Run it:**
   - macOS / Linux: `./run.sh`
   - Windows: double-click `run.bat`

The script creates a local Python virtualenv, installs dependencies, and serves
the dashboard on the port from `config.toml` (default
`http://localhost:8080`). Requires **Python 3.11+**; Node is *not* needed to run
a release.

> Running from a fresh **git clone** instead of a release? Build the frontend
> once first: `cd frontend && npm install && npm run build`. Releases skip this
> because CI (`release.yml`) bundles the prebuilt `frontend/dist`.

## Try it (no install)

A static, view-only demo runs entirely in the browser with sample data — make
hints, tag them, click around; everything resets on reload. It's published to
GitHub Pages via `.github/workflows/pages.yml`. Build it yourself with
`cd frontend && npm run build:demo && npm run preview`.

## Configuration

Everything host-facing lives in `config.toml` (parsed with Python's built-in
`tomllib`; every field is optional). Highlights:

| Section | Controls |
|---|---|
| `[server]` | AP host/port, `multiworld_dir`, `web_port`, `bind` |
| `[server.remote]` | fallback host/port/password used only when no local `host.yaml` is found — connect to a multiworld hosted elsewhere |
| `[branding]` | `hero_title`, `hero_image` (+ `hero_image_fade`), `loading_name` |
| `[footer]` | the two footer text lines |
| `[features]` | toggle the Hall of Fame, death leaderboard, constellation |
| `[hints]` | the hint tags players can pin, and which tag drives the "BKed" panel |

**Local vs. remote multiworld:** on boot the dashboard looks for a `host.yaml`
next to the `.archipelago` file in `multiworld_dir`. If found, it's treated as
local — it connects to `localhost` using that host.yaml's own port and
password, same as before. If not found, it falls back to `[server.remote]` and
connects to that address instead, so you can point the same dashboard at a
multiworld running on someone else's machine and still see live data as if it
were local. `AP_HOST`/`AP_PORT` env vars (used by the VPS deploy) always take
priority over both.

Drop custom images (e.g. a replacement `hero_image`) into `assets/` — they're
served under `/host/` with no rebuild. The frontend reads all of this at runtime
from `/api/config`, so one prebuilt bundle serves every host.

The footer shows a fixed **"Report issues or ask for features"** link to the
project maintainer (GitHub + Discord, in
`frontend/src/components/SocialLinks.tsx`). It is baked in, not host-configurable.

## Layout

```
.
├── config.toml     host configuration (branding, tags, features)
├── run.sh / run.bat  one-command launchers (create venv, install, serve)
├── multiworld/     drop your *.archipelago (and host.yaml) here
├── assets/         host-droppable images, served under /host/
├── data/           runtime logs (deaths / received items / hint tags)
├── server/         FastAPI backend (Python 3.11+)
│   ├── config.py         config.toml loader + /api/config subset
│   ├── __main__.py       `python -m server` entrypoint (used by run scripts)
│   ├── main.py           routes + lifecycle
│   ├── multidata.py      .archipelago zlib+pickle reader
│   ├── tracker.py        persistent Tracker-tag AP WS client
│   ├── session.py        per-browser AP WS sessions for /api/hint
│   ├── state.py          WorldState + delta pub/sub
│   └── requirements.txt
├── frontend/       React + Vite + Tailwind frontend
│   ├── src/config.tsx    ConfigProvider (fetches /api/config)
│   ├── src/demo/         in-memory backend for the static demo
│   └── src/
├── scripts/start.sh   tmux launcher (session "archipelago-web")
└── .github/workflows/  deploy.yml · pages.yml (demo) · release.yml (bundle)
```

## Local dev

```bash
# backend (from repo root)
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r server/requirements.txt
AP_FILE=/path/to/latest.archipelago uvicorn server.main:app --reload --port 8080

# frontend
cd frontend
npm install
npm run dev      # vite proxies /api and /ws to :8080
```

See `SETUP.md` for the full setup + VPS deploy guide.

## VPS deploy

`.github/workflows/deploy.yml` builds the frontend on the runner, scps
backend + dist to `/opt/archipelago/web/`, installs Python deps into the
on-VPS venv (`/opt/archipelago/web/.venv`), then restarts the
`archipelago-web` tmux session via `scripts/start.sh`.

Reverse-proxy with Caddy or nginx → `127.0.0.1:8080`.

## Config (env overrides)

Hosts should use `config.toml`. Environment variables still **override** any
config value (used by the VPS deploy in `scripts/start.sh`):

| var | overrides | purpose |
|---|---|---|
| `AP_CONFIG` | — | path to the config file (default `./config.toml`) |
| `AP_HOST` | `[server].ap_host` / `[server.remote].host` | AP server host (setting either `AP_HOST` or `AP_PORT` skips host.yaml/remote detection entirely) |
| `AP_PORT` | `[server].ap_port` / `[server.remote].port` | AP server port |
| `AP_FILE` | `[server].multiworld_dir` discovery | exact multidata to parse on boot |
| `AP_HOST_YAML` | `<multiworld_dir>/host.yaml` | host.yaml for hint cost / password |
| `DEATHS_FILE` / `ITEMS_FILE` / `TAGS_FILE` | `[paths].data_dir/*` | runtime JSON logs |
| `WEB_DIST` | `frontend/dist/` next to backend | static frontend dir |
| `WEB_PORT` / `WEB_BIND` | `[server].web_port` / `[server].bind` | listen port / address |
