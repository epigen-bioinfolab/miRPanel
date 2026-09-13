#!/bin/bash

cd "$(dirname "$0")"

source venv/bin/activate

export PYTHONPATH=src

echo "Starting miRNA Tool worker..."

python scripts/worker.py
