#!/bin/bash
set -euo pipefail

python -u backend/allmusic_server.py & BACKEND_PID=$!
python -u backend/radio-live.py & LIVE_PID=$!

cleanup() {
  kill "$BACKEND_PID" "$LIVE_PID" 2>/dev/null || true
}
trap cleanup TERM INT

wait -n "$BACKEND_PID" "$LIVE_PID"
EXIT_CODE=$?
cleanup
exit $EXIT_CODE
