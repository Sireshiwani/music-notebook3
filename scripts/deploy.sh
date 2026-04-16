#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/root/music-notebook3"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="shajara"
HEALTH_URL="http://127.0.0.1:8000/health"
CURRENT_FILE="$APP_DIR/.deploy_current_commit"

cd "$APP_DIR"

echo "[1/8] Capture current commit"
git rev-parse HEAD > "$CURRENT_FILE"

echo "[2/8] Fetch latest master"
git fetch origin
git checkout master
git reset --hard origin/master

echo "[3/8] Ensure virtualenv exists"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

echo "[4/8] Install dependencies"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
pip install flask-migrate psycopg2-binary gunicorn

echo "[5/8] Ensure app.py has Flask-Migrate wiring"
python3 - <<'PY'
from pathlib import Path

p = Path("app.py")
s = p.read_text()

if "from flask_migrate import Migrate" not in s:
    s = s.replace(
        "from flask_wtf import CSRFProtect",
        "from flask_wtf import CSRFProtect\nfrom flask_migrate import Migrate",
    )

if "Migrate(app, db)" not in s:
    s = s.replace(
        "    db.init_app(app)",
        "    db.init_app(app)\n    Migrate(app, db)",
    )

p.write_text(s)
print("Flask-Migrate wiring ensured")
PY

echo "[6/8] Run database migrations"
export FLASK_APP=app:create_app
if [ ! -d "migrations" ]; then
  flask db init
  flask db migrate -m "baseline schema"
fi
flask db upgrade

echo "[7/8] Restart app service"
systemctl daemon-reload
systemctl restart "$SERVICE_NAME"

echo "[8/8] Wait for service"
sleep 2
systemctl is-active --quiet "$SERVICE_NAME"

echo "[9/8] Health check"
curl -fsS "$HEALTH_URL" >/dev/null

echo "Deploy successful"
