import threading
from typing import Dict, Optional

import tradingagents.default_config as default_config

# Use default config but allow it to be overridden.
# All access is guarded by _config_lock for thread safety.
_config: Optional[Dict] = None
_config_lock = threading.Lock()


def initialize_config():
    """Initialize the configuration with default values."""
    global _config
    with _config_lock:
        if _config is None:
            _config = default_config.DEFAULT_CONFIG.copy()


def set_config(config: Dict):
    """Update the configuration with custom values (thread-safe)."""
    global _config
    with _config_lock:
        if _config is None:
            _config = default_config.DEFAULT_CONFIG.copy()
        _config.update(config)


def get_config() -> Dict:
    """Get a snapshot of the current configuration (thread-safe)."""
    with _config_lock:
        if _config is None:
            initialize_config()
        return _config.copy()


# Initialize with default config
initialize_config()
