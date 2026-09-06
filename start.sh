#!/bin/bash
python -u backend/allmusic_server.py & BACKEND_PID=$!
python -u backend/radio-live.py & LIVE_PID=$!
trap 'kill "$BACKEND_PID" "$LIVE_PID" 2>/dev/null' TERM INT
wait -n
kill "$BACKEND_PID" "$LIVE_PID" 2>/dev/null