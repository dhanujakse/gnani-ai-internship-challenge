#!/usr/bin/env bash
# Puts the latest code on the server and restarts it. Run from the repository folder on the server:
#   git pull && bash deploy/update.sh
# Users stay signed in (sessions live in the database); calls in progress are dropped by the restart.
set -euo pipefail
APP_DIR=/opt/sarvagyan
DATA_DIR=/var/lib/sarvagyan
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

sudo rsync -a --delete --exclude .git --exclude android --exclude .env --exclude 'server/.venv' --exclude 'server/data' "$REPO_DIR/" "$APP_DIR/"
sudo chown -R sarvagyan:sarvagyan "$APP_DIR"
sudo -u sarvagyan env UV_CACHE_DIR="$DATA_DIR/.uv-cache" UV_PYTHON_INSTALL_DIR="$DATA_DIR/.uv-python" \
  bash -c "cd $APP_DIR/server && uv sync --frozen --no-dev"
sudo systemctl restart sarvagyan
sleep 3
curl -fsS http://127.0.0.1:8787/health && echo && echo "Updated and running."
