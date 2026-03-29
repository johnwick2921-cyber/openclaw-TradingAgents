"""Background runner for the web dashboard.

Runs OpenClaw's RunEngine in a background thread and streams normalized
progress events to connected WebSocket clients through an in-memory buffer.
This is OpenClaw-native: no TradingAgentsGraph and no LangChain callbacks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from openclaw.callbacks import RunCallback
from openclaw.engine import RunEngine

logger = logging.getLogger(__name__)

_FUTURES_MAP: Dict[str, str] = {
    "NQ": "NQ=F", "MNQ": "MNQ=F", "ES": "ES=F", "MES": "MES=F",
    "YM": "YM=F", "MYM": "MYM=F", "RTY": "RTY=F", "M2K": "M2K=F",
    "CL": "CL=F", "GC": "GC=F", "SI": "SI=F", "ZB": "ZB=F",
}

DISPLAY_AGENT_NAMES: Dict[str, str] = {
    "market-analyst": "Market Analyst",
    "social-analyst": "Social Analyst",
    "news-analyst": "News Analyst",
    "fundamentals-analyst": "Fundamentals Analyst",
    "bull-researcher": "Bull Researcher",
    "bear-researcher": "Bear Researcher",
    "research-manager": "Research Manager",
    "trader": "Trader",
    "aggressive-risk": "Aggressive Analyst",
    "conservative-risk": "Conservative Analyst",
    "neutral-risk": "Neutral Analyst",
    "portfolio-manager": "Portfolio Manager",
    "reflection": "Reflection",
}


class WebUICallbackHandler(RunCallback):
    """OpenClaw-native callback adapter that emits dashboard events."""

    def __init__(self, runner: "RunnerManager") -> None:
        self._runner = runner

    def _name(self, agent: str) -> str:
        return DISPLAY_AGENT_NAMES.get(agent, agent)

    def _check_cancel(self) -> None:
        if self._runner.cancel_event.is_set():
            raise RuntimeError("Run cancelled")

    def on_run_start(self, ticker: str, date: str) -> None:
        self._check_cancel()
        self._runner.add_event({
            "type": "run_progress",
            "data": {"ticker": ticker, "trade_date": date, "status": "running"},
        })

    def on_agent_status(self, agent: str, status: str) -> None:
        self._check_cancel()
        self._runner.add_event({
            "type": "agent_status",
            "data": {"agent": self._name(agent), "status": status},
        })

    def on_report_section(self, name: str, content: str) -> None:
        self._runner.add_event({
            "type": "report_section",
            "data": {"section": name, "content": content},
        })

    def on_debate_turn(self, speaker: str, argument: str) -> None:
        self._runner.add_event({
            "type": "debate_turn",
            "data": {"speaker": self._name(speaker), "argument": argument},
        })

    def on_signal(self, signal: str) -> None:
        self._runner.add_event({
            "type": "signal",
            "data": {"signal": signal},
        })

    def on_run_complete(self, result: Any) -> None:
        self._runner.add_event({
            "type": "complete",
            "data": {
                "run_id": getattr(result, "run_id", self._runner.active_run_id),
                "signal": getattr(result, "signal", "HOLD"),
                "duration_seconds": round(getattr(result, "duration_seconds", 0.0), 2),
            },
        })

    def on_error(self, error: Exception) -> None:
        self._runner.add_event({
            "type": "failed",
            "data": {"run_id": self._runner.active_run_id, "error": str(error)},
        })


class RunnerManager:
    """Manages one active analysis run and a replayable event buffer."""

    def __init__(self) -> None:
        self.active_run_id: Optional[str] = None
        self.events: List[Dict[str, Any]] = []
        self.cancel_event: threading.Event = threading.Event()
        self.ws_connections: Set[Any] = set()

        self._thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._config_dict: Dict[str, Any] = {}

    @property
    def is_running(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return True
        if self._thread is not None and not self._thread.is_alive():
            self._thread = None
        return False

    def force_reset(self) -> None:
        self._thread = None
        self.active_run_id = None
        self.events.clear()
        self.cancel_event.clear()

    def add_event(self, event_dict: Dict[str, Any]) -> None:
        with self._lock:
            event_dict["id"] = len(self.events) + 1
            event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
            event_dict["run_id"] = self.active_run_id
            self.events.append(event_dict)
        self._schedule_broadcast(event_dict)

    def get_events(self, since_id: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            return [e for e in self.events if e.get("id", 0) > since_id]

    def start_run(self, run_id: str, config_dict: Dict[str, Any]) -> None:
        if self.is_running:
            raise RuntimeError(f"A run is already in progress (run_id={self.active_run_id})")

        self.active_run_id = run_id
        self.events.clear()
        self.cancel_event.clear()
        self._config_dict = config_dict

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        raw_ticker = str(config_dict.get("ticker", "")).upper().strip()
        mapped_ticker = _FUTURES_MAP.get(raw_ticker, config_dict.get("ticker", raw_ticker))
        self.add_event({
            "type": "run_started",
            "data": {
                "run_id": run_id,
                "ticker": mapped_ticker,
                "trade_date": config_dict.get("trade_date"),
                "selected_analysts": config_dict.get("selected_analysts", []),
            },
        })

        self._thread = threading.Thread(
            target=self._execute_run,
            name=f"run-{run_id}",
            daemon=True,
        )
        self._thread.start()

    def cancel_run(self) -> bool:
        if not self.is_running:
            return False
        self.cancel_event.set()
        self.add_event({"type": "run_cancelling", "data": {}})
        return True

    def _build_engine_config(self) -> Dict[str, Any]:
        engine = RunEngine()
        config = engine.config

        strategy = self._config_dict.get("strategy")
        if strategy:
            config["strategy"] = strategy

        if self._config_dict.get("deep_model") or self._config_dict.get("quick_model"):
            llm = dict(config.get("llm", {}))
            if self._config_dict.get("deep_model"):
                llm["deep_think"] = self._config_dict["deep_model"]
            if self._config_dict.get("quick_model"):
                llm["quick_think"] = self._config_dict["quick_model"]
            config["llm"] = llm

        if self._config_dict.get("max_debate_rounds") is not None:
            config.setdefault("analysis", {})["max_debate_rounds"] = self._config_dict["max_debate_rounds"]
        if self._config_dict.get("max_risk_discuss_rounds") is not None:
            config.setdefault("analysis", {})["max_risk_discuss_rounds"] = self._config_dict["max_risk_discuss_rounds"]
        if self._config_dict.get("selected_analysts"):
            config.setdefault("analysis", {})["analysts"] = self._config_dict["selected_analysts"]

        if self._config_dict.get("data_vendors"):
            config["data_vendors"] = {
                **config.get("data_vendors", {}),
                **self._config_dict["data_vendors"],
            }
        if self._config_dict.get("tool_vendors"):
            config["tool_vendors"] = {
                **config.get("tool_vendors", {}),
                **self._config_dict["tool_vendors"],
            }

        return config

    def _execute_run(self) -> None:
        run_id = self.active_run_id
        start_time = time.monotonic()

        try:
            engine = RunEngine()
            engine.config = self._build_engine_config()

            ticker = str(self._config_dict.get("ticker", "")).upper().strip()
            ticker = _FUTURES_MAP.get(ticker, self._config_dict.get("ticker", ticker))
            trade_date = self._config_dict["trade_date"]
            callback_handler = WebUICallbackHandler(self)

            result = engine.run(
                ticker=ticker,
                date=trade_date,
                callbacks=[callback_handler],
            )

            logger.info(
                "Completed web run %s for %s with signal %s in %.2fs",
                run_id,
                ticker,
                result.signal,
                result.duration_seconds,
            )

        except RuntimeError as exc:
            duration = time.monotonic() - start_time
            is_cancel = "cancelled" in str(exc).lower()
            logger.warning("Run %s %s: %s", run_id, "cancelled" if is_cancel else "failed", exc)
            self.add_event({
                "type": "cancelled" if is_cancel else "failed",
                "data": {"run_id": run_id, "error": str(exc), "duration_seconds": round(duration, 2)},
            })
        except Exception as exc:
            duration = time.monotonic() - start_time
            logger.exception("Run %s failed with unexpected error", run_id)
            self.add_event({
                "type": "failed",
                "data": {"run_id": run_id, "error": f"{type(exc).__name__}: {exc}", "duration_seconds": round(duration, 2)},
            })

    def _schedule_broadcast(self, event_dict: Dict[str, Any]) -> None:
        if not self.ws_connections:
            return

        async def _broadcast() -> None:
            payload = json.dumps(event_dict)
            dead: Set[Any] = set()
            for ws in list(self.ws_connections):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            self.ws_connections -= dead

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast(), self._loop)


runner_manager = RunnerManager()
