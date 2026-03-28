"""OpenClaw trading module — subagent-based market analysis pipeline."""

import os

# Load .env for API keys (ALPHA_VANTAGE_API_KEY, DATABENTO_API_KEY, etc.)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — keys must be set in environment

# Ensure UTF-8 output
os.environ.setdefault("PYTHONUTF8", "1")

import logging
logger = logging.getLogger("openclaw")
