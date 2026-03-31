"""Unified config: JSON file + schema defaults.
Replaces default_config.py, jadecap_config.py globals, and WebUI settings table.
"""

import json
import os
import copy
from typing import Any, Dict


SCHEMA_DEFAULTS: Dict[str, Any] = {
    "strategy": "stocks",
    "watchlist": [],

    "bias": {
        "direction": "neutral",  # bullish / bearish / neutral
        "reason": "",
        "confidence": "medium",  # low / medium / high
    },

    "llm": {
        "default": "gpt-4o",
        "deep_think": "claude-opus-4-6",
        "quick_think": "gpt-4o-mini",
        "per_agent": {},
    },

    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
        "live_price_data": "auto",
        "macro_news_data": "auto",
    },
    "tool_vendors": {
        "web_search": "auto",
    },

    "analysis": {
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "analysts": ["market", "social", "news", "fundamentals"],
        "agent_timeout_seconds": 300,
    },

    "risk": {
        "max_loss_per_trade": 500,
        "daily_loss_limit": 1000,
        "max_drawdown_pct": 5,
        "max_consecutive_losses": 3,
        "min_risk_reward": 3,
    },

    "jadecap": {
        "active_instrument": "NQ",
        "prop_firm": "apex",
        "hard_close_time": "15:45",
        "atr_stop_multiplier": 1.5,
        "t1_close_pct": 0.5,
        "sessions": {
            "asia": {"start": "20:00", "end": "00:00"},
            "london": {"start": "02:00", "end": "05:00"},
            "ny_am": {"start": "09:30", "end": "11:30"},
            "ny_pm": {"start": "13:00", "end": "16:00"},
        },
        "kill_zones": {
            "ny_am": {"start": "09:30", "end": "11:30"},
            "ny_pm": {"start": "13:00", "end": "16:00"},
            "silver_bullet_1": {"start": "10:00", "end": "11:00"},
            "silver_bullet_2": {"start": "14:00", "end": "15:00"},
        },
        "midday_avoidance": {"start": "11:30", "end": "13:00"},
        "instruments": {
            "NQ": {"ticker": "NQ=F", "point_value": 20, "description": "Nasdaq 100 E-mini Futures"},
            "ES": {"ticker": "ES=F", "point_value": 50, "description": "S&P 500 E-mini Futures"},
            "MNQ": {"ticker": "MNQ=F", "point_value": 2, "description": "Micro Nasdaq Futures"},
        },
    },

    "halt": False,

    "schedule": {
        "pre_session_analysis": False,
        "monitor_interval_min": 30,
        "post_session_reflect": False,
        "market_hours": {
            "stock": {"open": "09:30", "close": "16:00"},
            "futures": {"open": "18:00", "close": "17:00"},
            "timezone": "US/Eastern",
            "use": "auto",
        },
    },

    "paths": {
        "database": "trading.db",
        "memory_dir": "memory",
        "results_dir": "results",
        "agents_dir": "agents/trading",
        "data_cache_dir": "data_cache",
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values win.
    Does NOT mutate base — returns a new dict.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: str = "trading-config.json") -> Dict[str, Any]:
    """Load JSON config file, merge with schema defaults.
    If the file doesn't exist, returns schema defaults.
    """
    user_config: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r") as f:
            user_config = json.load(f)
    return deep_merge(SCHEMA_DEFAULTS, user_config)


def save_config(config: Dict[str, Any], path: str = "trading-config.json") -> None:
    """Save config to JSON file."""
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


def get_model_for_agent(config: Dict[str, Any], agent_name: str, tier: str = "quick") -> str:
    """Resolve which LLM model an agent should use.

    Priority: per_agent override > tier default > global default.

    Args:
        config: The loaded config dict
        agent_name: e.g., "market-analyst", "portfolio-manager"
        tier: "deep" for managers/PM, "quick" for analysts/researchers/debaters
    """
    llm = config.get("llm", {})

    # Check per-agent override first
    per_agent = llm.get("per_agent", {})
    if agent_name in per_agent:
        return per_agent[agent_name]

    # Fall back to tier default
    if tier == "deep":
        return llm.get("deep_think", llm.get("default", "gpt-4o"))

    return llm.get("quick_think", llm.get("default", "gpt-4o"))
