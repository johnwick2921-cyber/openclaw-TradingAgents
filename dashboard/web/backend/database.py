"""Dashboard DB compatibility layer over the unified OpenClaw SQLite schema.

This module keeps the async aiosqlite API the web backend expects, but points
it at the same database path and core schema used by openclaw.database.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite

from openclaw.config import load_config
from openclaw.database import init_db as core_init_db


def _resolve_db_path() -> str:
    """Resolve the unified trading database path from trading-config.json."""
    config = load_config()
    configured = config.get("paths", {}).get("database", "trading.db")
    return os.path.abspath(configured)


DB_PATH = _resolve_db_path()
DB_DIR = os.path.dirname(DB_PATH)

_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


async def init_db() -> None:
    """Initialize the unified DB and add dashboard-specific compatibility tables."""
    global DB_PATH, DB_DIR
    DB_PATH = _resolve_db_path()
    DB_DIR = os.path.dirname(DB_PATH)

    os.makedirs(DB_DIR, exist_ok=True)
    core_init_db(DB_PATH)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(_SETTINGS_TABLE_SQL)
        await db.commit()


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an async connection to the unified trading database.

    Self-initializes the schema on first access so route tests and direct module
    use do not depend on lifespan startup having already run.
    """
    global DB_PATH
    DB_PATH = _resolve_db_path()
    await init_db()
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()
