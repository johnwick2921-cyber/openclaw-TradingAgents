"""Background runner for TradingAgents analysis.

Wraps TradingAgentsGraph.propagate() in a background thread and streams
events to connected WebSocket clients via an in-memory event buffer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import LLMResult

from cli.stats_handler import StatsCallbackHandler
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from webui.backend.database import get_db

logger = logging.getLogger(__name__)


def _register_deepseek_provider():
    """Register DeepSeek as an OpenAI-compatible provider.

    Patches the factory and OpenAI client at runtime so that
    ``create_llm_client("deepseek", ...)`` works correctly.
    Only needs to be called once per process.
    """
    from tradingagents.llm_clients import openai_client, factory

    if getattr(factory.create_llm_client, '_deepseek_patched', False):
        return

    # 1. Add to _PROVIDER_CONFIG so get_llm() uses the right URL/key
    #    and does NOT set use_responses_api
    if "deepseek" not in openai_client._PROVIDER_CONFIG:
        openai_client._PROVIDER_CONFIG["deepseek"] = (
            "https://api.deepseek.com/v1",
            "DEEPSEEK_API_KEY",
        )

    # 2. Patch the factory to recognize "deepseek"
    _original = factory.create_llm_client

    def _patched_create(provider, model, base_url=None, **kwargs):
        if provider.lower() == "deepseek":
            return openai_client.OpenAIClient(
                model, base_url, provider="deepseek", **kwargs
            )
        return _original(provider, model, base_url, **kwargs)

    factory.create_llm_client = _patched_create
    _patched_create._deepseek_patched = True

    # 3. Also patch the module-level import in trading_graph
    import tradingagents.graph.trading_graph as tg_mod
    tg_mod.create_llm_client = _patched_create


# ---------------------------------------------------------------------------
# Constants for chunk parsing (mirrored from cli/main.py)
# ---------------------------------------------------------------------------

# Map common futures symbols to yfinance format (module-level constant)
_FUTURES_MAP: Dict[str, str] = {
    "NQ": "NQ=F", "MNQ": "MNQ=F", "ES": "ES=F", "MES": "MES=F",
    "YM": "YM=F", "MYM": "MYM=F", "RTY": "RTY=F", "M2K": "M2K=F",
    "CL": "CL=F", "GC": "GC=F", "SI": "SI=F", "ZB": "ZB=F",
}

ANALYST_ORDER = ["market", "social", "news", "fundamentals"]

ANALYST_AGENT_NAMES: Dict[str, str] = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}

ANALYST_REPORT_MAP: Dict[str, str] = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}


# ---------------------------------------------------------------------------
# WebUI callback handler
# ---------------------------------------------------------------------------


class WebUICallbackHandler(StatsCallbackHandler):
    """Callback handler that extends StatsCallbackHandler with cancel support
    and event emission for the Web UI.

    Events are pushed into the RunnerManager event buffer so they can be
    forwarded to WebSocket clients in real time.
    """

    def __init__(self, runner: "RunnerManager") -> None:
        super().__init__()
        self._runner = runner

    # -- Cancel gate ----------------------------------------------------------

    def _check_cancel(self) -> None:
        """Raise RuntimeError if the current run has been cancelled."""
        if self._runner.cancel_event.is_set():
            raise RuntimeError("Run cancelled")

    # -- LLM callbacks --------------------------------------------------------

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        self._check_cancel()
        super().on_llm_start(serialized, prompts, **kwargs)

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        **kwargs: Any,
    ) -> None:
        self._check_cancel()
        super().on_chat_model_start(serialized, messages, **kwargs)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        super().on_llm_end(response, **kwargs)
        stats = self.get_stats()
        self._runner.add_event({
            "type": "token_stats",
            "data": stats,
        })

    # -- Tool callbacks -------------------------------------------------------

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        super().on_tool_start(serialized, input_str, **kwargs)
        tool_name = serialized.get("name", "unknown")
        self._runner.add_event({
            "type": "tool_call",
            "data": {"tool_name": tool_name, "input": input_str[:500]},
        })

    # -- Chain callbacks (agent lifecycle) ------------------------------------

    def on_chain_start(
        self,
        serialized: Dict[str, Any] = None,
        inputs: Dict[str, Any] = None,
        **kwargs: Any,
    ) -> None:
        self._check_cancel()
        agent_name = (serialized or {}).get("name")
        if agent_name:
            self._runner.add_event({
                "type": "agent_status",
                "data": {"agent": agent_name, "status": "running"},
            })

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        # Chain-end does not carry the serialized dict with a name reliably,
        # so we rely on chunk parsing for fine-grained agent status tracking.
        pass


# ---------------------------------------------------------------------------
# RunnerManager
# ---------------------------------------------------------------------------


class RunnerManager:
    """Manages a single active analysis run.

    Only one run may be active at a time.  The manager holds an event buffer
    that WebSocket connections read from, supporting reconnect replay via
    ``get_events(since_id)``.
    """

    def __init__(self) -> None:
        self.active_run_id: Optional[str] = None
        self.events: List[Dict[str, Any]] = []
        self.cancel_event: threading.Event = threading.Event()
        self.ws_connections: Set[Any] = set()

        self._thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Run parameters (set by start_run)
        self._config_dict: Dict[str, Any] = {}
        self._ticker: str = ""
        self._trade_date: str = ""
        self._selected_analysts: List[str] = []

    # -- Public properties ----------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Return True if a run is currently executing."""
        if self._thread is not None and self._thread.is_alive():
            return True
        # Clean up dead thread reference so new runs aren't blocked
        if self._thread is not None and not self._thread.is_alive():
            self._thread = None
        return False

    def force_reset(self) -> None:
        """Force-reset the runner state. Use when a run is stuck."""
        self._thread = None
        self.active_run_id = None
        self.events.clear()
        self.cancel_event.clear()

    # -- Event buffer ---------------------------------------------------------

    def add_event(self, event_dict: Dict[str, Any]) -> None:
        """Append an event to the buffer and schedule broadcast to WebSocket
        connections.

        Each event is assigned a monotonically increasing ``id`` and a
        timestamp.
        """
        with self._lock:
            event_dict["id"] = len(self.events) + 1
            event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
            event_dict["run_id"] = self.active_run_id
            self.events.append(event_dict)

        # Broadcast to connected WebSocket clients asynchronously
        self._schedule_broadcast(event_dict)

    def get_events(self, since_id: int = 0) -> List[Dict[str, Any]]:
        """Return all events with ``id > since_id``.

        This enables reconnect replay: a client that disconnects and
        reconnects can pass ``last_event_id`` to catch up.
        """
        with self._lock:
            return [e for e in self.events if e.get("id", 0) > since_id]

    # -- Run lifecycle --------------------------------------------------------

    def start_run(self, run_id: str, config_dict: Dict[str, Any]) -> None:
        """Start a new analysis run in a background thread.

        Args:
            run_id: Unique identifier for this run (UUID).
            config_dict: Run parameters including ticker, trade_date,
                selected_analysts, and LLM configuration.

        Raises:
            RuntimeError: If another run is already in progress.
        """
        if self.is_running:
            raise RuntimeError(
                f"A run is already in progress (run_id={self.active_run_id})"
            )

        # Reset state
        self.active_run_id = run_id
        self.events.clear()
        self.cancel_event.clear()

        # Store run params
        self._config_dict = config_dict
        raw_ticker = config_dict["ticker"].upper().strip()
        self._ticker = _FUTURES_MAP.get(raw_ticker, config_dict["ticker"])
        self._trade_date = config_dict["trade_date"]
        self._selected_analysts = config_dict.get(
            "selected_analysts", ["market", "social", "news", "fundamentals"]
        )

        # Capture the running event loop for async broadcasts
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        self.add_event({
            "type": "run_started",
            "data": {
                "run_id": run_id,
                "ticker": self._ticker,
                "trade_date": self._trade_date,
                "selected_analysts": self._selected_analysts,
            },
        })

        self._thread = threading.Thread(
            target=self._execute_run,
            name=f"run-{run_id}",
            daemon=True,
        )
        self._thread.start()

    def cancel_run(self) -> bool:
        """Signal the active run to cancel.

        The callback handler checks the cancel event on every ``on_llm_start``
        and raises RuntimeError to abort the graph execution.

        Returns:
            True if a cancel was signalled, False if no run was active.
        """
        if not self.is_running:
            return False
        self.cancel_event.set()
        self.add_event({"type": "run_cancelling", "data": {}})
        return True

    # -- Internal -------------------------------------------------------------

    def _build_config(self) -> Dict[str, Any]:
        """Build a full TradingAgentsGraph config dict from run parameters."""
        cfg = DEFAULT_CONFIG.copy()

        cfg["quick_think_llm"] = self._config_dict.get(
            "quick_model", DEFAULT_CONFIG["quick_think_llm"]
        )
        cfg["deep_think_llm"] = self._config_dict.get(
            "deep_model", DEFAULT_CONFIG["deep_think_llm"]
        )
        provider = self._config_dict.get(
            "provider", DEFAULT_CONFIG["llm_provider"]
        ).lower()

        # DeepSeek uses OpenAI-compatible Chat Completions API.
        if provider == "deepseek":
            _register_deepseek_provider()
            # Ensure the env var is loaded from .env
            from dotenv import load_dotenv
            load_dotenv(os.path.join(
                os.path.dirname(__file__), "..", "..", ".env"
            ))
            cfg["llm_provider"] = "deepseek"
        else:
            cfg["llm_provider"] = provider
            cfg["backend_url"] = self._config_dict.get(
                "backend_url", DEFAULT_CONFIG["backend_url"]
            )
        cfg["max_debate_rounds"] = self._config_dict.get(
            "max_debate_rounds", DEFAULT_CONFIG["max_debate_rounds"]
        )
        cfg["max_risk_discuss_rounds"] = self._config_dict.get(
            "max_risk_discuss_rounds", DEFAULT_CONFIG["max_risk_discuss_rounds"]
        )

        # Data vendor overrides
        if "data_vendors" in self._config_dict:
            cfg["data_vendors"] = {
                **DEFAULT_CONFIG["data_vendors"],
                **self._config_dict["data_vendors"],
            }
        if "tool_vendors" in self._config_dict:
            cfg["tool_vendors"] = {
                **DEFAULT_CONFIG.get("tool_vendors", {}),
                **self._config_dict["tool_vendors"],
            }

        # Pass strategy key so setup.py knows to use jadecap agents
        strategy = self._config_dict.get("strategy", "default")
        if strategy and strategy != "default":
            cfg["strategy"] = strategy

        # For JadeCap futures strategy, only market + news are useful
        if cfg.get("strategy") in ("jadecap", "jadecap_ict"):
            self._selected_analysts = [a for a in self._selected_analysts if a in ("market", "news")]

        # Map effort to provider-specific key
        effort = self._config_dict.get("effort")
        if effort:
            provider = cfg["llm_provider"]
            if provider == "google":
                cfg["google_thinking_level"] = effort
            elif provider == "openai":
                cfg["openai_reasoning_effort"] = effort
            elif provider == "anthropic":
                cfg["anthropic_effort"] = effort

        return cfg

    def _execute_run(self) -> None:
        """Run the analysis graph in a background thread.

        Streams chunks from ``graph.graph.stream()``, parses them into
        events, and saves results to SQLite on completion.
        """
        run_id = self.active_run_id
        start_time = time.monotonic()

        try:
            config = self._build_config()

            # Apply saved strategy settings to jadecap_config module globals
            # so all agents see the UI values instead of hardcoded defaults
            if config.get("strategy") in ("jadecap", "jadecap_ict"):
                from tradingagents.jadecap_config import apply_settings
                strategy_cfg = self._config_dict.get("strategy_config", {})
                if isinstance(strategy_cfg, str):
                    import json as _json
                    try:
                        strategy_cfg = _json.loads(strategy_cfg)
                    except (ValueError, TypeError):
                        strategy_cfg = {}
                apply_settings(strategy_cfg)

            callback_handler = WebUICallbackHandler(self)

            graph = TradingAgentsGraph(
                selected_analysts=self._selected_analysts,
                debug=True,
                config=config,
                callbacks=[callback_handler],
            )

            # Inject saved memories from SQLite into the graph's BM25 instances
            try:
                from webui.backend.memory_bridge import memory_bridge
                _mem_map = {
                    "bull": "bull_memory",
                    "bear": "bear_memory",
                    "trader": "trader_memory",
                    "invest_judge": "invest_judge_memory",
                    "portfolio_manager": "portfolio_manager_memory",
                }
                for agent_key, attr_name in _mem_map.items():
                    bridge_mem = memory_bridge.get_memory(agent_key)
                    if bridge_mem.documents:
                        graph_mem = getattr(graph, attr_name, None)
                        if graph_mem is not None:
                            pairs = list(zip(bridge_mem.documents, bridge_mem.recommendations))
                            graph_mem.add_situations(pairs)
                            logger.info(
                                "Injected %d memories into %s", len(pairs), attr_name
                            )
            except Exception as e:
                logger.warning("Failed to inject memories: %s", e)

            # Initialise state and stream
            init_state = graph.propagator.create_initial_state(
                self._ticker, self._trade_date
            )
            args = graph.propagator.get_graph_args(callbacks=[callback_handler])

            trace: List[Dict[str, Any]] = []
            report_sections: Dict[str, Optional[str]] = {}

            for chunk in graph.graph.stream(init_state, **args):
                if self.cancel_event.is_set():
                    raise RuntimeError("Run cancelled")

                # -- Parse chunk following cli/main.py logic --

                # Process messages
                if chunk.get("messages") and len(chunk["messages"]) > 0:
                    last_msg = chunk["messages"][-1]
                    content = _extract_content(last_msg)
                    if content:
                        self.add_event({
                            "type": "message",
                            "data": {
                                "content": content[:2000],
                                "message_type": _classify_message(last_msg),
                            },
                        })

                    # Tool calls embedded in AI messages
                    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                        for tc in last_msg.tool_calls:
                            name = tc["name"] if isinstance(tc, dict) else tc.name
                            tc_args = tc["args"] if isinstance(tc, dict) else tc.args
                            self.add_event({
                                "type": "tool_call_detail",
                                "data": {"tool_name": name, "args": tc_args},
                            })

                # Update analyst statuses
                self._update_analyst_statuses(chunk, report_sections)

                # Investment debate
                if chunk.get("investment_debate_state"):
                    self._handle_investment_debate(chunk["investment_debate_state"], report_sections)

                # Trader plan — only emit if new
                trader_content = chunk.get("trader_investment_plan")
                if trader_content and trader_content != report_sections.get("trader_investment_plan"):
                    report_sections["trader_investment_plan"] = trader_content
                    self.add_event({
                        "type": "report_section",
                        "data": {
                            "section": "trader_investment_plan",
                            "content": trader_content,
                        },
                    })
                    self.add_event({
                        "type": "agent_status",
                        "data": {"agent": "Trader", "status": "completed"},
                    })
                    self.add_event({
                        "type": "agent_status",
                        "data": {"agent": "Aggressive Analyst", "status": "in_progress"},
                    })

                # Risk debate
                if chunk.get("risk_debate_state"):
                    self._handle_risk_debate(chunk["risk_debate_state"], report_sections)

                trace.append(chunk)

            # -- Analysis complete -------------------------------------------
            if not trace:
                raise RuntimeError("Analysis produced no output")

            final_state = trace[-1]
            duration = time.monotonic() - start_time
            decision = graph.process_signal(final_state.get("final_trade_decision", ""))

            stats = callback_handler.get_stats()

            # Save to database
            self._save_results(
                run_id=run_id,
                final_state=final_state,
                decision=decision,
                duration=duration,
                stats=stats,
            )

            # Use the framework's built-in reflect_and_remember to save memories
            # Pass 0 as returns since we don't know P&L yet
            try:
                graph.reflect_and_remember(0)
                logger.info("reflect_and_remember completed for run %s", run_id)
                # Persist the in-memory BM25 memories to SQLite
                self._persist_memories_to_db(run_id, graph)
            except Exception as e:
                logger.warning("reflect_and_remember failed: %s", e)

            self.add_event({
                "type": "complete",
                "data": {
                    "run_id": run_id,
                    "signal": decision,
                    "duration_seconds": round(duration, 2),
                    "stats": stats,
                },
            })

        except RuntimeError as exc:
            duration = time.monotonic() - start_time
            is_cancel = "cancelled" in str(exc).lower()
            status = "cancelled" if is_cancel else "failed"
            error_msg = str(exc)

            logger.warning("Run %s %s: %s", run_id, status, error_msg)

            self._save_failure(run_id, status, error_msg, duration)
            self.add_event({
                "type": "failed" if not is_cancel else "cancelled",
                "data": {"run_id": run_id, "error": error_msg},
            })

        except Exception as exc:
            duration = time.monotonic() - start_time
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.exception("Run %s failed with unexpected error", run_id)

            self._save_failure(run_id, "failed", error_msg, duration)
            self.add_event({
                "type": "failed",
                "data": {"run_id": run_id, "error": error_msg},
            })

    # -- Chunk parsing helpers -----------------------------------------------

    def _update_analyst_statuses(
        self,
        chunk: Dict[str, Any],
        report_sections: Dict[str, Optional[str]],
    ) -> None:
        """Update analyst statuses based on accumulated report state.

        Mirrors the logic from cli/main.py ``update_analyst_statuses()``.
        """
        found_active = False

        for analyst_key in ANALYST_ORDER:
            if analyst_key not in self._selected_analysts:
                continue

            agent_name = ANALYST_AGENT_NAMES[analyst_key]
            report_key = ANALYST_REPORT_MAP[analyst_key]

            # Capture new report content — only emit if it's genuinely new
            new_content = chunk.get(report_key)
            if new_content and new_content != report_sections.get(report_key):
                report_sections[report_key] = new_content
                self.add_event({
                    "type": "report_section",
                    "data": {"section": report_key, "content": new_content},
                })

            has_report = bool(report_sections.get(report_key))

            if has_report:
                self.add_event({
                    "type": "agent_status",
                    "data": {"agent": agent_name, "status": "completed"},
                })
            elif not found_active:
                self.add_event({
                    "type": "agent_status",
                    "data": {"agent": agent_name, "status": "in_progress"},
                })
                found_active = True
            else:
                self.add_event({
                    "type": "agent_status",
                    "data": {"agent": agent_name, "status": "pending"},
                })

        # All analysts done => transition to research team
        if not found_active and self._selected_analysts:
            self.add_event({
                "type": "agent_status",
                "data": {"agent": "Bull Researcher", "status": "in_progress"},
            })

    def _handle_investment_debate(
        self,
        debate_state: Dict[str, Any],
        report_sections: Dict[str, Optional[str]],
    ) -> None:
        """Parse investment debate state and emit events."""
        bull_hist = (debate_state.get("bull_history") or "").strip()
        bear_hist = (debate_state.get("bear_history") or "").strip()
        judge = (debate_state.get("judge_decision") or "").strip()

        # Only emit if content has changed since last event
        if bull_hist and bull_hist != report_sections.get("_bull_hist"):
            report_sections["_bull_hist"] = bull_hist
            self.add_event({
                "type": "agent_status",
                "data": {"agent": "Bull Researcher", "status": "completed"},
            })
            self.add_event({
                "type": "report_section",
                "data": {"section": "bull_analysis", "content": f"### Bull Researcher Analysis\n{bull_hist}"},
            })
            # Bear is next
            self.add_event({
                "type": "agent_status",
                "data": {"agent": "Bear Researcher", "status": "in_progress"},
            })

        if bear_hist and bear_hist != report_sections.get("_bear_hist"):
            report_sections["_bear_hist"] = bear_hist
            self.add_event({
                "type": "agent_status",
                "data": {"agent": "Bear Researcher", "status": "completed"},
            })
            self.add_event({
                "type": "report_section",
                "data": {"section": "bear_analysis", "content": f"### Bear Researcher Analysis\n{bear_hist}"},
            })

        if judge and judge != report_sections.get("_judge"):
            report_sections["_judge"] = judge
            content = f"### Research Manager Decision\n{judge}"
            report_sections["investment_plan"] = content
            self.add_event({
                "type": "report_section",
                "data": {"section": "investment_plan", "content": content},
            })
            for agent in ("Bull Researcher", "Bear Researcher", "Research Manager"):
                self.add_event({
                    "type": "agent_status",
                    "data": {"agent": agent, "status": "completed"},
                })
            self.add_event({
                "type": "agent_status",
                "data": {"agent": "Trader", "status": "in_progress"},
            })

    def _handle_risk_debate(
        self,
        risk_state: Dict[str, Any],
        report_sections: Dict[str, Optional[str]],
    ) -> None:
        """Parse risk debate state and emit events."""
        agg_hist = (risk_state.get("aggressive_history") or "").strip()
        con_hist = (risk_state.get("conservative_history") or "").strip()
        neu_hist = (risk_state.get("neutral_history") or "").strip()
        judge = (risk_state.get("judge_decision") or "").strip()

        if agg_hist and agg_hist != report_sections.get("_agg_hist"):
            report_sections["_agg_hist"] = agg_hist
            self.add_event({
                "type": "agent_status",
                "data": {"agent": "Aggressive Analyst", "status": "in_progress"},
            })
            content = f"### Aggressive Analyst Analysis\n{agg_hist}"
            report_sections["final_trade_decision"] = content
            self.add_event({
                "type": "report_section",
                "data": {"section": "final_trade_decision", "content": content},
            })

        if con_hist and con_hist != report_sections.get("_con_hist"):
            report_sections["_con_hist"] = con_hist
            self.add_event({
                "type": "agent_status",
                "data": {"agent": "Conservative Analyst", "status": "in_progress"},
            })
            content = f"### Conservative Analyst Analysis\n{con_hist}"
            report_sections["final_trade_decision"] = content
            self.add_event({
                "type": "report_section",
                "data": {"section": "final_trade_decision", "content": content},
            })

        if neu_hist and neu_hist != report_sections.get("_neu_hist"):
            report_sections["_neu_hist"] = neu_hist
            self.add_event({
                "type": "agent_status",
                "data": {"agent": "Neutral Analyst", "status": "in_progress"},
            })
            content = f"### Neutral Analyst Analysis\n{neu_hist}"
            report_sections["final_trade_decision"] = content
            self.add_event({
                "type": "report_section",
                "data": {"section": "final_trade_decision", "content": content},
            })

        if judge and judge != report_sections.get("_risk_judge"):
            report_sections["_risk_judge"] = judge
            content = f"### Portfolio Manager Decision\n{judge}"
            report_sections["final_trade_decision"] = content
            self.add_event({
                "type": "report_section",
                "data": {"section": "final_trade_decision", "content": content},
            })
            for agent in ("Aggressive Analyst", "Conservative Analyst",
                          "Neutral Analyst", "Portfolio Manager"):
                self.add_event({
                    "type": "agent_status",
                    "data": {"agent": agent, "status": "completed"},
                })

    # -- Database persistence -------------------------------------------------

    def _save_results(
        self,
        run_id: str,
        final_state: Dict[str, Any],
        decision: str,
        duration: float,
        stats: Dict[str, Any],
    ) -> None:
        """Persist run results to SQLite.

        Runs in the background thread, so we create a new event loop for
        the async database calls.
        """
        print(f"\n>>> _save_results CALLED for {run_id[:12]}... keys={[k for k in final_state.keys() if k != 'messages']}", flush=True)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self._async_save_results(run_id, final_state, decision, duration, stats)
            )
        except Exception as e:
            print(f"\n!!! _save_results FAILED: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            loop.close()

        # Auto-save memories in a SEPARATE event loop to avoid conflicts
        print(f"\n>>> ENTERING _auto_save_memories for {run_id[:12]}...", flush=True)
        self._auto_save_memories(run_id, final_state, decision)
        print(f">>> EXITED _auto_save_memories for {run_id[:12]}", flush=True)

    def _persist_memories_to_db(self, run_id: str, graph) -> None:
        """Sync BM25 memories from the graph to SQLite after reflect_and_remember."""
        import sqlite3
        from webui.backend.database import DB_PATH
        from datetime import datetime as _dt, timezone as _tz
        now = _dt.now(_tz.utc).isoformat()

        mem_map = {
            "bull": graph.bull_memory,
            "bear": graph.bear_memory,
            "trader": graph.trader_memory,
            "invest_judge": graph.invest_judge_memory,
            "portfolio_manager": graph.portfolio_manager_memory,
        }

        db = sqlite3.connect(str(DB_PATH))
        try:
            # Get existing memory count per agent for this run
            existing = db.execute(
                "SELECT agent_name, count(*) FROM memories WHERE run_id = ? GROUP BY agent_name",
                (run_id,)
            ).fetchall()
            existing_map = {r[0]: r[1] for r in existing}

            count = 0
            for agent_name, mem in mem_map.items():
                if existing_map.get(agent_name, 0) > 0:
                    continue  # Already saved for this run
                # Get the latest memory entry (the one just added by reflect_and_remember)
                if mem.documents and mem.recommendations:
                    situation = mem.documents[-1][:2000]
                    recommendation = mem.recommendations[-1][:2000]
                    db.execute(
                        "INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (agent_name, situation, recommendation, run_id, now),
                    )
                    count += 1
            db.commit()
            logger.info("Persisted %d memories to SQLite for run %s", count, run_id)
        except Exception as e:
            logger.warning("Failed to persist memories: %s", e)
        finally:
            db.close()

    def _auto_save_memories(self, run_id: str, final_state: Dict[str, Any], decision: str) -> None:
        """Save memories from completed run to SQLite using sync sqlite3 (no async issues)."""
        import sqlite3
        from datetime import datetime as _dt, timezone as _tz
        from webui.backend.database import DB_PATH

        try:
            situation = "\n\n".join(
                final_state.get(k, "") for k in
                ["market_report", "news_report", "sentiment_report"]
                if final_state.get(k)
            )[:2000]

            if not situation:
                print(f"!!! Auto-save: empty situation for run {run_id[:12]}", flush=True)
                return

            agent_reports = {
                "bull": final_state.get("investment_plan", ""),
                "bear": final_state.get("investment_plan", ""),
                "trader": final_state.get("trader_investment_plan", ""),
                "invest_judge": final_state.get("investment_plan", ""),
                "portfolio_manager": final_state.get("final_trade_decision", ""),
            }

            now = _dt.now(_tz.utc).isoformat()
            db = sqlite3.connect(str(DB_PATH))
            count = 0
            try:
                for agent_name, content in agent_reports.items():
                    if not content:
                        continue
                    recommendation = f"Signal: {decision}. Analysis: {content[:500]}"
                    db.execute(
                        "INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (agent_name, situation, recommendation, run_id, now),
                    )
                    count += 1
                db.commit()
            finally:
                db.close()

            print(f"\n>>> AUTO-SAVED {count} memories to SQLite for run {run_id[:12]}...", flush=True)

            # Also load into BM25 so next run's agents can retrieve them
            try:
                from webui.backend.memory_bridge import memory_bridge
                for agent_name, content in agent_reports.items():
                    if not content:
                        continue
                    recommendation = f"Signal: {decision}. Analysis: {content[:500]}"
                    mem = memory_bridge.get_memory(agent_name)
                    mem.add_situations([(situation, recommendation)])
                print(f">>> Loaded {count} memories into BM25 — agents will use them next run", flush=True)
            except Exception as bm25_err:
                print(f"!!! BM25 load failed (non-fatal, will reload on restart): {bm25_err}", flush=True)

        except Exception as e:
            print(f"\n!!! MEMORY AUTO-SAVE FAILED for run {run_id[:12]}: {e}", flush=True)
            import traceback
            traceback.print_exc()

    async def _async_save_results(
        self,
        run_id: str,
        final_state: Dict[str, Any],
        decision: str,
        duration: float,
        stats: Dict[str, Any],
    ) -> None:
        """Async implementation of result persistence."""
        async with get_db() as db:
            # Update run status
            await db.execute(
                """
                UPDATE runs
                SET status = 'completed',
                    signal = ?,
                    tokens_in = ?,
                    tokens_out = ?,
                    duration_seconds = ?
                WHERE id = ?
                """,
                (
                    decision,
                    stats.get("tokens_in", 0),
                    stats.get("tokens_out", 0),
                    round(duration, 2),
                    run_id,
                ),
            )

            # Save analyst reports
            report_keys = [
                "market_report",
                "sentiment_report",
                "news_report",
                "fundamentals_report",
            ]
            for key in report_keys:
                content = final_state.get(key, "")
                if content:
                    await db.execute(
                        "INSERT INTO reports (run_id, section_name, content) VALUES (?, ?, ?)",
                        (run_id, key, content),
                    )

            # Save trader investment plan
            if final_state.get("trader_investment_plan"):
                await db.execute(
                    "INSERT INTO reports (run_id, section_name, content) VALUES (?, ?, ?)",
                    (run_id, "trader_investment_plan", final_state["trader_investment_plan"]),
                )

            # Save investment plan
            if final_state.get("investment_plan"):
                await db.execute(
                    "INSERT INTO reports (run_id, section_name, content) VALUES (?, ?, ?)",
                    (run_id, "investment_plan", final_state["investment_plan"]),
                )

            # Save final trade decision
            if final_state.get("final_trade_decision"):
                await db.execute(
                    "INSERT INTO reports (run_id, section_name, content) VALUES (?, ?, ?)",
                    (run_id, "final_trade_decision", final_state["final_trade_decision"]),
                )

            # Save investment debate
            inv_debate = final_state.get("investment_debate_state")
            if inv_debate:
                await db.execute(
                    """
                    INSERT INTO debates
                        (run_id, debate_type, full_history, side_a_history,
                         side_b_history, judge_decision)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        "investment",
                        inv_debate.get("history", ""),
                        inv_debate.get("bull_history", ""),
                        inv_debate.get("bear_history", ""),
                        inv_debate.get("judge_decision", ""),
                    ),
                )

            # Save risk debate
            risk_debate = final_state.get("risk_debate_state")
            if risk_debate:
                await db.execute(
                    """
                    INSERT INTO debates
                        (run_id, debate_type, full_history, side_a_history,
                         side_b_history, side_c_history, judge_decision)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        "risk",
                        risk_debate.get("history", ""),
                        risk_debate.get("aggressive_history", ""),
                        risk_debate.get("conservative_history", ""),
                        risk_debate.get("neutral_history", ""),
                        risk_debate.get("judge_decision", ""),
                    ),
                )

            await db.commit()

            # Auto-save memories using the SAME db connection (no separate event loop)
            try:
                from datetime import datetime as _dt, timezone as _tz
                _now = _dt.now(_tz.utc).isoformat()

                situation = "\n\n".join(
                    final_state.get(k, "") for k in
                    ["market_report", "news_report", "sentiment_report"]
                    if final_state.get(k)
                )[:2000]

                if situation:
                    agent_reports = {
                        "bull": final_state.get("investment_plan", ""),
                        "bear": final_state.get("investment_plan", ""),
                        "trader": final_state.get("trader_investment_plan", ""),
                        "invest_judge": final_state.get("investment_plan", ""),
                        "portfolio_manager": final_state.get("final_trade_decision", ""),
                    }
                    mem_count = 0
                    for agent_name, content in agent_reports.items():
                        if not content:
                            continue
                        recommendation = f"Signal: {decision}. Analysis: {content[:500]}"
                        await db.execute(
                            "INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (agent_name, situation, recommendation, run_id, _now),
                        )
                        mem_count += 1
                    await db.commit()
                    logger.info("Auto-saved %d memories for run %s", mem_count, run_id)
            except Exception as mem_err:
                logger.warning("Memory auto-save failed: %s", mem_err)

    def _save_failure(
        self,
        run_id: str,
        status: str,
        error_msg: str,
        duration: float,
    ) -> None:
        """Persist a failed/cancelled run status to SQLite."""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                self._async_save_failure(run_id, status, error_msg, duration)
            )
        finally:
            loop.close()

    async def _async_save_failure(
        self,
        run_id: str,
        status: str,
        error_msg: str,
        duration: float,
    ) -> None:
        async with get_db() as db:
            await db.execute(
                """
                UPDATE runs
                SET status = ?, error_message = ?, duration_seconds = ?
                WHERE id = ?
                """,
                (status, error_msg, round(duration, 2), run_id),
            )
            await db.commit()

    # -- WebSocket broadcast --------------------------------------------------

    def _schedule_broadcast(self, event_dict: Dict[str, Any]) -> None:
        """Schedule an async broadcast of an event to all WebSocket connections.

        If called from the background thread (no running event loop), the
        broadcast is scheduled on the main loop captured at ``start_run()``.
        """
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


# ---------------------------------------------------------------------------
# Helpers for message parsing
# ---------------------------------------------------------------------------


def _extract_content(message: Any) -> Optional[str]:
    """Extract string content from a LangChain message."""
    content = getattr(message, "content", None)
    if content is None:
        return None

    if isinstance(content, str):
        text = content.strip()
        return text if text else None

    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() if text else None

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", "").strip())
            elif isinstance(item, str):
                parts.append(item.strip())
        result = " ".join(p for p in parts if p)
        return result if result else None

    text = str(content).strip()
    return text if text else None


def _classify_message(message: Any) -> str:
    """Classify a LangChain message into a display type string."""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    if isinstance(message, HumanMessage):
        return "User"
    if isinstance(message, ToolMessage):
        return "Data"
    if isinstance(message, AIMessage):
        return "Agent"
    return "System"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

runner_manager = RunnerManager()
