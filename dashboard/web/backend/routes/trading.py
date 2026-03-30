"""Trading monitor API endpoints."""
import os
from typing import Any, Dict
from fastapi import APIRouter
from openclaw.config import load_config, save_config, deep_merge
from openclaw.database import safe_get_db
from openclaw.heartbeat import get_market_phase

router = APIRouter(prefix="/api/trading")

@router.get("/status")
async def get_trading_status() -> dict:
    config = load_config()
    db_path = config.get("paths", {}).get("database", "trading.db")
    phase = get_market_phase(config)
    watchlist_data = []
    last_run = None
    memory_stats = []
    try:
        with safe_get_db(db_path) as conn:
            for ticker in config.get("watchlist", []):
                row = conn.execute("SELECT signal, trade_date, status FROM runs WHERE ticker = ? ORDER BY created_at DESC LIMIT 1", (ticker,)).fetchone()
                outcome = conn.execute("SELECT correct FROM outcomes WHERE ticker = ? ORDER BY created_at DESC LIMIT 1", (ticker,)).fetchone()
                watchlist_data.append({"ticker": ticker, "signal": row["signal"] if row else None, "date": row["trade_date"] if row else None, "status": row["status"] if row else None, "correct": bool(outcome["correct"]) if outcome and outcome["correct"] is not None else None})
            row = conn.execute("SELECT id, ticker, trade_date, strategy, signal, status, duration_seconds, created_at FROM runs ORDER BY created_at DESC LIMIT 1").fetchone()
            if row:
                last_run = dict(row)
            rows = conn.execute("SELECT agent_name, COUNT(*) as count FROM memories GROUP BY agent_name ORDER BY count DESC").fetchall()
            memory_stats = [{"agent": r["agent_name"], "count": r["count"]} for r in rows]
    except Exception:
        pass
    return {"state": "halted" if config.get("halt") else "active", "strategy": config.get("strategy", "default"), "market_phase": phase, "bias": config.get("bias", {"direction": "neutral", "reason": "", "confidence": "medium"}), "watchlist": watchlist_data, "last_run": last_run, "memory_stats": memory_stats, "risk": config.get("risk", {}), "llm": config.get("llm", {}), "analysis": config.get("analysis", {}), "schedule": config.get("schedule", {}), "jadecap": config.get("jadecap", {}) if config.get("strategy") == "jadecap" else None}

@router.put("/bias")
async def set_bias(payload: Dict[str, Any]) -> dict:
    config = load_config()
    config["bias"] = {"direction": payload.get("direction", "neutral"), "reason": payload.get("reason", ""), "confidence": payload.get("confidence", "medium")}
    save_config(config)
    return {"status": "ok", "bias": config["bias"]}

@router.put("/halt")
async def set_halt(payload: Dict[str, Any]) -> dict:
    config = load_config()
    config["halt"] = bool(payload.get("halt", False))
    save_config(config)
    return {"status": "ok", "halt": config["halt"]}

@router.put("/watchlist")
async def set_watchlist(payload: Dict[str, Any]) -> dict:
    config = load_config()
    action = payload.get("action", "set")
    ticker = payload.get("ticker", "").upper().strip()
    if action == "add" and ticker:
        if ticker not in config.get("watchlist", []):
            config.setdefault("watchlist", []).append(ticker)
    elif action == "remove" and ticker:
        config["watchlist"] = [t for t in config.get("watchlist", []) if t != ticker]
    elif action == "set":
        config["watchlist"] = [t.upper().strip() for t in payload.get("tickers", [])]
    save_config(config)
    return {"status": "ok", "watchlist": config["watchlist"]}

@router.put("/risk")
async def set_risk(payload: Dict[str, Any]) -> dict:
    config = load_config()
    config["risk"] = deep_merge(config.get("risk", {}), payload)
    save_config(config)
    return {"status": "ok", "risk": config["risk"]}
