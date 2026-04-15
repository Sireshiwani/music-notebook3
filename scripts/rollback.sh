#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/music-notebook3"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="shajara"
CURRENT_FILE="$APP_DIR/.deploy_current_commit"

cd "$APP_DIR"

if [ ! -f "$CURRENT_FILE" ]; then
  echo "No rollback commit file found: $CURRENT_FILE"
  exit 1
fi

PREV_COMMIT="$(cat "$CURRENT_FILE")"
echo "Rolling back to $PREV_COMMIT"

git fetch origin
git checkout "$PREV_COMMIT"

source "$VENV_DIR/bin/activate"
pip install -r requirements.txt

systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"

echo "Rollback successful"