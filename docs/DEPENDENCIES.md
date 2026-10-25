# miRNA Tool Dependencies

## Python
- Python 3.x
- Python packages: see `requirements-lock.txt`

## R
- R 4.5.0
- clusterProfiler 4.18.4
- org.Hs.eg.db 3.22.0

## External programs
- RNAhybrid
- Firefox or another web browser

## Application data
- SQLite database: `data/processed/mirna.db`

## Runtime
- FastAPI + Uvicorn web server
- Background worker: `scripts/worker.py`
