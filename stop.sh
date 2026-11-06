#!/usr/bin/env bash
# Stop laschuk-resume started by start.sh. Usage: ./stop.sh
set -euo pipefail
cd "$(dirname "$0")"

PIDFILE=run/laschuk-resume.pid
if [[ ! -f "$PIDFILE" ]]; then echo "laschuk-resume not running (no pidfile)"; exit 0; fi
PID="$(cat "$PIDFILE")"
if ! kill -0 "$PID" 2>/dev/null; then echo "stale pidfile removed"; rm -f "$PIDFILE"; exit 0; fi

kill -TERM "$PID"
for _ in $(seq 1 30); do
  kill -0 "$PID" 2>/dev/null || { rm -f "$PIDFILE"; echo "laschuk-resume stopped"; exit 0; }
  sleep 1
done
echo "did not exit after 30s; sending SIGKILL"; kill -KILL "$PID" 2>/dev/null || true
rm -f "$PIDFILE"
