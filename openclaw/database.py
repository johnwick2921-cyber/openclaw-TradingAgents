"""SQLite database schema for trading run persistence.

Tables: runs, reports, debates, memories, outcomes.
Uses synchronous sqlite3 (no aiosqlite dependency for the core package).
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'default',
    signal TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    error_message TEXT,
    duration_seconds REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    section_name TEXT NOT NULL,
    content TEXT
);

CREATE TABLE IF NOT EXISTS debates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    debate_type TEXT NOT NULL,
    full_history TEXT,
    side_a_history TEXT,
    side_b_history TEXT,
    side_c_history TEXT,
    judge_decision TEXT
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    situation TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    run_id TEXT,  -- intentionally no FK: memories can exist independently of runs
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,  -- intentionally no FK: outcomes can be recorded for runs from other systems
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    signal TEXT NOT NULL,
    actual_close REAL,
    actual_change_pct REAL,
    correct INTEGER,
    reflection TEXT,
    created_at TEXT NOT NULL
);
"""


def init_db(db_path: str) -> None:
    """Create all tables and enable PRAGMA optimizations.

    Args:
        db_path: Path to the SQLite database file.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(_CREATE_TABLES_SQL)
        conn.commit()
    finally:
        conn.close()


def safe_get_db(db_path: str):
    """Return a get_db context manager, initializing the DB if it doesn't exist."""
    if not os.path.exists(db_path):
        init_db(db_path)
    return get_db(db_path)


@contextmanager
def get_db(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a sqlite3.Connection with Row factory.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        sqlite3.Connection configured with Row factory and foreign keys.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
