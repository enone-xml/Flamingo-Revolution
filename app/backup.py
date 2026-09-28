"""Make a consistent copy of the SQLite database and keep the last 14.

Run:  python -m app.backup
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config

KEEP = 14


def run() -> Path:
    src = Path(config.DB_PATH)
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"flamingo-{datetime.now(timezone.utc):%Y-%m-%d-%H%M}.db"
    with sqlite3.connect(src) as live, sqlite3.connect(dest) as copy:
        live.backup(copy)  # safe while the app is running
    for old in sorted(dest_dir.glob("flamingo-*.db"))[:-KEEP]:
        old.unlink()
    return dest


if __name__ == "__main__":
    print(f"backup written: {run()}")
