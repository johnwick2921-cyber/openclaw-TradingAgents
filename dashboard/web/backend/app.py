import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dashboard.web.backend.database import init_db
from dashboard.web.backend.routes.config import router as config_router
from dashboard.web.backend.routes.runs import router as runs_router
from dashboard.web.backend.routes.memories import router as memories_router
from dashboard.web.backend.routes.cache import router as cache_router
from dashboard.web.backend.routes.prices import router as prices_router, _ws_router as prices_ws_router
from dashboard.web.backend.ws import router as ws_router
from dashboard.web.backend.routes.trading import router as trading_router

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_FRONTEND_DIST = os.path.join(_PROJECT_ROOT, "frontend", "dist")

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    # Startup
    await init_db()
    # Clean up any runs stuck in "running" from a previous crash
    from dashboard.web.backend.database import get_db
    async with get_db() as db:
        await db.execute(
            "UPDATE runs SET status = 'failed', error_message = 'Server restarted while run was active' "
            "WHERE status = 'running'"
        )
        await db.commit()
    # Load saved memories from SQLite into BM25 instances
    from openclaw.memory import FinancialSituationMemory
    from openclaw.memory_persistence import hydrate_memories
    from dashboard.web.backend.database import DB_PATH
    _memories = {
        "bull_memory": FinancialSituationMemory("bull_memory"),
        "bear_memory": FinancialSituationMemory("bear_memory"),
        "trader_memory": FinancialSituationMemory("trader_memory"),
        "invest_judge_memory": FinancialSituationMemory("invest_judge_memory"),
        "portfolio_manager_memory": FinancialSituationMemory("portfolio_manager_memory"),
    }
    hydrate_memories(_memories, DB_PATH)
    # Capture event loop once at startup for background thread → async bridge
    from dashboard.web.backend.routes.prices import init_event_loop
    init_event_loop()
    # Start Databento live price stream on server startup (not just on WS connect)
    if os.environ.get("DATABENTO_API_KEY"):
        try:
            from dashboard.web.backend.routes.prices import _start_live_stream
            _start_live_stream()
        except Exception:
            pass  # Non-fatal — falls back to Historical
    yield
    # Shutdown (if needed)


app = FastAPI(title="TradingAgents API", lifespan=lifespan)

# CORS — allow the Vite dev server and local API in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:8000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers — WebSocket MUST come before the SPA catch-all
app.include_router(ws_router)
app.include_router(prices_ws_router)  # WebSocket for live price streaming
app.include_router(runs_router)
app.include_router(config_router)
app.include_router(memories_router)
app.include_router(cache_router)
app.include_router(prices_router)
app.include_router(trading_router)


@app.get("/api/health")
async def health_check() -> dict:
    return {"status": "ok", "version": "0.2.2"}


# ---------------------------------------------------------------------------
# Static file serving & SPA catch-all (production)
# ---------------------------------------------------------------------------
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str) -> FileResponse:
        """Serve index.html for any non-API route (SPA catch-all)."""
        from starlette.responses import Response

        # Security: resolve real paths to prevent directory traversal
        abs_dist = os.path.realpath(_FRONTEND_DIST)
        file_path = os.path.realpath(os.path.join(_FRONTEND_DIST, full_path))
        if full_path and file_path.startswith(abs_dist + os.sep) and os.path.isfile(file_path):
            # Assets have hashes in filenames — cache them long
            resp = FileResponse(file_path)
            if "/assets/" in full_path:
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        # index.html — never cache so browser always loads latest build
        resp = FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
