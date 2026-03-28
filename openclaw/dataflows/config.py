"""Thread-safe config singleton for dataflows.

The RunEngine calls set_config() at the start of each run to bridge
trading-config.json values into this singleton. Dataflow functions
call get_config() to read vendor settings.
"""

import threading
from typing import Dict, Optional

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


def initialize_config():
    """Initialize the configuration with defaults."""
    global _config
    with _config_lock:
        if _config is None:
            _config = _DATAFLOW_DEFAULTS.copy()


def set_config(config: Dict):
    """Update the configuration with custom values (thread-safe)."""
    global _config
    with _config_lock:
        if _config is None:
            _config = _DATAFLOW_DEFAULTS.copy()
        _config.update(config)


def get_config() -> Dict:
    """Get a snapshot of the current configuration (thread-safe)."""
    with _config_lock:
        if _config is None:
            initialize_config()
        return _config.copy()


# Initialize with defaults
initialize_config()
