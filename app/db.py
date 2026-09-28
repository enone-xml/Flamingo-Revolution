"""SQLite storage. One file, created on first use."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY,
    url           TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    title_norm    TEXT NOT NULL,
    snippet       TEXT,             -- feed snippet, kept only until the AI step runs
    source        TEXT NOT NULL,
    lang          TEXT,
    published_at  TEXT NOT NULL,    -- ISO 8601 UTC
    fetched_at    TEXT NOT NULL,
    ai_status     TEXT NOT NULL DEFAULT 'pending',  -- pending/done/failed/skipped/keyword_only
    relevant      INTEGER,          -- 1/0 from the AI, NULL if unknown
    title_en      TEXT,
    title_sq      TEXT,
    summary_en    TEXT,
    summary_sq    TEXT,
    tags          TEXT,             -- JSON list
    story_key     TEXT
);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_title_norm ON articles(title_norm);
CREATE INDEX IF NOT EXISTS idx_articles_ai_status ON articles(ai_status);

CREATE TABLE IF NOT EXISTS feed_status (
    source        TEXT PRIMARY KEY,
    url           TEXT,
    etag          TEXT,
    modified      TEXT,
    last_ok_at    TEXT,
    last_error_at TEXT,
    last_error    TEXT,
    last_new      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ai_usage (
    id            INTEGER PRIMARY KEY,
    created_at    TEXT NOT NULL,
    month         TEXT NOT NULL,    -- YYYY-MM
    article_id    INTEGER,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_month ON ai_usage(month);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path: str | None = None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def set_meta(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def get_meta(conn, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default
