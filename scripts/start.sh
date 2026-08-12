#!/bin/bash
# Launch the Archipelago web dashboard in tmux session "archipelago-web".
# Mirrors the pattern used by /opt/archipelago/scripts/regenerate.sh.
set -e

WEB_DIR="/opt/archipelago/web"
VENV="$WEB_DIR/.venv"
SESSION="archipelago-web"
PORT="${WEB_PORT:-8090}"

if [ ! -x "$VENV/bin/uvicorn" ]; then
    echo "!! venv missing or incomplete at $VENV"
    echo "   create it with: python3 -m venv $VENV && $VENV/bin/pip install -r $WEB_DIR/server/requirements.txt"
    exit 1
fi

# The dashboard now reads config.toml by default, but the VPS keeps its
# established paths by exporting the same env overrides it always used, so this
# deploy is unaffected by the community-release defaults.
CMD="cd $WEB_DIR && \
AP_HOST=localhost AP_PORT=38281 \
AP_FILE=/opt/archipelago/output/latest.archipelago \
AP_HOST_YAML=/opt/archipelago/host.yaml \
DEATHS_FILE=/opt/archipelago/death_leaderboard.json \
ITEMS_FILE=/opt/archipelago/received_items.json \
TAGS_FILE=/opt/archipelago/hint_tags.json \
WEB_DIST=$WEB_DIR/frontend/dist \
$VENV/bin/uvicorn server.main:app --host 127.0.0.1 --port $PORT"

# Always relaunch from scratch so the new process re-reads host.yaml (the
# dashboard caches server options — including the password — at startup). The
# old "Ctrl-C then retype" approach left the pane on a shell without actually
# restarting, so host.yaml edits never took effect.
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "==> Stopping existing $SESSION..."
    tmux send-keys -t "$SESSION" C-c
    sleep 2
    tmux kill-session -t "$SESSION"
fi

echo "==> Starting $SESSION on port $PORT"
tmux new-session -d -s "$SESSION" \; \
    set-option -t "$SESSION" window-size largest \; \
    set-option -t "$SESSION" aggressive-resize on \; \
    send-keys -t "$SESSION" "$CMD 2>&1 | tee /tmp/ap_web.log" Enter

sleep 2
if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "==> ✓ $SESSION is running."
else
    echo "==> !! $SESSION failed to start — check /tmp/ap_web.log"
    exit 1
fi

echo "==> Done."
