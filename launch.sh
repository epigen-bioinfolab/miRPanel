#!/bin/bash

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$APP_DIR" || exit 1

source "$APP_DIR/venv/bin/activate"

export PYTHONPATH="$APP_DIR/src"

echo "===================================="
echo "        miRNA Tool"
echo "===================================="

# Start worker if it is not already running
if pgrep -f "$APP_DIR/scripts/worker.py" > /dev/null; then
    echo "Worker: already running"
else
    echo "Worker: starting..."
    nohup python "$APP_DIR/scripts/worker.py" >> "$APP_DIR/worker.log" 2>&1 &
    echo "Worker: started"
fi

# Start web server if port 8000 is not already being used
if ss -ltn 2>/dev/null | grep -q ':8000 '; then
    echo "Web server: already running"
else
    echo "Web server: starting..."
    nohup uvicorn api:app --host 0.0.0.0 --port 8000 >> "$APP_DIR/server.log" 2>&1 &
    echo "Web server: started"
fi

echo ""
echo "miRNA Tool is available at:"
echo "http://localhost:8000"
echo ""

sleep 2
firefox http://localhost:8000 >/dev/null 2>&1 &
