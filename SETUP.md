# Archipelago Web Dashboard — Setup Guide

End-to-end instructions for getting this repo running both locally and on the
existing Ionos VPS (`nguengant.fr`, SSH port 2222).

The repo is laid out flat:
```
.
├── server/      FastAPI backend (Python)
├── frontend/    React + Vite + Tailwind app
├── scripts/     start.sh (tmux launcher)
├── .github/     CI/CD
├── README.md
└── SETUP.md     (this file)
```

> The dashboard reuses the `DeathTracker` slot already present in every
> generated world. Make sure `Players/DeathTracker.yaml` is committed to your
> Archipelago session repo before generating, or login & tracker will fail.

---

## 1. Prerequisites

### On your laptop
- **Python 3.11+** (for backend dev)
- **Node 20+** with `npm` (for frontend dev / building)
- A `.archipelago` file to test against (any seed produced by `ArchipelagoGenerate`)

### On the VPS (one-time)
```bash
ssh dopa@nguengant.fr -p 2222

# System packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv tmux nodejs npm caddy

# Lay out the dashboard tree and create the venv
sudo mkdir -p /opt/archipelago/web/{server,frontend,scripts}
sudo chown -R dopa:dopa /opt/archipelago/web
python3 -m venv /opt/archipelago/web/.venv
/opt/archipelago/web/.venv/bin/pip install --upgrade pip
```

The dashboard will run from this venv — nothing leaks into the system Python
that `archipelago_ui.py` uses. `requirements.txt` gets installed into the
venv automatically by the deploy workflow (see §3).

> `tmux`, `python3`, and `pip` should already be there from the existing
> `archipelago_ui.py` setup — you only need `caddy` (or `nginx` if you prefer).

---

## 2. Local development

```bash
git clone <your-fork> archipelago-web
cd archipelago-web
```

### 2a. Backend
```bash
# create the venv at the repo root (mirrors the VPS layout)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r server/requirements.txt

# point at any local .archipelago file
export AP_FILE=/absolute/path/to/your.archipelago
export AP_HOST=localhost
export AP_PORT=38281

# run from the repo root so "server.main" imports cleanly
uvicorn server.main:app --reload --port 8080
```

You should see:
```
INFO  ap.tracker  ...
INFO  Uvicorn running on http://0.0.0.0:8080
```

Quick smoke test:
```bash
curl localhost:8080/api/state | jq .seed_name
```

### 2b. Frontend
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Vite serves on `http://localhost:5173` and proxies `/api` and `/ws` to the
backend on `:8080`. Open the URL — Dashboard should populate.

---

## 3. First deploy to the VPS

> The directory and venv were already created in §1 ("On the VPS").
> If you skipped that step, run it now before pushing.

### 3a. GitHub secrets
The deploy workflow (`.github/workflows/deploy.yml`) reuses the secrets you
already added for the session repo:

| Secret | Value |
|---|---|
| `VPS_HOST` | `nguengant.fr` |
| `VPS_USER` | `dopa` |
| `VPS_SSH_KEY` | contents of `~/.ssh/archipelago_deploy` (private ed25519 key) |

No new secrets are needed.

### 3b. Push and let CI run
```bash
git add .
git commit -m "Initial dashboard"
git push origin main
```

Watch the run under **Actions → Deploy Web Dashboard**. On success it will:
1. `npm install && npm run build` in `frontend/` on the runner
2. `scp` `server/`, `frontend/dist/`, and `scripts/start.sh` to `/opt/archipelago/web/`
3. Install requirements **into the venv** at `/opt/archipelago/web/.venv`
4. Run `scripts/start.sh`, which spawns/refreshes the `archipelago-web` tmux session running the venv's `uvicorn` on port 8080

Verify directly on the VPS:
```bash
ssh dopa@nguengant.fr -p 2222
tmux attach -t archipelago-web
# Ctrl+b d to detach
curl localhost:8080/api/state | head -c 200
```

---

## 4. Reverse proxy + TLS

Pick a hostname. Examples below assume `play.nguengant.fr`. Point an `A`
record at the VPS IP first.

### Caddy (simplest — auto TLS)
```bash
sudo nano /etc/caddy/Caddyfile
```
Append:
```
play.nguengant.fr {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8080
}
```
```bash
sudo systemctl reload caddy
```

### nginx alternative
```nginx
server {
    listen 443 ssl http2;
    server_name play.nguengant.fr;
    ssl_certificate     /etc/letsencrypt/live/play.nguengant.fr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/play.nguengant.fr/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }
}
```
Get the cert with `sudo certbot --nginx -d play.nguengant.fr`.

Open the browser at `https://play.nguengant.fr` — Dashboard, live updates,
and `/ws/live` should all work.

---

## 5. Daily operation

### Restart the dashboard
```bash
ssh dopa@nguengant.fr -p 2222
/opt/archipelago/web/scripts/start.sh
```

### Tail logs
```bash
tail -f /tmp/ap_web.log
# or
tmux attach -t archipelago-web
```

### When you launch a new multiworld
The dashboard parses `latest.archipelago` **once at boot**. World generation
now happens locally; once the new zip is uploaded to
`/opt/archipelago/output/latest.zip`, run:
```bash
/opt/archipelago/scripts/start.sh
```
That script already restarts this dashboard, so no separate step is needed.

### When players need to hint
1. They visit `https://play.nguengant.fr/login`
2. Type their slot name (autocomplete pulls from the live world). Password
   only required if your seed sets one.
3. Go to **Hint Manager** → either tab → click **Hint** on a row.
   The backend opens a short-lived AP WS as that slot, sends `!hint <item>`
   or `!hint_location <location>`, the AP server charges their hint points,
   and the persistent tracker picks up the broadcast for everyone.

---

## 6. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `frontend not built` JSON at `/` | `frontend/dist/` didn't ship — re-run the workflow or `npm run build` locally and scp |
| Dashboard loads but slot list empty | `AP_FILE` points at a missing/old file. Update env in `start.sh` and restart |
| Tracker logs `refused: InvalidSlot` | `DeathTracker` slot missing from this seed — add `Players/DeathTracker.yaml` and regenerate |
| Login returns 401 "InvalidPassword" | Seed has a password; user must enter it on the login form |
| `/ws/live` keeps reconnecting in browser | Reverse proxy missing the `Upgrade` headers — see the nginx snippet above; Caddy's `reverse_proxy` does it by default |
| Hint button does nothing, log shows `session expired` | Cookie wasn't sent (cross-site / different host). Make sure the frontend is served from the same origin as the API (it is by default — FastAPI serves the static dist) |
| Port 8080 conflict | `WEB_PORT=8090 /opt/archipelago/web/scripts/start.sh` and adjust the reverse proxy |
| Multidata parse error on boot | An AP version changed the pickle schema. Run `python3 -c "import pickle, zlib, sys; print(list(pickle.loads(zlib.decompress(open(sys.argv[1],'rb').read())).keys()))" /opt/archipelago/output/latest.archipelago` and adjust `multidata.py` field names |

---

## 7. Security notes

- Sessions are an in-memory dict keyed by an `httpOnly` cookie. They die on
  process restart — that is fine.
- The site is **publicly readable**. Anyone with the URL can see every
  player's progression. There's no admin auth; the only thing protected is
  hint submission, which is gated by the AP server's slot password (if any).
- The backend trusts the multidata file (we generated it ourselves on the
  same VPS). Don't run this against multidata you didn't produce.
- The reverse proxy terminates TLS; the backend listens on plain HTTP on
  `127.0.0.1:8080` (set in `scripts/start.sh`). If you need to expose it
  directly during testing, change `--host 127.0.0.1` to `--host 0.0.0.0`.

---

## 8. Quick reference

```bash
# Local dev (from repo root)
source .venv/bin/activate
uvicorn server.main:app --reload --port 8080
# in another shell
cd frontend && npm run dev

# VPS restart
/opt/archipelago/web/scripts/start.sh

# VPS — install/upgrade backend deps manually
/opt/archipelago/web/.venv/bin/pip install -r /opt/archipelago/web/server/requirements.txt

# VPS logs
tail -f /tmp/ap_web.log

# Tmux sessions on the VPS
tmux ls
#   archipelago      -- the TUI + game server
#   archipelago-web  -- this dashboard
```
