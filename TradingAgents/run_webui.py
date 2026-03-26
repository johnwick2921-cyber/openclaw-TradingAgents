"""Entry point for the TradingAgents Web UI server."""

import os
import sys

# Fix Windows Unicode encoding for libraries that print emoji
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import warnings
import webbrowser
import threading

# Suppress noisy library warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
warnings.filterwarnings("ignore", message=".*reduced quality.*")
import uvicorn

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file for API keys
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    host = os.getenv("WEBUI_HOST", "127.0.0.1")
    port = int(os.getenv("WEBUI_PORT", "8000"))

    dist_dir = os.path.join(os.path.dirname(__file__), "webui", "frontend", "dist")
    if not os.path.exists(dist_dir):
        print("WARNING: Frontend not built yet.")
        print("  Run: cd webui/frontend && npm install && npm run build")
        print("  Or for development: cd webui/frontend && npm run dev")
        print()
        print(f"Starting API-only server on http://{host}:{port}")
    else:
        print(f"Starting TradingAgents Web UI on http://{host}:{port}")

    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://{host}:{port}")

    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        "webui.backend.app:app",
        host=host,
        port=port,
        reload=os.getenv("WEBUI_RELOAD", "").lower() == "true",
        log_level="info",
    )


if __name__ == "__main__":
    main()
