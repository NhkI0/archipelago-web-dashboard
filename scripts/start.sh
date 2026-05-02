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

CMD="cd $WEB_DIR && \
AP_HOST=localhost AP_PORT=38281 \
AP_FILE=/opt/archipelago/output/latest.archipelago \
WEB_DIST=$WEB_DIR/frontend/dist \
$VENV/bin/uvicorn server.main:app --host 127.0.0.1 --port $PORT"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "==> Restarting $SESSION"
    tmux send-keys -t "$SESSION" C-c ""
    sleep 2
    tmux send-keys -t "$SESSION" "$CMD" Enter
else
    echo "==> Starting $SESSION on port $PORT"
    tmux new-session -d -s "$SESSION" -x 220 -y 50 \; \
        send-keys -t "$SESSION" "$CMD 2>&1 | tee /tmp/ap_web.log" Enter
fi

echo "==> Done."
