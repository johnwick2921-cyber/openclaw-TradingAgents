"""Tests for the RunEngine orchestrator."""

import json
import os
import pytest
from openclaw.engine import RunEngine, RunResult
from openclaw.dataflows.config import get_config
from openclaw.callbacks import CollectorCallback


# ---------- Fixtures ----------

@pytest.fixture
def config_file(tmp_path):
    """Create a minimal config file and agent .md stubs for testing."""
    agents_dir = tmp_path / "agents" / "trading"
    agents_dir.mkdir(parents=True)

    config = {
        "strategy": "default",
        "halt": False,
        "analysis": {
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "analysts": ["market"],
            "agent_timeout_seconds": 10,
        },
        "paths": {
            "agents_dir": str(agents_dir),
            "database": str(tmp_path / "test.db"),
            "memory_dir": str(tmp_path / "memory"),
            "results_dir": str(tmp_path / "results"),
        },
    }
    path = str(tmp_path / "test-config.json")
    with open(path, "w") as f:
        json.dump(config, f)

    # Create minimal agent .md files
    for name in [
        "market-analyst", "bull-researcher", "bear-researcher",
        "research-manager", "trader", "aggressive-risk",
        "conservative-risk", "neutral-risk", "portfolio-manager",
    ]:
        (agents_dir / f"{name}.md").write_text(
            f"---\nname: {name}\n---\n# {name}\n"
            f"## Default Strategy Prompt\nYou are {name}. Analyze the data and respond.\n"
            f"## JadeCap Strategy Prompt\nN/A\n"
        )
    return path


def _stub_dispatch(agent_name, prompt, model):
    """A simple stub dispatch that returns a canned response."""
    return f"[Stub response from {agent_name}]"


# ---------- Tests ----------

def test_engine_loads_config(config_file):
    engine = RunEngine(config_path=config_file)
    assert engine.config["strategy"] == "default"
    assert engine.config["halt"] is False


def test_engine_halted_blocks_run(config_file):
    engine = RunEngine(config_path=config_file)
    engine.halt()
    with pytest.raises(RuntimeError, match="halted"):
        engine.run("NVDA", "2026-03-27")


def test_engine_halt_and_resume(config_file):
    engine = RunEngine(config_path=config_file)
    engine.halt()
    assert engine.config["halt"] is True
    assert engine.status["state"] == "halted"

    engine.resume()
    assert engine.config["halt"] is False
    assert engine.status["state"] == "idle"


def test_engine_run_with_stub_dispatch(config_file):
    """Full pipeline with stub dispatch should complete without errors."""
    engine = RunEngine(config_path=config_file)
    collector = CollectorCallback()

    result = engine.run("NVDA", "2026-03-27", callbacks=[collector])

    assert isinstance(result, RunResult)
    assert result.ticker == "NVDA"
    assert result.date == "2026-03-27"
    assert result.signal in ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
    assert result.duration_seconds > 0

    # Verify events were emitted
    event_types = [e[0] for e in collector.events]
    assert "run_start" in event_types
    assert "signal" in event_types
    assert "complete" in event_types


def test_engine_extract_signal():
    engine = RunEngine.__new__(RunEngine)
    assert engine._extract_signal("FINAL TRANSACTION PROPOSAL: **BUY**") == "BUY"
    assert engine._extract_signal("Rating: SELL\nSome explanation") == "SELL"
    assert engine._extract_signal("I recommend we HOLD for now") == "HOLD"
    assert engine._extract_signal("OVERWEIGHT based on analysis") == "OVERWEIGHT"
    assert engine._extract_signal("no clear signal here") == "HOLD"  # fallback


def test_engine_debate_terminates(config_file):
    """Debate should run exactly max_debate_rounds times."""
    engine = RunEngine(config_path=config_file)
    call_count = {"bull": 0, "bear": 0}

    def counting_dispatch(agent_name, prompt, model):
        if "bull" in agent_name:
            call_count["bull"] += 1
        elif "bear" in agent_name:
            call_count["bear"] += 1
        return f"[Response from {agent_name}]"

    engine.run("NVDA", "2026-03-27", dispatch_fn=counting_dispatch)

    assert call_count["bull"] == 1  # max_debate_rounds = 1
    assert call_count["bear"] == 1


def test_engine_callbacks_fire(config_file):
    """CollectorCallback should capture all expected event types."""
    engine = RunEngine(config_path=config_file)
    collector = CollectorCallback()

    engine.run("NVDA", "2026-03-27", dispatch_fn=_stub_dispatch, callbacks=[collector])

    event_types = [e[0] for e in collector.events]

    # Must have these event types
    assert "run_start" in event_types
    assert "agent_status" in event_types
    assert "report" in event_types
    assert "debate" in event_types
    assert "signal" in event_types
    assert "complete" in event_types

    # run_start should be first, complete should be last
    assert collector.events[0][0] == "run_start"
    assert collector.events[-1][0] == "complete"

    # Should have multiple agent_status events (running + completed pairs)
    status_events = [e for e in collector.events if e[0] == "agent_status"]
    assert len(status_events) >= 2  # at least one agent with running+completed


def test_engine_parallel_tier1(config_file):
    """dispatch_parallel_fn should be used for Tier 1 analysts when provided."""
    engine = RunEngine(config_path=config_file)
    parallel_called = {"called": False, "args": []}

    def mock_parallel(tasks):
        parallel_called["called"] = True
        parallel_called["args"] = tasks
        return [f"[Parallel response from {t[0]}]" for t in tasks]

    # Need at least 2 analysts for parallel to kick in
    engine.config["analysis"]["analysts"] = ["market", "news"]

    # Create the missing news-analyst.md
    agents_dir = engine.config["paths"]["agents_dir"]
    news_path = os.path.join(agents_dir, "news-analyst.md")
    if not os.path.exists(news_path):
        with open(news_path, "w") as f:
            f.write("---\nname: news-analyst\n---\n# news-analyst\n"
                    "## Default Strategy Prompt\nYou are news-analyst.\n")

    result = engine.run(
        "NVDA", "2026-03-27",
        dispatch_fn=_stub_dispatch,
        dispatch_parallel_fn=mock_parallel,
    )

    assert parallel_called["called"] is True
    assert len(parallel_called["args"]) == 2
    assert result.signal in ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]


def test_engine_persists_run_to_db(config_file):
    """Successful run should persist run, reports, and debates to SQLite."""
    from openclaw.database import get_db

    engine = RunEngine(config_path=config_file)
    result = engine.run("NVDA", "2026-03-27", dispatch_fn=_stub_dispatch)

    assert result.run_id  # Should have a run_id

    db_path = engine.config["paths"]["database"]
    with get_db(db_path) as conn:
        run_row = conn.execute("SELECT * FROM runs WHERE id = ?", (result.run_id,)).fetchone()
        reports = conn.execute("SELECT * FROM reports WHERE run_id = ?", (result.run_id,)).fetchall()
        debates = conn.execute("SELECT * FROM debates WHERE run_id = ?", (result.run_id,)).fetchall()

    assert run_row is not None
    assert run_row["status"] == "completed"
    assert run_row["signal"] == result.signal
    assert run_row["ticker"] == "NVDA"
    assert len(reports) > 0  # At least the market report
    assert len(debates) > 0  # At least the investment debate


def test_engine_config_singleton(config_file):
    """CC-9: run() should set the config singleton."""
    engine = RunEngine(config_path=config_file)
    engine.run("NVDA", "2026-03-27", dispatch_fn=_stub_dispatch)

    config = get_config()
    assert config is not None
    assert config["strategy"] == "default"


def test_engine_timeout(config_file):
    """CC-4b: Slow dispatch should raise TimeoutError."""
    import time

    engine = RunEngine(config_path=config_file)
    # Set very short timeout
    engine.config["analysis"]["agent_timeout_seconds"] = 0.1

    def slow_dispatch(agent_name, prompt, model):
        time.sleep(5)
        return "should not reach here"

    with pytest.raises(TimeoutError, match="timed out"):
        engine.run("NVDA", "2026-03-27", dispatch_fn=slow_dispatch)


def test_engine_partial_state_saved_on_error(config_file, tmp_path):
    """Partial state should be saved to SQLite when a tier fails."""
    from openclaw.database import get_db

    engine = RunEngine(config_path=config_file)

    def failing_dispatch(agent_name, prompt, model):
        if "bull" in agent_name:
            raise ValueError("Simulated bull failure")
        return f"[Response from {agent_name}]"

    with pytest.raises(ValueError, match="bull failure"):
        engine.run("NVDA", "2026-03-27", dispatch_fn=failing_dispatch)

    # Check that the run was marked as failed in the database
    db_path = engine.config["paths"]["database"]
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT status, error_message FROM runs WHERE ticker = 'NVDA' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

    assert row is not None
    assert row["status"] == "failed"
    assert "bull failure" in row["error_message"]

    # Check that Tier 1 reports were persisted before failure
    with get_db(db_path) as conn:
        reports = conn.execute(
            "SELECT section_name FROM reports WHERE run_id = (SELECT id FROM runs ORDER BY created_at DESC LIMIT 1)"
        ).fetchall()

    assert len(reports) > 0  # Tier 1 completed before Tier 2 failed


def test_parse_frontmatter(config_file):
    """Frontmatter parser should extract tools, tier, memory from .md files."""
    engine = RunEngine(config_path=config_file)
    agents_dir = engine.config["paths"]["agents_dir"]

    # Write an agent .md with full frontmatter
    md_path = os.path.join(agents_dir, "test-agent.md")
    with open(md_path, "w") as f:
        f.write("---\nname: test-agent\nmodel: claude-opus-4-6\n"
                "tools: [get_stock_data, get_indicators]\n"
                "tools_jadecap: [get_ict_levels, fetch_live_price]\n"
                "memory: bull_memory\ntier: deep\n"
                "input: [trade_date, company_of_interest]\noutput: test_report\n"
                "---\n# Test Agent\n## Default Strategy Prompt\nYou are a test.\n")

    fm = engine._parse_frontmatter(md_path)
    assert fm["name"] == "test-agent"
    assert fm["model"] == "claude-opus-4-6"
    assert fm["tools"] == ["get_stock_data", "get_indicators"]
    assert fm["tools_jadecap"] == ["get_ict_levels", "fetch_live_price"]
    assert fm["memory"] == "bull_memory"
    assert fm["tier"] == "deep"
    assert fm["output"] == "test_report"


def test_parse_frontmatter_missing_file():
    """Missing .md file should return empty dict."""
    fm = RunEngine._parse_frontmatter("/nonexistent/path.md")
    assert fm == {}


def test_prefetch_tool_data_empty():
    """Empty tool list should return empty dict."""
    engine = RunEngine.__new__(RunEngine)
    engine.config = {"strategy": "default"}
    result = engine._prefetch_tool_data([], "NVDA", "2026-03-28")
    assert result == {}


def test_analyst_prompt_includes_data_section(config_file):
    """Analyst prompt should include PRE-FETCHED DATA when tools are declared."""
    import openclaw.tools  # ensure tools are registered

    engine = RunEngine(config_path=config_file)
    agents_dir = engine.config["paths"]["agents_dir"]

    # Write analyst with tools that will fail (no real API) but gracefully
    md_path = os.path.join(agents_dir, "market-analyst.md")
    with open(md_path, "w") as f:
        f.write("---\nname: market-analyst\ntools: [get_stock_data]\ntier: quick\n---\n"
                "# Market Analyst\n## Default Strategy Prompt\nAnalyze the market.\n")

    prompt = engine._build_analyst_prompt(agents_dir, "market-analyst", "default", "NVDA", "2026-03-28")
    # Should contain the prompt text
    assert "Analyze the market" in prompt
    assert "NVDA" in prompt
    # Tool data section should be present (even if data unavailable)
    assert "PRE-FETCHED DATA" in prompt or "Data unavailable" in prompt or "get_stock_data" in prompt
