"""Open the project database and apply the schema."""
import sqlite3
from pathlib import Path

DB_PATH = "data/processed/mirna.db"
SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path=DB_PATH):
    """Return a connection, creating the file and tables if they don't exist."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA cache_size = -64000")
    con.executescript(SCHEMA.read_text())
    return con
