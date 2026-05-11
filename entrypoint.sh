#!/bin/sh
set -e

# Initial build so the page is live as soon as the container is up
python3 /app/build_manifest.py || echo "initial build failed — empty manifest will be served until next cron tick"

# crond rebuilds on schedule; http.server stays in the foreground (PID 1)
crond -f -L /dev/stderr &
cd "$NOTES_OUT_DIR" && exec python3 -m http.server "${PORT:-8181}" --bind 0.0.0.0
