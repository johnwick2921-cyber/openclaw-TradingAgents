"""Tests for openclaw.config — the unified config system."""

import json
import os
import tempfile
import pytest

# Add parent to path so openclaw is importable
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openclaw.config import load_config, save_config, deep_merge, get_model_for_agent, SCHEMA_DEFAULTS


def test_load_config_defaults():
    """Loading an empty config should return schema defaults."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        path = f.name
    try:
        config = load_config(path)
        assert config["strategy"] == "default"
        assert config["llm"]["default"] == "gpt-4o"
        assert config["llm"]["deep_think"] == "claude-opus-4-6"
        assert config["llm"]["quick_think"] == "gpt-4o-mini"
        assert config["analysis"]["max_debate_rounds"] == 1
        assert config["data_vendors"]["core_stock_apis"] == "yfinance"
        assert config["halt"] is False
        assert config["paths"]["database"] == "trading.db"
        assert config["schedule"]["market_hours"]["timezone"] == "US/Eastern"
    finally:
        os.unlink(path)


def test_load_config_overrides():
    """User config should override defaults, preserving non-overridden nested fields."""
    user = {"strategy": "jadecap", "llm": {"default": "claude-sonnet-4-6"}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(user, f)
        path = f.name
    try:
        config = load_config(path)
        assert config["strategy"] == "jadecap"
        assert config["llm"]["default"] == "claude-sonnet-4-6"
        # Non-overridden nested fields preserved
        assert config["llm"]["deep_think"] == "claude-opus-4-6"
        assert config["llm"]["quick_think"] == "gpt-4o-mini"
        assert config["llm"]["per_agent"] == {}
    finally:
        os.unlink(path)


def test_load_config_missing_file():
    """Missing config file should return defaults without error."""
    config = load_config("/nonexistent/path/config.json")
    assert config["strategy"] == "default"
    assert config["halt"] is False
    assert config["llm"]["default"] == "gpt-4o"


def test_deep_merge_nested():
    """deep_merge should recursively merge nested dicts."""
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    override = {"a": {"b": 10, "e": 5}}
    result = deep_merge(base, override)
    assert result == {"a": {"b": 10, "c": 2, "e": 5}, "d": 3}


def test_deep_merge_does_not_mutate_base():
    """deep_merge should not modify the base dict."""
    base = {"a": {"b": 1}}
    override = {"a": {"b": 2}}
    deep_merge(base, override)
    assert base["a"]["b"] == 1


def test_deep_merge_override_replaces_non_dict():
    """Non-dict values in override should replace base values entirely."""
    base = {"a": [1, 2, 3]}
    override = {"a": [4, 5]}
    result = deep_merge(base, override)
    assert result["a"] == [4, 5]


def test_save_and_reload(tmp_path):
    """save_config then load_config should roundtrip."""
    path = str(tmp_path / "test.json")
    config = load_config("/nonexistent")
    config["strategy"] = "jadecap"
    config["watchlist"] = ["NVDA", "AAPL"]
    save_config(config, path)

    reloaded = load_config(path)
    assert reloaded["strategy"] == "jadecap"
    assert reloaded["watchlist"] == ["NVDA", "AAPL"]
    # Defaults still present
    assert reloaded["llm"]["default"] == "gpt-4o"


def test_get_model_for_agent_quick_tier():
    """Quick tier agents should use quick_think model."""
    config = SCHEMA_DEFAULTS.copy()
    assert get_model_for_agent(config, "market-analyst", "quick") == "gpt-4o-mini"
    assert get_model_for_agent(config, "bull-researcher", "quick") == "gpt-4o-mini"
    assert get_model_for_agent(config, "aggressive-risk", "quick") == "gpt-4o-mini"


def test_get_model_for_agent_deep_tier():
    """Deep tier agents should use deep_think model."""
    config = SCHEMA_DEFAULTS.copy()
    assert get_model_for_agent(config, "research-manager", "deep") == "claude-opus-4-6"
    assert get_model_for_agent(config, "portfolio-manager", "deep") == "claude-opus-4-6"


def test_get_model_for_agent_per_agent_override():
    """per_agent config should override tier default."""
    config = deep_merge(SCHEMA_DEFAULTS, {
        "llm": {"per_agent": {"bull-researcher": "claude-sonnet-4-6"}}
    })
    # Overridden agent
    assert get_model_for_agent(config, "bull-researcher", "quick") == "claude-sonnet-4-6"
    # Non-overridden agent still uses tier default
    assert get_model_for_agent(config, "bear-researcher", "quick") == "gpt-4o-mini"


def test_get_model_for_agent_fallback_to_default():
    """If no tier key exists, fall back to global default."""
    config = {"llm": {"default": "gpt-4o"}}
    assert get_model_for_agent(config, "market-analyst", "quick") == "gpt-4o"
    assert get_model_for_agent(config, "research-manager", "deep") == "gpt-4o"


def test_market_hours_in_config():
    """Config should have separate stock and futures market hours."""
    config = load_config("/nonexistent")
    hours = config["schedule"]["market_hours"]
    assert hours["stock"]["open"] == "09:30"
    assert hours["stock"]["close"] == "16:00"
    assert hours["futures"]["open"] == "18:00"
    assert hours["futures"]["close"] == "17:00"
    assert hours["timezone"] == "US/Eastern"
    assert hours["use"] == "auto"
