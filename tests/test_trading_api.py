"""Tests for trading config API logic."""
import json, os, pytest
from openclaw.config import load_config, save_config, SCHEMA_DEFAULTS
from openclaw.database import init_db

@pytest.fixture
def config_file(tmp_path):
    config = {"strategy": "default", "watchlist": ["NVDA"], "bias": {"direction": "neutral", "reason": "", "confidence": "medium"}, "halt": False, "risk": {"max_loss_per_trade": 500, "daily_loss_limit": 1000}, "paths": {"database": str(tmp_path / "test.db"), "agents_dir": str(tmp_path / "agents")}}
    path = str(tmp_path / "test-config.json")
    with open(path, "w") as f:
        json.dump(config, f)
    init_db(config["paths"]["database"])
    return path

def test_bias_roundtrip(config_file):
    config = load_config(config_file)
    config["bias"] = {"direction": "bullish", "reason": "NQ displacement", "confidence": "high"}
    save_config(config, config_file)
    reloaded = load_config(config_file)
    assert reloaded["bias"]["direction"] == "bullish"
    assert reloaded["bias"]["reason"] == "NQ displacement"
    assert reloaded["bias"]["confidence"] == "high"

def test_halt_roundtrip(config_file):
    config = load_config(config_file)
    config["halt"] = True
    save_config(config, config_file)
    assert load_config(config_file)["halt"] is True

def test_watchlist_add_remove(config_file):
    config = load_config(config_file)
    assert "NVDA" in config["watchlist"]
    config["watchlist"].append("AAPL")
    save_config(config, config_file)
    assert "AAPL" in load_config(config_file)["watchlist"]
    config["watchlist"] = [t for t in config["watchlist"] if t != "NVDA"]
    save_config(config, config_file)
    r = load_config(config_file)
    assert "NVDA" not in r["watchlist"]
    assert "AAPL" in r["watchlist"]

def test_risk_update(config_file):
    config = load_config(config_file)
    config["risk"]["max_loss_per_trade"] = 750
    save_config(config, config_file)
    r = load_config(config_file)
    assert r["risk"]["max_loss_per_trade"] == 750
    assert r["risk"]["daily_loss_limit"] == 1000

def test_schema_defaults_has_bias():
    assert "bias" in SCHEMA_DEFAULTS
    assert SCHEMA_DEFAULTS["bias"]["direction"] == "neutral"
