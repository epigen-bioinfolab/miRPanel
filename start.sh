#!/bin/bash

cd "$(dirname "$0")"

source venv/bin/activate

export PYTHONPATH=src

echo "Starting miRNA Tool..."
echo "Open http://localhost:8000 in your browser."

uvicorn api:app --host 127.0.0.1 --port 8000
