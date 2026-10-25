#!/bin/sh
# Starts the worker and the web server in one container.
#
# The server binds 0.0.0.0 here rather than 127.0.0.1. Inside a container
# that is not exposing it to the network - the container's own loopback is
# unreachable from outside, so binding to it would make -p 8000:8000 do
# nothing. What the port is published to is decided by docker run.

set -e
cd /app

python3 /app/scripts/worker.py &
WORKER=$!

# stop both together on docker stop
trap 'kill $WORKER 2>/dev/null; exit 0' TERM INT

echo "miRPanel is running. Open http://localhost:8000"

exec uvicorn api:app --host 0.0.0.0 --port 8000 --app-dir /app/src
