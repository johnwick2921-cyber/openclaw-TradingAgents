import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite

# Database file path relative to project root
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_DIR = os.path.join(_PROJECT_ROOT, "webui", "data")
DB_PATH = os.path.join(DB_DIR, "tradingagents.db")

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    provider TEXT NOT NULL,
    deep_model TEXT,
    quick_model TEXT,
    effort TEXT,
    backend_url TEXT,
    max_debate_rounds INTEGER DEFAULT 1,
    max_risk_discuss_rounds INTEGER DEFAULT 1,
    data_vendors TEXT DEFAULT '{}',
    tool_vendors TEXT DEFAULT '{}',
    selected_analysts TEXT DEFAULT '[]',
    signal TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    error_message TEXT,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
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
    debate_type TEXT,
    full_history TEXT,
    side_a_history TEXT,
    side_b_history TEXT,
    side_c_history TEXT,
    judge_decision TEXT
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    situation TEXT,
    recommendation TEXT,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


async def init_db() -> None:
    """Initialize the database, creating tables if they do not exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_CREATE_TABLES_SQL)
        await db.commit()


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager that yields an aiosqlite connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
