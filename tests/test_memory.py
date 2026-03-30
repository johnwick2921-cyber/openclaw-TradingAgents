"""Tests for openclaw.database and openclaw.memory_persistence."""

import os
import sys
import sqlite3
import tempfile

# Ensure openclaw and TradingAgents are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ))

from openclaw.database import init_db, get_db
from openclaw.memory_persistence import persist_memories, hydrate_memories
from openclaw.memory import FinancialSituationMemory


def _tmp_db():
    """Create a temporary database file and initialize it."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    return path


def _make_memories():
    """Create a sample memories dict with test data."""
    mem = FinancialSituationMemory("bull_memory")
    mem.add_situations([
        ("High inflation with rising rates", "Shift to defensive sectors"),
        ("Tech selloff with institutional exits", "Reduce growth exposure"),
    ])
    return {"bull": mem}


class TestInitDb:
    def test_init_db_creates_tables(self):
        """Verify all 5 tables are created by init_db."""
        db_path = _tmp_db()
        try:
            with get_db(db_path) as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = sorted(row["name"] for row in cursor if row["name"] != "sqlite_sequence")
            expected = ["debates", "memories", "outcomes", "reports", "runs"]
            assert tables == expected, f"Expected {expected}, got {tables}"
        finally:
            os.unlink(db_path)


class TestPersistAndHydrate:
    def test_persist_and_hydrate_roundtrip(self):
        """Add memories, persist, create new store, hydrate, verify data matches."""
        db_path = _tmp_db()
        try:
            # Persist
            original = _make_memories()
            inserted = persist_memories(original, db_path, "run-001")
            assert inserted == 2

            # Hydrate into fresh stores
            fresh = {"bull": FinancialSituationMemory("bull_memory")}
            loaded = hydrate_memories(fresh, db_path)
            assert loaded == 2

            # Verify data matches
            assert fresh["bull"].documents == original["bull"].documents
            assert fresh["bull"].recommendations == original["bull"].recommendations
        finally:
            os.unlink(db_path)

    def test_bm25_search_after_hydration(self):
        """Query after hydration returns relevant results."""
        db_path = _tmp_db()
        try:
            original = _make_memories()
            persist_memories(original, db_path, "run-002")

            fresh = {"bull": FinancialSituationMemory("bull_memory")}
            hydrate_memories(fresh, db_path)

            results = fresh["bull"].get_memories("inflation rates defensive", n_matches=1)
            assert len(results) == 1
            assert "inflation" in results[0]["matched_situation"].lower()
        finally:
            os.unlink(db_path)

    def test_persist_avoids_duplicates(self):
        """Same data persisted twice produces only 1 copy."""
        db_path = _tmp_db()
        try:
            memories = _make_memories()

            first = persist_memories(memories, db_path, "run-003")
            assert first == 2

            second = persist_memories(memories, db_path, "run-004")
            assert second == 0

            # Verify only 2 rows total in database
            with get_db(db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) as cnt FROM memories")
                count = cursor.fetchone()["cnt"]
            assert count == 2
        finally:
            os.unlink(db_path)


class TestMarkdownSummary:
    def test_markdown_summary_written(self):
        """FileMemoryCallback should write summary to memory/YYYY-MM-DD.md."""
        import tempfile
        from openclaw.callbacks import FileMemoryCallback
        from openclaw.engine import RunResult

        with tempfile.TemporaryDirectory() as tmpdir:
            cb = FileMemoryCallback(memory_dir=tmpdir)
            cb.on_run_start("NVDA", "2026-03-28")
            cb.on_report_section("market_report", "Market looks bullish")
            cb.on_signal("BUY")
            result = RunResult(
                run_id="test-001", ticker="NVDA", date="2026-03-28",
                signal="BUY", duration_seconds=5.0,
            )
            cb.on_run_complete(result)

            filepath = os.path.join(tmpdir, "2026-03-28.md")
            assert os.path.exists(filepath), "Summary file not created"
            with open(filepath) as f:
                content = f.read()
            assert "NVDA" in content
            assert "BUY" in content
            assert "Market looks bullish" in content


class TestOutcomeRecording:
    def test_outcome_recording(self):
        """Insert outcome row, read back, verify fields."""
        db_path = _tmp_db()
        try:
            # Insert a run first (foreign key target)
            with get_db(db_path) as conn:
                conn.execute(
                    "INSERT INTO runs (id, ticker, trade_date, strategy, signal, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("run-010", "NVDA", "2026-03-28", "default", "BUY", "completed", "2026-03-28T10:00:00Z"),
                )
                conn.execute(
                    "INSERT INTO outcomes (run_id, ticker, trade_date, signal, actual_close, "
                    "actual_change_pct, correct, reflection, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("run-010", "NVDA", "2026-03-28", "BUY", 145.50, 2.3, 1,
                     "Signal was correct, stock rose 2.3%", "2026-03-29T10:00:00Z"),
                )
                conn.commit()

            # Read back
            with get_db(db_path) as conn:
                cursor = conn.execute("SELECT * FROM outcomes WHERE run_id = ?", ("run-010",))
                row = cursor.fetchone()

            assert row["ticker"] == "NVDA"
            assert row["trade_date"] == "2026-03-28"
            assert row["signal"] == "BUY"
            assert row["actual_close"] == 145.50
            assert row["actual_change_pct"] == 2.3
            assert row["correct"] == 1
            assert "correct" in row["reflection"].lower()
        finally:
            os.unlink(db_path)
