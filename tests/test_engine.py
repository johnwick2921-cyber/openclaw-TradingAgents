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
    """CC-3: Partial state should be saved when a tier fails."""
    engine = RunEngine(config_path=config_file)
    call_count = {"n": 0}

    def failing_dispatch(agent_name, prompt, model):
        call_count["n"] += 1
        if "bull" in agent_name:
            raise ValueError("Simulated bull failure")
        return f"[Response from {agent_name}]"

    with pytest.raises(ValueError, match="bull failure"):
        engine.run("NVDA", "2026-03-27", dispatch_fn=failing_dispatch)

    # Check that partial state was written
    results_dir = engine.config["paths"]["results_dir"]
    partial_file = os.path.join(results_dir, "NVDA_2026-03-27_partial.json")
    assert os.path.exists(partial_file)

    with open(partial_file) as f:
        partial = json.load(f)
    assert partial["tier_completed"] == 1  # Tier 1 completed, Tier 2 failed
    assert "market_report" in partial["reports"]
