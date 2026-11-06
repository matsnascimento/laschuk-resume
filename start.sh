#!/usr/bin/env bash
# Start laschuk-resume in the background (no systemd). Usage: ./start.sh
set -euo pipefail
cd "$(dirname "$0")"

PIDFILE=run/laschuk-resume.pid
mkdir -p run logs data

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "laschuk-resume already running (pid $(cat "$PIDFILE"))"; exit 0
fi
[[ -f .env ]] || { echo "missing .env — copy .env.example to .env and fill it in"; exit 1; }

set -a; source .env; set +a
HOST="${HOST:-0.0.0.0}"; PORT="${PORT:-8787}"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
if [[ "${TRANSCRIBER:-auto}" == "local" || ( "${TRANSCRIBER:-auto}" == "auto" && -z "${OPENAI_API_KEY:-}" ) ]]; then
  .venv/bin/pip install -q -r requirements-local.txt
fi

nohup .venv/bin/uvicorn --factory app.main:app_factory --host "$HOST" --port "$PORT" \
  --workers 1 --no-access-log >> logs/stdout.log 2>&1 &
echo $! > "$PIDFILE"

sleep 2
if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "laschuk-resume started (pid $(cat "$PIDFILE")) on http://$HOST:$PORT — logs: logs/laschuk-resume.log"
else
  echo "laschuk-resume failed to start; see logs/stdout.log"; rm -f "$PIDFILE"; exit 1
fi
