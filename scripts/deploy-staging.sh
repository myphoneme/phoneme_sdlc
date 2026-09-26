#!/usr/bin/env bash
# Phoneme SDLC Platform — staging deploy script
#
# Idempotent: safe to re-run for every future update. First run turns the
# staging directory into a real git clone (fresh clone + swap); every run
# after that is just a `git pull` + rebuild + restart in place.
#
# Usage (as the user/root that currently runs the backend on staging):
#   chmod +x deploy-staging.sh
#   ./deploy-staging.sh
#
# What it does, in order:
#   1. Stops whatever is currently listening on $PORT (the running backend)
#   2. Clones a fresh copy of the repo (first run only) or `git pull`s
#      (subsequent runs) — never touches an existing .env
#   3. Installs backend deps (creates/reuses a venv) and frontend deps,
#      builds the frontend
#   4. Starts the backend in the background, logging to backend.log,
#      and writes its PID to backend.pid for the next run to stop cleanly
#   5. Curls the health endpoint to confirm it came up

set -euo pipefail

# ---------------------------------------------------------------------------
# Config — edit these if your paths/ports differ
# ---------------------------------------------------------------------------
REPO_URL="https://github.com/myphoneme/phoneme_sdlc.git"
BASE_DIR="/home/project"
LIVE_DIR="$BASE_DIR/phoneme_sdlc"          # the directory actually served
BACKUP_DIR="$BASE_DIR/phoneme_sdlc_old"    # first-run-only backup of the pre-git copy
PORT=8081
HOST="0.0.0.0"
PYTHON_BIN="${PYTHON_BIN:-python3}"

ORCH_DIR="$LIVE_DIR/apps/orchestrator"
WEB_DIR="$LIVE_DIR/apps/web"
ENV_FILE="$ORCH_DIR/.env"
PID_FILE="$LIVE_DIR/backend.pid"
LOG_FILE="$LIVE_DIR/backend.log"

echo "==> Phoneme SDLC staging deploy starting: $(date)"

# ---------------------------------------------------------------------------
# 1. Stop whatever is currently serving $PORT
# ---------------------------------------------------------------------------
stop_backend() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "==> Stopping existing backend (pid $(cat "$PID_FILE"))"
    kill "$(cat "$PID_FILE")" || true
    sleep 2
    kill -9 "$(cat "$PID_FILE")" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  # Belt-and-braces: kill anything still bound to the port
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:"$PORT" 2>/dev/null | xargs -r kill -9 || true
  fi
}
stop_backend

# ---------------------------------------------------------------------------
# 2. Get the latest code — first run: fresh clone + swap. Later runs: pull.
# ---------------------------------------------------------------------------
if [ -d "$LIVE_DIR/.git" ]; then
  echo "==> Existing git checkout found — pulling latest"
  git -C "$LIVE_DIR" fetch origin
  git -C "$LIVE_DIR" reset --hard origin/main
else
  echo "==> No git checkout yet — cloning fresh and swapping in"
  NEW_DIR="$BASE_DIR/phoneme_sdlc_new"
  rm -rf "$NEW_DIR"
  git clone "$REPO_URL" "$NEW_DIR"

  # Carry over the real .env (has the live Anthropic/Gemini keys) if present
  if [ -f "$LIVE_DIR/.env" ]; then
    cp "$LIVE_DIR/.env" "$NEW_DIR/apps/orchestrator/.env"
  elif [ -f "$LIVE_DIR/apps/orchestrator/.env" ]; then
    cp "$LIVE_DIR/apps/orchestrator/.env" "$NEW_DIR/apps/orchestrator/.env"
  else
    echo "!! WARNING: no existing .env found to carry over."
    echo "!! You'll need to create $NEW_DIR/apps/orchestrator/.env yourself before the backend can use the commercial tier."
  fi
  # Make sure .env can never be committed from the new checkout
  grep -qxF '.env' "$NEW_DIR/.gitignore" 2>/dev/null || echo '.env' >> "$NEW_DIR/.gitignore"
  grep -qxF '.env' "$NEW_DIR/apps/orchestrator/.gitignore" 2>/dev/null || echo '.env' >> "$NEW_DIR/apps/orchestrator/.gitignore"

  if [ -d "$LIVE_DIR" ]; then
    rm -rf "$BACKUP_DIR"
    mv "$LIVE_DIR" "$BACKUP_DIR"
    echo "==> Old (pre-git) staging copy preserved at $BACKUP_DIR — safe to delete once you've confirmed the new one works"
  fi
  mv "$NEW_DIR" "$LIVE_DIR"
fi

# ---------------------------------------------------------------------------
# 3. Install deps + build
# ---------------------------------------------------------------------------
echo "==> Installing backend dependencies"
cd "$ORCH_DIR"
if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
deactivate

echo "==> Installing frontend dependencies and building"
cd "$WEB_DIR"
npm install --silent
npm run build

# ---------------------------------------------------------------------------
# 4. Start the backend
# ---------------------------------------------------------------------------
echo "==> Starting backend on ${HOST}:${PORT}"
cd "$ORCH_DIR"
source .venv/bin/activate
nohup uvicorn app.main:app --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
deactivate
disown || true

# ---------------------------------------------------------------------------
# 5. Health check
# ---------------------------------------------------------------------------
echo "==> Waiting for health check..."
for i in $(seq 1 10); do
  sleep 1
  if curl -sf "http://localhost:${PORT}/api/health" > /tmp/phoneme_health.json 2>/dev/null; then
    echo "==> Backend is up:"
    cat /tmp/phoneme_health.json
    echo
    echo "==> Deploy complete: $(date)"
    exit 0
  fi
done

echo "!! Backend did not respond to health check after 10s."
echo "!! Check $LOG_FILE for errors:"
tail -n 40 "$LOG_FILE" || true
exit 1
