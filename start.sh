#!/bin/bash

cd "$(dirname "$0")"

source venv/bin/activate

export PYTHONPATH=src

echo "Starting miRNA Tool..."
echo "Open http://localhost:8000 in your browser."

uvicorn api:app --host 0.0.0.0 --port 8000
