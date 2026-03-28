"""Tests for the dashboard terminal modules."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.panel import Panel

from openclaw.database import init_db, get_db
from dashboard.terminal.monitor import render_signal_board, show_monitor
from dashboard.terminal.analysis_viewer import show_analysis


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary trading-config.json with a watchlist."""
    config = {
        "strategy": "default",
        "halt": False,
        "watchlist": ["AAPL", "NVDA"],
        "paths": {"database": str(tmp_path / "test.db")},
    }
    path = str(tmp_path / "config.json")
    with open(path, "w") as f:
        json.dump(config, f)
    return path, str(tmp_path / "test.db")


@pytest.fixture
def populated_db(tmp_path):
    """Create a trading.db with sample data."""
    db_path = str(tmp_path / "populated.db")
    init_db(db_path)

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO runs (id, ticker, trade_date, strategy, signal, status, "
            "duration_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("run-001", "AAPL", "2026-03-27", "default", "buy", "completed",
             42.5, "2026-03-27T10:00:00"),
        )
        conn.execute(
            "INSERT INTO reports (run_id, section_name, content) VALUES (?, ?, ?)",
            ("run-001", "Market Analysis", "Strong bullish momentum observed."),
        )
        conn.execute(
            "INSERT INTO reports (run_id, section_name, content) VALUES (?, ?, ?)",
            ("run-001", "News Summary", "Positive earnings beat expectations."),
        )
        conn.execute(
            "INSERT INTO debates (run_id, debate_type, side_a_history, "
            "side_b_history, judge_decision) VALUES (?, ?, ?, ?, ?)",
            ("run-001", "Bull vs Bear", "Strong earnings, expanding margins",
             "Overvalued at current levels", "Bullish — fundamentals support upside"),
        )
        conn.execute(
            "INSERT INTO memories (agent_name, situation, recommendation, "
            "run_id, created_at) VALUES (?, ?, ?, ?, ?)",
            ("market-analyst", "tech sector rally", "buy the dip",
             "run-001", "2026-03-27T10:00:00"),
        )
        conn.execute(
            "INSERT INTO outcomes (run_id, ticker, trade_date, signal, "
            "correct, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("run-001", "AAPL", "2026-03-27", "buy", 1, "2026-03-27T16:00:00"),
        )
        conn.commit()

    return db_path


def test_monitor_renders(tmp_config, populated_db):
    """render_signal_board returns a Rich Panel without crashing."""
    config_path, _ = tmp_config
    panel = render_signal_board(config_path=config_path, db_path=populated_db)
    assert isinstance(panel, Panel)


def test_monitor_with_empty_db(tmp_path):
    """render_signal_board works with an empty (freshly initialized) database."""
    db_path = str(tmp_path / "empty.db")
    init_db(db_path)

    config = {"watchlist": [], "paths": {"database": db_path}}
    config_path = str(tmp_path / "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)

    panel = render_signal_board(config_path=config_path, db_path=db_path)
    assert isinstance(panel, Panel)


def test_monitor_with_nonexistent_db(tmp_path):
    """render_signal_board works even if DB file doesn't exist yet."""
    db_path = str(tmp_path / "missing.db")
    config = {"watchlist": ["SPY"], "paths": {"database": db_path}}
    config_path = str(tmp_path / "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)

    panel = render_signal_board(config_path=config_path, db_path=db_path)
    assert isinstance(panel, Panel)


def test_viewer_missing_run(tmp_path):
    """show_analysis gracefully handles a nonexistent run_id."""
    db_path = str(tmp_path / "viewer.db")
    init_db(db_path)

    result = show_analysis("nonexistent-run-id", db_path=db_path)
    assert result is None


def test_viewer_with_data(tmp_config, populated_db):
    """show_analysis returns a Panel for a valid run."""
    result = show_analysis("run-001", db_path=populated_db)
    assert isinstance(result, Panel)


def test_viewer_reports_and_debates(populated_db):
    """show_analysis includes reports and debates in the output."""
    result = show_analysis("run-001", db_path=populated_db)
    assert result is not None
    assert isinstance(result, Panel)
