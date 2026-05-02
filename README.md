# Archipelago Web Dashboard

Public-facing player dashboard + hint manager for the self-hosted Archipelago
server. Reads `latest.archipelago` for totals/names and stays connected to the
server WebSocket as a passive `Tracker` to receive live `RoomUpdate` /
`PrintJSON` events for every slot.

## Layout

```
.
├── server/        FastAPI backend (Python 3.11+)
│   ├── main.py            routes + lifecycle
│   ├── multidata.py       .archipelago zlib+pickle reader
│   ├── tracker.py         persistent Tracker-tag AP WS client
│   ├── session.py         per-browser AP WS sessions for /api/hint
│   ├── state.py           WorldState + delta pub/sub
│   └── requirements.txt
├── frontend/      React + Vite + Tailwind frontend (Composio design tokens)
│   ├── package.json
│   ├── tailwind.config.ts
│   └── src/
├── scripts/start.sh   tmux launcher (session "archipelago-web")
└── .github/workflows/deploy.yml
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

## Config (env)

| var | default | purpose |
|---|---|---|
| `AP_HOST` | `localhost` | AP server host |
| `AP_PORT` | `38281` | AP server port |
| `AP_FILE` | `/opt/archipelago/output/latest.archipelago` | multidata to parse on boot |
| `AP_TRACKER_SLOT` | `DeathTracker` | slot used by the persistent tracker WS |
| `WEB_DIST` | `frontend/dist/` next to backend | static frontend dir |

The backend re-uses the existing `DeathTracker` slot — multiple clients can
share the same slot name.
