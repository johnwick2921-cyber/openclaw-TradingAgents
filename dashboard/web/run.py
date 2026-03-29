"""Entry point for the OpenClaw Web Dashboard.

Usage:
    python -m dashboard.web.run
    # or
    python dashboard/web/run.py
"""

import uvicorn
from dashboard.web.backend.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
