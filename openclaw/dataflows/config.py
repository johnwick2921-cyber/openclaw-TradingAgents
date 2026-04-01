"""Thread-safe config singleton for dataflows.

The RunEngine calls set_config() at the start of each run to bridge
trading-config.json values into this singleton. Dataflow functions
call get_config() to read vendor settings.

If RunEngine hasn't called set_config() yet, get_config() auto-loads
from trading-config.json so direct function calls also use the correct
vendor/key settings.
"""

import json
import logging
import os
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Minimal defaults for dataflows — RunEngine overrides via set_config()
_DATAFLOW_DEFAULTS: Dict = {
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "tool_vendors": {},
    "data_cache_dir": "data_cache",
}

_config: Optional[Dict] = None
_config_lock = threading.Lock()
_loaded_from_file = False


def _find_trading_config() -> Optional[str]:
    """Locate trading-config.json (workspace → cwd → env)."""
    candidates = [
        os.path.join(
            os.environ.get("OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")),
            "trading-config.json",
        ),
        os.path.join(os.getcwd(), "trading-config.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _load_from_file() -> Dict:
    """Load trading-config.json and merge with defaults."""
    cfg = _DATAFLOW_DEFAULTS.copy()
    path = _find_trading_config()
    if path:
        try:
            with open(path) as f:
                file_cfg = json.load(f)
            _deep_update(cfg, file_cfg)
            logger.debug("Loaded config from %s", path)
        except Exception as e:
            logger.warning("Failed to load %s: %s", path, e)
    return cfg


def initialize_config():
    """Initialize the configuration — loads from trading-config.json if available."""
    global _config, _loaded_from_file
    with _config_lock:
        if _config is None:
            _config = _load_from_file()
            _loaded_from_file = True


def set_config(config: Dict):
    """Update the configuration with custom values (thread-safe).

    Uses deep merge so nested dicts (like data_vendors) are merged
    rather than replaced entirely.
    """
    global _config
    with _config_lock:
        if _config is None:
            _config = _load_from_file()
        _deep_update(_config, config)


def _deep_update(base: Dict, override: Dict) -> None:
    """Recursively merge override into base (mutates base)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


def get_config() -> Dict:
    """Get a snapshot of the current configuration (thread-safe).

    Auto-loads from trading-config.json on first access if set_config()
    hasn't been called yet.
    """
    with _config_lock:
        if _config is None:
            initialize_config()
        return _config.copy()


# Initialize with defaults + trading-config.json
initialize_config()
