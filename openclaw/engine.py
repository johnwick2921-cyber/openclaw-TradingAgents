"""Unified RunEngine: dispatches subagents in the 4-tier trading pipeline.

Features:
- Error recovery: try/except around each tier, persist partial state
- Parallel Tier 1: dispatch_parallel_fn for analysts
- Timeout: _dispatch_with_timeout using concurrent.futures
- BM25 memory: hydrate on init, inject into prompts, persist after run
- Config bridge: set_dataflow_config() at start of run()
"""

import logging
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from openclaw.config import load_config, save_config, get_model_for_agent
from openclaw.memory import FinancialSituationMemory

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Result of a complete trading analysis run."""
    run_id: str = ""
    ticker: str = ""
    date: str = ""
    signal: str = ""  # BUY/SELL/OVERWEIGHT/UNDERWEIGHT/BULLISH/BEARISH/NEUTRAL
    market_report: str = ""
    news_report: str = ""
    investment_debate: dict = field(default_factory=dict)
    risk_debate: dict = field(default_factory=dict)
    trader_plan: str = ""
    final_decision: str = ""
    duration_seconds: float = 0.0


class RunEngine:
    """Orchestrates the 4-tier trading analysis pipeline via subagent dispatch."""

    def __init__(self, config_path: str = "trading-config.json"):
        self.config_path = os.path.abspath(config_path)
        self.workspace = os.path.dirname(self.config_path)
        self.config = load_config(config_path)
        self._running = False

        self.memories = {
            "market-analyst": FinancialSituationMemory("market-analyst"),
            "news-analyst": FinancialSituationMemory("news-analyst"),
            "bull-researcher": FinancialSituationMemory("bull-researcher"),
            "bear-researcher": FinancialSituationMemory("bear-researcher"),
            "research-manager": FinancialSituationMemory("research-manager"),
            "trader": FinancialSituationMemory("trader"),
            "aggressive-risk": FinancialSituationMemory("aggressive-risk"),
            "conservative-risk": FinancialSituationMemory("conservative-risk"),
            "neutral-risk": FinancialSituationMemory("neutral-risk"),
            "portfolio-manager": FinancialSituationMemory("portfolio-manager"),
        }

        db_path = self._resolve_path(self.config["paths"]["database"])
        if os.path.exists(db_path):
            from openclaw.memory_persistence import hydrate_memories
            hydrate_memories(self.memories, db_path)

        # Clean stub entries from dry runs
        if os.path.exists(db_path):
            try:
                from openclaw.database import get_db
                with get_db(db_path) as conn:
                    conn.execute("DELETE FROM memories WHERE situation LIKE '%Stub response%'")
                    conn.commit()
            except Exception:
                pass

    def _resolve_path(self, p: str) -> str:
        """Resolve a path relative to the workspace root."""
        if os.path.isabs(p):
            return p
        return os.path.join(self.workspace, p)

    def run(
        self,
        ticker: str,
        date: str,
        dispatch_fn: Optional[Callable] = None,
        dispatch_parallel_fn: Optional[Callable] = None,
        callbacks: Optional[list] = None,
        run_id: Optional[str] = None,
    ) -> RunResult:
        from openclaw.dataflows.config import set_config as set_dataflow_config
        set_dataflow_config(self.config)

        if self.config.get("halt"):
            raise RuntimeError("Analysis is halted. Call engine.resume() to re-enable.")

        from openclaw.database import init_db, get_db

        callbacks = callbacks or []
        dispatch = dispatch_fn or self._default_dispatch
        self._running = True
        start_time = datetime.now()

        run_id = run_id or str(uuid.uuid4())[:8]
        db_path = self._resolve_path(self.config["paths"]["database"])
        init_db(db_path)
        now = datetime.now(timezone.utc).isoformat()
        strategy = self.config["strategy"]
        agents_dir = self._resolve_path(self.config["paths"]["agents_dir"])

        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO runs (id, ticker, trade_date, strategy, status, created_at) "
                "VALUES (?, ?, ?, ?, 'running', ?)",
                (run_id, ticker, date, strategy, now),
            )
            conn.commit()

        for cb in callbacks:
            cb.on_run_start(ticker, date)

        try:
            try:
                reports = self._run_tier1_analysts(
                    agents_dir, strategy, ticker, date,
                    dispatch, dispatch_parallel_fn, callbacks,
                )
                self._persist_reports(db_path, run_id, reports)
            except Exception as e:
                self._mark_run_failed(db_path, run_id, str(e), start_time)
                for cb in callbacks:
                    cb.on_error(e)
                raise

            try:
                debate = self._run_debate(
                    agents_dir, strategy, ticker, date, reports, dispatch, callbacks
                )
                self._persist_debate(db_path, run_id, "investment", debate)
            except Exception as e:
                self._mark_run_failed(db_path, run_id, str(e), start_time)
                for cb in callbacks:
                    cb.on_error(e)
                raise

            try:
                investment_plan, trader_plan, risk_debate = self._run_judge_trader_risk(
                    agents_dir, strategy, ticker, date, reports, debate, dispatch, callbacks,
                    dispatch_parallel_fn=dispatch_parallel_fn,
                )
                self._persist_debate(db_path, run_id, "risk", risk_debate,
                                     judge_decision=investment_plan)
                # Persist Tier 3 reports (investment plan + trader plan)
                self._persist_reports(db_path, run_id, {
                    "investment_plan": investment_plan,
                    "trader_plan": trader_plan,
                })
            except Exception as e:
                self._mark_run_failed(db_path, run_id, str(e), start_time)
                for cb in callbacks:
                    cb.on_error(e)
                raise

            try:
                final_decision = self._run_portfolio_manager(
                    agents_dir, strategy, ticker, date, reports, debate,
                    investment_plan, trader_plan, risk_debate, dispatch, callbacks
                )
            except Exception as e:
                self._mark_run_failed(db_path, run_id, str(e), start_time)
                for cb in callbacks:
                    cb.on_error(e)
                raise

            # Persist final decision to SQLite reports table
            self._persist_reports(db_path, run_id, {
                "final_decision": final_decision,
            })

            # Write final_decision.md to results/ folder
            self._write_final_decision(ticker, date, final_decision, run_id)

            signal = self._extract_signal(final_decision)
            self._update_bias_from_signal(signal, ticker, date)
            for cb in callbacks:
                cb.on_signal(signal)

            duration = (datetime.now() - start_time).total_seconds()
            with get_db(db_path) as conn:
                conn.execute(
                    "UPDATE runs SET signal = ?, status = 'completed', duration_seconds = ? WHERE id = ?",
                    (signal, duration, run_id),
                )
                conn.commit()

            result = RunResult(
                run_id=run_id,
                ticker=ticker,
                date=date,
                signal=signal,
                market_report=reports.get("market_report", ""),
                news_report=reports.get("news_report", ""),
                investment_debate=debate,
                risk_debate=risk_debate,
                trader_plan=trader_plan,
                final_decision=final_decision,
                duration_seconds=duration,
            )

            try:
                from openclaw.memory_persistence import persist_memories
                persist_memories(self.memories, db_path, run_id)
            except Exception as exc:
                logger.warning("Failed to persist memories: %s", exc)

            try:
                self._write_agent_memories(result, agents_dir)
            except Exception as exc:
                logger.warning("Failed to write agent memories: %s", exc)

            for cb in callbacks:
                cb.on_run_complete(result)
            return result

        except Exception:
            # on_error already fired in the tier's inner except
            raise
        finally:
            self._running = False

    def _run_tier1_analysts(self, agents_dir, strategy, ticker, date, dispatch, dispatch_parallel_fn, callbacks):
        reports = {}
        analyst_map = {
            "market": ("market-analyst", "market_report"),
            "news": ("news-analyst", "news_report"),
        }
        selected = self.config["analysis"]["analysts"]
        tasks = []
        for analyst_key in selected:
            if analyst_key not in analyst_map:
                continue
            agent_name, report_field = analyst_map[analyst_key]
            frontmatter = self._parse_frontmatter(os.path.join(agents_dir, agent_name, "PROMPT.md"))
            tier = frontmatter.get("tier", "quick") or "quick"
            model = get_model_for_agent(self.config, agent_name, tier)
            prompt = self._build_analyst_prompt(agents_dir, agent_name, strategy, ticker, date)
            tasks.append((agent_name, report_field, prompt, model))

        if dispatch_parallel_fn and len(tasks) > 1:
            for agent_name, _, _, _ in tasks:
                for cb in callbacks:
                    cb.on_agent_status(agent_name, "running")
            parallel_args = [(t[0], t[2], t[3]) for t in tasks]
            responses = dispatch_parallel_fn(parallel_args)
            for (agent_name, report_field, _, _), response in zip(tasks, responses):
                reports[report_field] = response
                for cb in callbacks:
                    cb.on_report_section(report_field, response)
                    cb.on_agent_status(agent_name, "completed")
        else:
            for agent_name, report_field, prompt, model in tasks:
                for cb in callbacks:
                    cb.on_agent_status(agent_name, "running")
                response = self._dispatch_with_timeout(dispatch, agent_name, prompt, model)
                reports[report_field] = response
                for cb in callbacks:
                    cb.on_report_section(report_field, response)
                    cb.on_agent_status(agent_name, "completed")
        return reports

    def _run_debate(self, agents_dir, strategy, ticker, date, reports, dispatch, callbacks):
        max_rounds = self.config["analysis"]["max_debate_rounds"]
        debate = {"history": "", "bull_history": "", "bear_history": "", "count": 0}
        reports_context = self._format_reports(reports)
        for _ in range(max_rounds):
            bull_prompt = self._build_researcher_prompt(agents_dir, "bull-researcher", strategy, ticker, date, reports_context, debate, "bull", reports=reports)
            fm = self._parse_frontmatter(os.path.join(agents_dir, "bull-researcher", "PROMPT.md"))
            model = get_model_for_agent(self.config, "bull-researcher", fm.get("tier", "quick") or "quick")
            for cb in callbacks:
                cb.on_agent_status("bull-researcher", "running")
            bull_response = self._dispatch_with_timeout(dispatch, "bull-researcher", bull_prompt, model)
            debate["bull_history"] += f"\n{bull_response}"
            debate["history"] += f"\nBull Analyst: {bull_response}"
            debate["count"] += 1
            for cb in callbacks:
                cb.on_debate_turn("Bull Analyst", bull_response)
                cb.on_agent_status("bull-researcher", "completed")

            bear_prompt = self._build_researcher_prompt(agents_dir, "bear-researcher", strategy, ticker, date, reports_context, debate, "bear", reports=reports)
            fm = self._parse_frontmatter(os.path.join(agents_dir, "bear-researcher", "PROMPT.md"))
            model = get_model_for_agent(self.config, "bear-researcher", fm.get("tier", "quick") or "quick")
            for cb in callbacks:
                cb.on_agent_status("bear-researcher", "running")
            bear_response = self._dispatch_with_timeout(dispatch, "bear-researcher", bear_prompt, model)
            debate["bear_history"] += f"\n{bear_response}"
            debate["history"] += f"\nBear Analyst: {bear_response}"
            debate["count"] += 1
            for cb in callbacks:
                cb.on_debate_turn("Bear Analyst", bear_response)
                cb.on_agent_status("bear-researcher", "completed")
        return debate

    def _run_judge_trader_risk(self, agents_dir, strategy, ticker, date, reports, debate, dispatch, callbacks, dispatch_parallel_fn=None):
        reports_context = self._format_reports(reports)
        manager_prompt = self._build_prompt_with_context(
            agents_dir, "research-manager", strategy,
            ticker=ticker, date=date,
            reports=reports_context,
            market_report=reports.get("market_report", ""),
            sentiment_report="N/A — analyst not active",
            news_report=reports.get("news_report", ""),
            fundamentals_report="N/A — analyst not active",
            debate_history=debate["history"],
            history=debate["history"],
            bull_history=debate["bull_history"],
            bear_history=debate["bear_history"],
            past_memory_str=self._get_memory_context("research-manager", ticker, date),
        )
        fm = self._parse_frontmatter(os.path.join(agents_dir, "research-manager", "PROMPT.md"))
        model = get_model_for_agent(self.config, "research-manager", fm.get("tier", "deep") or "deep")
        for cb in callbacks:
            cb.on_agent_status("research-manager", "running")
        investment_plan = self._dispatch_with_timeout(dispatch, "research-manager", manager_prompt, model)
        for cb in callbacks:
            cb.on_agent_status("research-manager", "completed")

        trader_prompt = self._build_prompt_with_context(
            agents_dir, "trader", strategy,
            ticker=ticker, date=date,
            reports=reports_context,
            market_research_report=reports.get("market_report", ""),
            market_report=reports.get("market_report", ""),
            sentiment_report="N/A — analyst not active",
            news_report=reports.get("news_report", ""),
            fundamentals_report="N/A — analyst not active",
            investment_plan=investment_plan,
            past_memory_str=self._get_memory_context("trader", ticker, date),
        )
        fm = self._parse_frontmatter(os.path.join(agents_dir, "trader", "PROMPT.md"))
        model = get_model_for_agent(self.config, "trader", fm.get("tier", "quick") or "quick")
        for cb in callbacks:
            cb.on_agent_status("trader", "running")
        trader_plan = self._dispatch_with_timeout(dispatch, "trader", trader_prompt, model)
        for cb in callbacks:
            cb.on_agent_status("trader", "completed")

        max_risk_rounds = self.config["analysis"]["max_risk_discuss_rounds"]
        risk_debate = {"history": "", "aggressive_history": "", "conservative_history": "", "neutral_history": "", "count": 0}
        risk_agents = [("aggressive-risk", "aggressive_history"), ("conservative-risk", "conservative_history"), ("neutral-risk", "neutral_history")]

        for round_num in range(max_risk_rounds):
            # Build prompts for all 3 risk agents
            risk_tasks = []
            for agent_name, history_key in risk_agents:
                prompt = self._build_prompt_with_context(
                    agents_dir, agent_name, strategy,
                    ticker=ticker, date=date,
                    reports=reports_context,
                    market_research_report=reports.get("market_report", ""),
                    market_report=reports.get("market_report", ""),
                    sentiment_report="N/A — analyst not active",
                    news_report=reports.get("news_report", ""),
                    fundamentals_report="N/A — analyst not active",
                    trader_decision=trader_plan,
                    trader_plan=trader_plan,
                    risk_history=risk_debate["history"],
                    history=risk_debate["history"],
                    current_aggressive_response=risk_debate.get("last_aggressive", ""),
                    current_conservative_response=risk_debate.get("last_conservative", ""),
                    current_neutral_response=risk_debate.get("last_neutral", ""),
                )
                fm = self._parse_frontmatter(os.path.join(agents_dir, agent_name, "PROMPT.md"))
                model = get_model_for_agent(self.config, agent_name, fm.get("tier", "quick") or "quick")
                risk_tasks.append((agent_name, history_key, prompt, model))

            # Dispatch all 3 in PARALLEL
            for agent_name, _, _, _ in risk_tasks:
                for cb in callbacks:
                    cb.on_agent_status(agent_name, "running")

            parallel_args = [(t[0], t[2], t[3]) for t in risk_tasks]
            if dispatch_parallel_fn and len(parallel_args) > 1:
                responses = dispatch_parallel_fn(parallel_args)
            else:
                responses = [self._dispatch_with_timeout(dispatch, a, p, m) for a, p, m in parallel_args]

            # Collect results
            for (agent_name, history_key, _, _), response in zip(risk_tasks, responses):
                risk_debate[history_key] += f"\n{response}"
                risk_debate["history"] += f"\n{agent_name}: {response}"
                risk_debate[f"last_{history_key.replace('_history', '')}"] = response
                risk_debate["count"] += 1
                for cb in callbacks:
                    cb.on_debate_turn(agent_name, response)
                    cb.on_agent_status(agent_name, "completed")

        return investment_plan, trader_plan, risk_debate

    def _run_portfolio_manager(self, agents_dir, strategy, ticker, date, reports, debate, investment_plan, trader_plan, risk_debate, dispatch, callbacks):
        reports_context = self._format_reports(reports)
        prompt = self._build_prompt_with_context(
            agents_dir, "portfolio-manager", strategy,
            ticker=ticker, date=date,
            reports=reports_context,
            market_research_report=reports.get("market_report", ""),
            market_report=reports.get("market_report", ""),
            sentiment_report="N/A — analyst not active",
            news_report=reports.get("news_report", ""),
            fundamentals_report="N/A — analyst not active",
            history=risk_debate["history"],
            debate_history=debate["history"],
            investment_plan=investment_plan,
            research_plan=investment_plan,
            trader_plan=trader_plan,
            risk_history=risk_debate["history"],
            aggressive_history=risk_debate["aggressive_history"],
            conservative_history=risk_debate["conservative_history"],
            neutral_history=risk_debate["neutral_history"],
            past_memory_str=self._get_memory_context("portfolio-manager", ticker, date),
        )
        fm = self._parse_frontmatter(os.path.join(agents_dir, "portfolio-manager", "PROMPT.md"))
        model = get_model_for_agent(self.config, "portfolio-manager", fm.get("tier", "deep") or "deep")
        for cb in callbacks:
            cb.on_agent_status("portfolio-manager", "running")
        response = self._dispatch_with_timeout(dispatch, "portfolio-manager", prompt, model)
        for cb in callbacks:
            cb.on_agent_status("portfolio-manager", "completed")
        return response

    def _extract_signal(self, final_decision: str) -> str:
        signals = ["BUY", "SELL", "OVERWEIGHT", "UNDERWEIGHT", "BULLISH", "BEARISH", "NEUTRAL"]
        text_upper = final_decision.upper()

        # Pattern 1: PM format — "Rating: BUY" or "RATING: **BUY**"
        for signal in signals:
            if f"RATING: {signal}" in text_upper or f"RATING: **{signal}**" in text_upper:
                return signal

        # Pattern 2: Trader format — "FINAL TRANSACTION PROPOSAL: **BUY**"
        for signal in signals:
            if f"FINAL TRANSACTION PROPOSAL: **{signal}**" in text_upper:
                return signal

        # Pattern 3: Legacy "NO TRADE" or "HOLD" → map to NEUTRAL
        if "NO TRADE" in text_upper or "NO_TRADE" in text_upper or "HOLD" in text_upper:
            return "NEUTRAL"

        # Pattern 4: Look for signal in last 500 chars only (avoids boilerplate)
        tail = text_upper[-500:]
        last_pos = -1
        last_signal = "NEUTRAL"
        for signal in signals:
            pos = tail.rfind(signal)
            if pos > last_pos:
                last_pos = pos
                last_signal = signal
        if last_pos == -1:
            logger.warning("Signal not found in final_decision — defaulting to NEUTRAL")
        return last_signal

    def _update_bias_from_signal(self, signal: str, ticker: str, date: str) -> None:
        """Auto-update agent bias in config based on the final analysis signal."""
        signal_to_bias = {
            "BUY": ("bullish", "high"),
            "OVERWEIGHT": ("bullish", "medium"),
            "BULLISH": ("bullish", "medium"),
            "NEUTRAL": ("neutral", "low"),
            "BEARISH": ("bearish", "medium"),
            "UNDERWEIGHT": ("bearish", "medium"),
            "SELL": ("bearish", "high"),
        }
        direction, confidence = signal_to_bias.get(signal, ("neutral", "low"))
        self.config.setdefault("agent_bias", {})
        self.config["agent_bias"]["direction"] = direction
        self.config["agent_bias"]["confidence"] = confidence
        self.config["agent_bias"]["reason"] = f"Auto: {ticker} analysis on {date} → {signal}"
        self.config["agent_bias"]["signal"] = signal
        self.config["agent_bias"]["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Compute confluence score
        self.config["confluence"] = self._compute_confluence(signal)

        try:
            save_config(self.config, self.config_path)
        except Exception as exc:
            logger.warning("Failed to update bias from signal: %s", exc)

    def _compute_confluence(self, agent_signal: str) -> dict:
        """Compute confluence score between user bias and agent signal.

        Scoring:
          User bias:  bullish/high=+3, medium=+2, low=+1, neutral=0, bearish flipped
          Agent signal: BUY=+3, OVERWEIGHT=+2, HOLD=0, UNDERWEIGHT=-2, SELL=-3

        Total: -6 to +6. Positive = bullish confluence, negative = bearish.
        """
        user_bias = self.config.get("bias", {})
        user_dir = user_bias.get("direction", "neutral")
        user_conf = user_bias.get("confidence", "medium")

        # User bias is pre-session gut feel — cap at 2 (moderate)
        # Only confirmed ICT analysis should reach 3 (strong)
        conf_map = {"high": 2, "medium": 1, "low": 1}
        user_score = conf_map.get(user_conf, 1)
        if user_dir == "bearish":
            user_score = -user_score
        elif user_dir == "neutral":
            user_score = 0

        signal_map = {"BUY": 3, "OVERWEIGHT": 2, "BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1, "UNDERWEIGHT": -2, "SELL": -3}
        agent_score = signal_map.get(agent_signal, 0)

        total = user_score + agent_score
        aligned = (user_score > 0 and agent_score > 0) or (user_score < 0 and agent_score < 0)
        conflicting = (user_score > 0 and agent_score < 0) or (user_score < 0 and agent_score > 0)

        if abs(total) >= 5:
            strength = "strong"
        elif abs(total) >= 2:
            strength = "moderate"
        elif abs(total) == 1:
            strength = "weak"
        else:
            strength = "neutral"

        direction = "bullish" if total > 0 else "bearish" if total < 0 else "neutral"

        return {
            "user_score": user_score,
            "agent_score": agent_score,
            "total": total,
            "direction": direction,
            "strength": strength,
            "aligned": aligned,
            "conflicting": conflicting,
        }

    def _get_user_bias_context(self) -> str:
        """Format user's pre-session bias as context for agent prompts."""
        bias = self.config.get("bias", {})
        direction = bias.get("direction", "neutral")
        confidence = bias.get("confidence", "medium")
        reason = bias.get("reason", "")
        if direction == "neutral" and not reason:
            return ""
        parts = [f"\nTrader's Daily Bias: {direction.upper()} (confidence: {confidence})"]
        if reason:
            parts.append(f"Reason: {reason}")
        return "\n".join(parts) + "\n"

    def _get_confluence_context(self) -> str:
        """Format confluence score as context for agent prompts."""
        bias = self.config.get("bias", {})
        direction = bias.get("direction", "neutral")
        confidence = bias.get("confidence", "medium")
        reason = bias.get("reason", "")

        agent_bias = self.config.get("agent_bias", {})
        agent_dir = agent_bias.get("direction", "")
        agent_signal = agent_bias.get("signal", "")

        parts = []
        parts.append("\n══ BIAS & CONFLUENCE CONTEXT ══")
        parts.append(f"Trader's Daily Bias: {direction.upper()} (confidence: {confidence})")
        if reason:
            parts.append(f"Bias Reason: {reason}")

        if not agent_dir:
            parts.append("No prior analysis available — this is the first run or no previous signal.")
            parts.append("Confluence cannot be computed yet. Decide based on trader bias + current evidence.")
        else:
            parts.append(f"Last Run Agent Bias: {agent_dir.upper()} (signal: {agent_signal})")
            aligned = (direction == "bullish" and agent_dir == "bullish") or \
                      (direction == "bearish" and agent_dir == "bearish")
            if direction == "neutral":
                parts.append("Confluence: NEUTRAL — trader has no directional bias")
            elif aligned:
                parts.append(f"Confluence: ALIGNED — trader and agents agree ({direction})")
            elif agent_dir == "neutral":
                parts.append(f"Confluence: MIXED — trader is {direction} but agents are neutral")
            else:
                parts.append(f"Confluence: CONFLICT — trader is {direction} but agents say {agent_dir}")
                parts.append("⚠ When trader and agents disagree, proceed with caution. Reduce size or wait.")

        parts.append("══════════════════════════════\n")
        return "\n".join(parts)

    def _get_session_context(self, ticker: str, date: str) -> str:
        """Pre-compute ALL session levels using indicators.py — same functions as backtest.

        Uses existing indicator functions: get_prev_day_levels, get_session_levels,
        get_midnight_open, calc_sfp_detection, calc_displacement_candle.
        No guessing — agents get exact pre-computed values.
        """
        try:
            from openclaw.indicators import (
                _fetch_ohlcv_df, get_prev_day_levels, get_session_levels,
                get_midnight_open, calc_sfp_detection, calc_displacement_candle,
                get_math_indicators,
            )
            import pandas as pd

            parts = ["\n══ PRE-COMPUTED SESSION LEVELS (exact values — use these, do not recompute) ══"]

            # Fetch data via indicators engine
            df_1m = _fetch_ohlcv_df(ticker, "1m", date)
            df_1h = _fetch_ohlcv_df(ticker, "1H", date)
            df_15m = _fetch_ohlcv_df(ticker, "15m", date)
            df_daily = _fetch_ohlcv_df(ticker, "1D", date)

            # ── MIDNIGHT OPEN + PDH/PDL + NDOG/NWOG ──
            if df_1m is not None and not isinstance(df_1m, str) and not df_1m.empty:
                parts.append(get_midnight_open(df_1m, date))

            # ── PDH / PDL (9:30-16:00 regular hours — same as backtest) ──
            if df_1h is not None and not isinstance(df_1h, str) and not df_1h.empty:
                df_1h_norm = df_1h.rename(columns={c: c.lower() for c in df_1h.columns})
                today_dt = pd.Timestamp(date).date()
                # Get yesterday's regular-hours data (9:30-16:00)
                prev_days = df_1h_norm[df_1h_norm.index.date < today_dt]
                if not prev_days.empty:
                    last_date = prev_days.index.date[-1]
                    prev_day = prev_days[prev_days.index.date == last_date]
                    prev_session = prev_day.between_time("09:30", "16:00")
                    if prev_session.empty:
                        prev_session = prev_day  # fallback to full day
                    pdh = float(prev_session["high"].max())
                    pdl = float(prev_session["low"].min())
                    parts.append(f"\nPDH (Previous Day High): {pdh:.2f}")
                    parts.append(f"PDL (Previous Day Low): {pdl:.2f}")
                    parts.append(f"PDH-PDL Range: {pdh - pdl:.2f} pts")
                else:
                    parts.append(get_prev_day_levels(df_1h))  # fallback to SMC

            # ── ASIA/LONDON SESSION LEVELS (from indicators.py) ──
            if df_15m is not None and not isinstance(df_15m, str) and not df_15m.empty:
                parts.append(get_session_levels(df_15m))

            # ── 1H SWING LEVELS + SFP DETECTION (from indicators.py) ──
            if df_1h is not None and not isinstance(df_1h, str) and not df_1h.empty:
                col_map = {c: c.lower() for c in df_1h.columns}
                df_1h_norm = df_1h.rename(columns=col_map)
                # Only use bars before today's NY open (completed 1H candles)
                if df_1h_norm.index.tz:
                    cutoff = pd.Timestamp(f"{date} 09:30", tz=df_1h_norm.index.tz)
                else:
                    cutoff = pd.Timestamp(f"{date} 09:30")
                prior_1h = df_1h_norm[df_1h_norm.index < cutoff].tail(30)

                if len(prior_1h) >= 5:
                    sfp_result = calc_sfp_detection(prior_1h)
                    # Format swing levels
                    swings = []
                    for sh in sfp_result.get("swing_highs", [])[-5:]:
                        swings.append(f"  Swing High: {sh['price']:.2f} ({sh.get('timestamp', '')})")
                    for sl in sfp_result.get("swing_lows", [])[-5:]:
                        swings.append(f"  Swing Low: {sl['price']:.2f} ({sl.get('timestamp', '')})")
                    if swings:
                        parts.append("\n1H Swing Levels (prior session — SFP targets):")
                        parts.extend(swings)

                    # SFP status
                    status = sfp_result.get("status", "no_sfp")
                    if status == "sfp_confirmed":
                        latest = sfp_result.get("latest_sfp", {})
                        parts.append(f"\nSFP CONFIRMED: {latest.get('direction', '?')} at {latest.get('swept_level', '?'):.2f} "
                                     f"(penetration: {latest.get('points_beyond', 0):.1f} pts)")
                    else:
                        parts.append(f"\nSFP Status: {status}")

            # ── DISPLACEMENT CANDLES (5m — from indicators.py) ──
            if df_15m is not None and not isinstance(df_15m, str) and not df_15m.empty:
                disp = calc_displacement_candle(df_15m)
                latest = disp.get("latest")
                if latest:
                    parts.append(f"\nDisplacement: {latest['direction'].upper()} candle at {latest['timestamp']} "
                                 f"(body {latest['body_pct']:.0f}% of range)")
                else:
                    parts.append("\nDisplacement: NONE detected on 15m")

            # ── DAILY BIAS (uses backtest's _daily_bias — same weighted scoring) ──
            if df_daily is not None and not isinstance(df_daily, str) and not df_daily.empty:
                from openclaw.backtest import _daily_bias, _structure_bias
                df_d = df_daily.rename(columns={c: c.lower() for c in df_daily.columns})
                today_dt = pd.Timestamp(date).date()
                prior_daily = df_d[df_d.index.date < today_dt]

                # Get 1H data for confirmation (same as backtest)
                df_1h_bias = None
                if df_1h is not None and not isinstance(df_1h, str) and not df_1h.empty:
                    df_1h_norm = df_1h.rename(columns={c: c.lower() for c in df_1h.columns})
                    if df_1h_norm.index.tz:
                        cutoff = pd.Timestamp(f"{date} 09:30", tz=df_1h_norm.index.tz)
                    else:
                        cutoff = pd.Timestamp(f"{date} 09:30")
                    df_1h_bias = df_1h_norm[df_1h_norm.index < cutoff].tail(30)

                if len(prior_daily) >= 5:
                    bias = _daily_bias(prior_daily, df_1h_bias)
                    d_bull, d_bear = _structure_bias(prior_daily)
                    last_d = prior_daily.iloc[-1]
                    bull_candle = last_d["close"] > last_d["open"]

                    parts.append(f"\nDAILY BIAS: {bias.upper()}")
                    parts.append(f"  Yesterday: {'BULLISH' if bull_candle else 'BEARISH'} close")
                    parts.append(f"  Daily structure: bull={d_bull} bear={d_bear}")
                    if df_1h_bias is not None and len(df_1h_bias) >= 5:
                        h_bull, h_bear = _structure_bias(df_1h_bias)
                        parts.append(f"  1H confirmation: bull={h_bull} bear={h_bear}")

            # ── ATR (from indicators.py math indicators) ──
            if df_daily is not None and not isinstance(df_daily, str) and not df_daily.empty:
                parts.append(f"\n{get_math_indicators(df_daily, '1D')}")

            parts.append("══════════════════════════════\n")
            return "\n".join(parts)
        except Exception as exc:
            logger.warning("Failed to compute session context: %s", exc)
            return ""

    def _get_ema200_context(self, ticker: str) -> str:
        """Compute EMA 200 on multiple timeframes and format as context."""
        try:
            from openclaw.indicators import _fetch_ohlcv_df
            import pandas as pd

            timeframes = ["1D", "4H", "1H", "30m", "15m", "5m"]
            parts = ["\n══ EMA 200 REFERENCE CONTEXT (all timeframes — not a bias filter) ══"]
            above_count = 0
            total = 0

            for tf in timeframes:
                try:
                    df = _fetch_ohlcv_df(ticker, tf, "")
                    if df is None or isinstance(df, str) or df.empty:
                        continue
                    # Normalize column names
                    col_map = {}
                    for c in df.columns:
                        col_map[c] = c.lower()
                    df = df.rename(columns=col_map)
                    if "close" not in df.columns:
                        continue
                    close = df["close"].astype(float)
                    span = min(200, len(close))
                    if span < 20:
                        continue
                    ema = close.ewm(span=span, adjust=True).mean()
                    ema_val = float(ema.iloc[-1])
                    price = float(close.iloc[-1])
                    above = price > ema_val
                    dist = round(price - ema_val, 2)
                    label = f"EMA {span}" if span < 200 else "EMA 200"
                    parts.append(f"  {tf:6s} {label}: {ema_val:.2f} | Price: {price:.2f} | {'ABOVE' if above else 'BELOW'} ({dist:+.2f})")
                    if above:
                        above_count += 1
                    total += 1
                except Exception:
                    continue

            if total > 0:
                if above_count == total:
                    parts.append(f"  Alignment: ALL ABOVE ({total}/{total} TF) — strong bullish reference context (structure determines bias, not EMA)")
                elif above_count == 0:
                    parts.append(f"  Alignment: ALL BELOW ({total}/{total} TF) — strong bearish reference context (structure determines bias, not EMA)")
                else:
                    parts.append(f"  Alignment: MIXED ({above_count} above, {total - above_count} below) — reduce conviction")

            parts.append("══════════════════════════════\n")
            return "\n".join(parts) if total > 0 else ""
        except Exception:
            return ""

    def _build_analyst_prompt(self, agents_dir, agent_name, strategy, ticker, date):
        md_path = os.path.join(agents_dir, agent_name, "PROMPT.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        frontmatter = self._parse_frontmatter(md_path)
        tools_key = "tools_jadecap" if strategy == "jadecap" else "tools"
        tool_names = frontmatter.get(tools_key, [])
        tool_data = self._prefetch_tool_data(tool_names, ticker, date)

        # Inject agent's past memory
        memory_str = self._get_memory_context(agent_name, ticker, date)

        context = {
            "ticker": ticker,
            "current_date": date,
            "company_name": ticker,
            "instrument_context": f"Instrument: {ticker}",
            "past_memory_str": memory_str or "No prior analysis memory available.",
        }
        if strategy == "jadecap":
            context.update(self._build_jadecap_context(ticker, date))
        prompt_text = self._substitute_placeholders(prompt_text, context)

        data_sections = ""
        if tool_data:
            data_sections = "\n\n=== PRE-FETCHED DATA ===\n"
            for tool_name, result in tool_data.items():
                data_sections += f"\n--- {tool_name} ---\n{result}\n"

        user_bias = self._get_user_bias_context()
        ema200_context = self._get_ema200_context(ticker)
        session_context = self._get_session_context(ticker, date)

        return f"""Analyze {ticker} for trade date {date}.
{user_bias}
{session_context}
{ema200_context}
{prompt_text}

Company/Instrument: {ticker}
Trade Date: {date}
{data_sections}
"""

    def _build_researcher_prompt(self, agents_dir, agent_name, strategy, ticker, date, reports_context, debate, side, reports=None):
        md_path = os.path.join(agents_dir, agent_name, "PROMPT.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        opponent_history = debate["bear_history"] if side == "bull" else debate["bull_history"]
        reports = reports or {}
        frontmatter = self._parse_frontmatter(md_path)
        memory_name = agent_name  # Each agent has its own memory store now
        past_memory_str = self._get_memory_context(memory_name, ticker, date)

        is_bear_jadecap = (side == "bear" and strategy == "jadecap")

        context = {
            "ticker": ticker,
            "current_date": date,
            "company_name": ticker,
            "market_research_report": reports.get("market_report", ""),
            "market_report": reports.get("market_report", ""),
            "sentiment_report": "N/A — analyst not active",
            "news_report": reports.get("news_report", ""),
            "fundamentals_report": "N/A — analyst not active",
            "history": debate.get("history", ""),
            "current_response": opponent_history[-2000:] if opponent_history else "",
            "past_memory_str": past_memory_str,
        }
        if strategy == "jadecap":
            context.update(self._build_jadecap_context(ticker, date))
        prompt_text = self._substitute_placeholders(prompt_text, context)
        user_bias = self._get_user_bias_context()
        confluence = self._get_confluence_context()
        ema200_context = self._get_ema200_context(ticker)

        # Bear researcher optimization: trim opponent arg and debate history
        # to reduce input tokens (bull goes first and gets the full context).
        if is_bear_jadecap:
            opponent_snippet = opponent_history[-1500:] if opponent_history else "No argument yet — you go first."
            debate_history = debate.get("history", "")
            debate_history_trimmed = debate_history[-3000:] if len(debate_history) > 3000 else debate_history
        else:
            opponent_snippet = opponent_history[-2000:] if opponent_history else "No argument yet — you go first."
            debate_history_trimmed = debate.get("history", "")

        return f"""{prompt_text}
{user_bias}
{confluence}
{ema200_context}
Company/Instrument: {ticker}
Trade Date: {date}

{reports_context}

Debate History:
{debate_history_trimmed}

Opponent's Last Argument:
{opponent_snippet}
"""

    def _build_prompt_with_context(self, agents_dir, agent_name, strategy, **context):
        md_path = os.path.join(agents_dir, agent_name, "PROMPT.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        base_context = context.copy()
        base_context["user_bias_context"] = self._get_user_bias_context()
        base_context["confluence_context"] = self._get_confluence_context()
        base_context["ema200_context"] = self._get_ema200_context(context.get("ticker", ""))
        base_context["past_memory_str"] = self._get_memory_context(
            agent_name,
            str(context.get("ticker") or context.get("company_name") or ""),
            str(context.get("date") or context.get("current_date") or ""),
        )
        if strategy == "jadecap":
            ticker = context.get("ticker") or context.get("company_name") or ""
            current_date = context.get("date") or context.get("current_date") or ""
            base_context.update(self._build_jadecap_context(str(ticker), str(current_date)))
        # Track which keys were substituted into the prompt template
        used_keys = set()
        for key in base_context:
            if f"{{{key}}}" in prompt_text or f"${{{key}}}" in prompt_text:
                used_keys.add(key)
        prompt_text = self._substitute_placeholders(prompt_text, base_context)
        # Only append context keys that were NOT already substituted
        remaining = {k: v for k, v in base_context.items() if v and k not in used_keys}
        if remaining:
            context_str = "\n".join(f"{k}: {v}" for k, v in remaining.items())
            return f"""{prompt_text}

{context_str}
"""
        return prompt_text

    @staticmethod
    def _substitute_placeholders(template: str, context: dict) -> str:
        def resolve(expr: str):
            expr = expr.strip()
            expr = re.sub(r"\.upper\(\)$", "_upper", expr)
            expr = expr.replace("int(t1_pct * 100)", "t1_pct_int")
            expr = expr.replace("instrument['description']", "instrument_description")
            expr = expr.replace('instrument["description"]', "instrument_description")
            for root in ["BULL_SETUP", "BEAR_SETUP", "AMD", "RISK"]:
                expr = re.sub(rf"{root}\[['\"]([^'\"]+)['\"]\]\[['\"]([^'\"]+)['\"]\]", rf"{root}_\1_\2", expr)
                expr = re.sub(rf"{root}\[['\"]([^'\"]+)['\"]\]", rf"{root}_\1", expr)
            return context.get(expr, "{" + expr + "}")
        return re.sub(r"\{([^{}]+)\}", lambda m: str(resolve(m.group(1))), template)

    def _build_jadecap_context(self, ticker: str, date: str) -> dict:
        from openclaw.jadecap_config import (
            JADECAP_CONFIG, AMD, RISK, HARD_RULES, BULL_SETUP, BEAR_SETUP,
            CHECKLIST, TRADE_OUTPUT_FORMAT, HOLIDAY_RULES, KILL_ZONES,
        )
        cfg = self.config.get("jadecap", {})
        active = cfg.get("active_instrument") or ticker or JADECAP_CONFIG.get("active_instrument", "NQ")
        active_firm = cfg.get("prop_firm") or JADECAP_CONFIG.get("active_firm", "apex")
        instruments = JADECAP_CONFIG.get("instruments", {})
        instrument = instruments.get(active, instruments.get(active.replace("=F", ""), {}))
        point_value = instrument.get("point_value", 20)
        max_loss = RISK.get("max_loss_per_trade", self.config.get("risk", {}).get("max_loss_per_trade", 500))
        min_rr = RISK.get("min_rr", self.config.get("risk", {}).get("min_risk_reward", 3))
        atr_mult = cfg.get("atr_stop_multiplier", 1.5)
        t1_pct = cfg.get("t1_close_pct", 0.5)
        half_risk_losses = RISK.get("half_risk_after_consecutive_losses", 2)
        max_streak = RISK.get("max_losing_streak_before_stop", self.config.get("risk", {}).get("max_consecutive_losses", 3))
        live_price_str = self._safe_live_price(active)
        kz_str = self._format_kill_zones(KILL_ZONES)
        checklist_str = self._format_checklist(CHECKLIST)
        hard_rules_str = self._format_hard_rules(HARD_RULES)
        bull_req = self._format_requirements(BULL_SETUP.get("requirements", []))
        bear_req = self._format_requirements(BEAR_SETUP.get("requirements", []))
        holiday_list = "\n".join(f"- {h}" for h in HOLIDAY_RULES.get("holidays", []))
        risk_dict = dict(RISK)
        risk_dict.setdefault("daily_profit_target", 1000)
        risk_dict.setdefault("max_loss_per_trade", max_loss)
        context = {
            "active": active,
            "active_firm": active_firm,
            "active_firm_upper": str(active_firm).upper(),
            "ticker": ticker,
            "current_date": date,
            "instrument": instrument,
            "instrument_description": instrument.get("description", active),
            "instrument_context": f"Instrument: {active} — {instrument.get('description', active)}",
            "point_value": point_value,
            "max_loss": max_loss,
            "min_rr": min_rr,
            "atr_mult": atr_mult,
            "t1_pct": t1_pct,
            "t1_pct_int": int(t1_pct * 100),
            "half_risk_losses": half_risk_losses,
            "max_streak": max_streak,
            "live_price_str": live_price_str,
            "kz_str": kz_str,
            "checklist_str": checklist_str,
            "hard_rules_str": hard_rules_str,
            "bull_req": bull_req,
            "bear_req": bear_req,
            "holiday_list": holiday_list,
            "TRADE_OUTPUT_FORMAT": TRADE_OUTPUT_FORMAT.strip(),
            "BULL_SETUP": BULL_SETUP,
            "BEAR_SETUP": BEAR_SETUP,
            "AMD": AMD,
            "RISK": risk_dict,
            "BULL_SETUP_target": BULL_SETUP.get("target", ""),
            "BULL_SETUP_stop": BULL_SETUP.get("stop", ""),
            "BULL_SETUP_invalidation": BULL_SETUP.get("invalidation", ""),
            "BEAR_SETUP_target": BEAR_SETUP.get("target", ""),
            "BEAR_SETUP_stop": BEAR_SETUP.get("stop", ""),
            "BEAR_SETUP_invalidation": BEAR_SETUP.get("invalidation", ""),
            "AMD_manipulation_action": AMD.get("manipulation", {}).get("action", ""),
            "AMD_distribution_action": AMD.get("distribution", {}).get("action", ""),
            "RISK_max_loss_per_trade": risk_dict.get("max_loss_per_trade", max_loss),
            "RISK_daily_profit_target": risk_dict.get("daily_profit_target", 1000),
        }

        # Inject prop firm-specific rules (scaling, runner, cashout)
        from openclaw.jadecap_config import PROP_FIRMS
        firm_cfg = PROP_FIRMS.get(active_firm, {})
        context["firm_name"] = firm_cfg.get("name", active_firm)
        context["firm_account_size"] = firm_cfg.get("account_size", 50000)
        context["firm_trailing_dd"] = firm_cfg.get("trailing_drawdown", 2000)
        context["firm_safety_net"] = firm_cfg.get("safety_net", 52100)
        context["firm_max_contracts_mnq"] = firm_cfg.get("max_contracts_mnq", 40)
        context["firm_base_contracts"] = firm_cfg.get("base_contracts_mnq", 5)
        context["firm_scaling_step"] = firm_cfg.get("scaling_step", 2500)
        context["firm_scaling_description"] = firm_cfg.get("scaling_description", "")
        context["firm_runner_description"] = firm_cfg.get("runner_description", "")
        context["firm_runner_exit"] = firm_cfg.get("runner_exit", "EOD")
        context["firm_consistency_rule"] = firm_cfg.get("consistency_rule", 0.50)

        return context

    _live_price_cache: dict = {}  # symbol -> (timestamp, result)

    def _safe_live_price(self, symbol: str) -> str:
        """Fetch live price with 30s cache to avoid repeated WebSocket connections."""
        import time
        now = time.time()
        cached = self._live_price_cache.get(symbol)
        if cached and (now - cached[0]) < 30:
            return cached[1]
        try:
            import openclaw.tools  # ensure registration/import side effects
            from openclaw.indicators import fetch_live_price
            result = fetch_live_price(symbol)
            self._live_price_cache[symbol] = (now, result)
            return result
        except Exception as exc:
            return f"CURRENT PRICE: {symbol} = unavailable ({exc})"

    @staticmethod
    def _format_kill_zones(kill_zones: dict) -> str:
        lines = []
        for name, data in kill_zones.items():
            label = data.get("name", name)
            start = data.get("start", "?")
            end = data.get("end", "?")
            active = data.get("active", True)
            note = data.get("note", "")
            lines.append(f"- {label}: {start}-{end} EST ({'active' if active else 'disabled'})")
            if note:
                lines.append(f"  Note: {note}")
            # Include Silver Bullet rules if present
            sb_rules = data.get("silver_bullet_rules")
            if sb_rules:
                lines.append("  Silver Bullet Rules:")
                if sb_rules.get("first_fvg_only"):
                    lines.append("    - Only the FIRST valid FVG in this window qualifies")
                if sb_rules.get("sweep_required_before_entry"):
                    lines.append("    - Liquidity sweep required before entry")
                if sb_rules.get("bearish_fvg_requires_high_sweep"):
                    lines.append("    - Bearish FVG requires a prior HIGH to be swept")
                if sb_rules.get("bullish_fvg_requires_low_sweep"):
                    lines.append("    - Bullish FVG requires a prior LOW to be swept")
                entry_type = sb_rules.get("entry_type", "")
                if entry_type:
                    lines.append(f"    - Entry type: {entry_type.replace('_', ' ')}")
                if sb_rules.get("cancel_unfilled_at_window_close"):
                    lines.append("    - Cancel unfilled orders when window closes")
                if sb_rules.get("one_trade_per_window"):
                    lines.append("    - One trade per window maximum")
        return "\n".join(lines)

    @staticmethod
    def _format_checklist(items: list) -> str:
        lines = []
        for item in items:
            req = "required" if item.get("required", False) else "optional"
            lines.append(f"- {item.get('description', item.get('id', 'item'))}: {item.get('detail', '')} [{req}]")
        return "\n".join(lines)

    @staticmethod
    def _format_hard_rules(rules: list) -> str:
        return "\n".join(f"- {r}" for r in rules)

    @staticmethod
    def _format_requirements(reqs: list) -> str:
        return "\n".join(f"- {r}" for r in reqs)

    def _read_strategy_prompt(self, md_path: str, strategy: str) -> str:
        if not os.path.exists(md_path):
            return f"Agent definition not found: {md_path}"
        with open(md_path, "r") as f:
            content = f.read()
        section = "## JadeCap Strategy Prompt" if strategy == "jadecap" else "## Default Strategy Prompt"
        if section in content:
            start = content.index(section) + len(section)
            next_heading = content.find("\n## ", start)
            if next_heading == -1:
                return content[start:].strip()
            return content[start:next_heading].strip()
        if "---" in content:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content

    def _format_reports(self, reports: dict) -> str:
        parts = []
        for key, value in reports.items():
            label = key.replace("_", " ").title()
            parts.append(f"=== {label} ===\n{value}")
        return "\n\n".join(parts)

    @staticmethod
    def _parse_frontmatter(md_path: str) -> dict:
        if not os.path.exists(md_path):
            return {}
        with open(md_path, "r") as f:
            content = f.read()
        if not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        frontmatter = {}
        for line in parts[1].strip().split("\n"):
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                items = value[1:-1]
                frontmatter[key] = [i.strip() for i in items.split(",") if i.strip()]
            elif value == "null" or value == "":
                frontmatter[key] = None
            else:
                frontmatter[key] = value
        return frontmatter

    def _prefetch_tool_data(self, tool_names: list, ticker: str, date: str) -> dict:
        if not tool_names:
            return {}
        import openclaw.tools
        from openclaw.tools import registry
        return registry.call_many(tool_names, ticker, date, self.config)

    def _get_memory_context(self, memory_name: str, ticker: str, date: str) -> str:
        mem = self.memories.get(memory_name)
        if not mem or not mem.documents:
            return ""
        situation = f"Trading analysis for {ticker} on {date}"
        matches = mem.get_memories(situation, n_matches=3)
        if not matches:
            return ""
        parts = ["Past relevant experiences:"]
        for m in matches:
            if m["similarity_score"] > 0.1:
                parts.append(f"- Situation: {m['matched_situation'][:200]}")
                parts.append(f"  Recommendation: {m['recommendation'][:200]}")
        return "\n".join(parts) if len(parts) > 1 else ""

    def _dispatch_with_timeout(self, dispatch_fn, agent_name: str, prompt: str, model: str) -> str:
        timeout = self.config.get("analysis", {}).get("agent_timeout_seconds", 300)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(dispatch_fn, agent_name, prompt, model)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError:
                raise TimeoutError(f"Agent '{agent_name}' timed out after {timeout}s")

    def _persist_reports(self, db_path: str, run_id: str, reports: dict) -> None:
        from openclaw.database import get_db
        try:
            with get_db(db_path) as conn:
                for section_name, content in reports.items():
                    conn.execute("INSERT INTO reports (run_id, section_name, content) VALUES (?, ?, ?)", (run_id, section_name, content))
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to persist reports: %s", exc)

    def _persist_debate(self, db_path: str, run_id: str, debate_type: str, debate: dict, judge_decision: str = "") -> None:
        from openclaw.database import get_db
        try:
            with get_db(db_path) as conn:
                conn.execute(
                    "INSERT INTO debates (run_id, debate_type, full_history, side_a_history, side_b_history, side_c_history, judge_decision) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id, debate_type,
                        debate.get("history", ""),
                        debate.get("bull_history", debate.get("aggressive_history", "")),
                        debate.get("bear_history", debate.get("conservative_history", "")),
                        debate.get("neutral_history", ""),
                        judge_decision,
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to persist debate: %s", exc)

    def _mark_run_failed(self, db_path: str, run_id: str, error_msg: str, start_time) -> None:
        from openclaw.database import get_db
        duration = (datetime.now() - start_time).total_seconds()
        try:
            with get_db(db_path) as conn:
                conn.execute(
                    "UPDATE runs SET status = 'failed', error_message = ?, duration_seconds = ? WHERE id = ?",
                    (error_msg[:500], duration, run_id),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to mark run as failed: %s", exc)

    def _write_final_decision(self, ticker: str, date: str, decision: str, run_id: str) -> None:
        """Write final_decision.md to results/ folder for UI display."""
        results_dir = self._resolve_path("results")
        try:
            os.makedirs(results_dir, exist_ok=True)
            filepath = os.path.join(results_dir, "final_decision.md")
            header = f"# {ticker} — {date} (run: {run_id})\n\n"
            with open(filepath, "w") as f:
                f.write(header + decision + "\n")
        except Exception as exc:
            logger.warning("Failed to write final_decision.md: %s", exc)

    def _default_dispatch(self, agent_name: str, prompt: str, model: str) -> str:
        print(f"[DISPATCH] {agent_name} (model: {model})")
        print(f"[PROMPT] {prompt[:200]}...")
        return f"[Stub response from {agent_name}]"

    def _write_agent_memories(self, result, agents_dir: str):
        """Write run lessons to each agent's MEMORY.md file."""
        for agent_name, mem in self.memories.items():
            if not mem.documents:
                continue
            memory_file = os.path.join(agents_dir, agent_name, "MEMORY.md")
            if not os.path.exists(os.path.dirname(memory_file)):
                continue
            latest_situation = mem.documents[-1] if mem.documents else ""
            latest_recommendation = mem.recommendations[-1] if mem.recommendations else ""
            entry = f"\n### {result.date}: {result.ticker} → {result.signal}\n"
            entry += f"- Situation: {latest_situation[:200]}\n"
            entry += f"- Lesson: {latest_recommendation[:200]}\n\n"
            try:
                with open(memory_file, "a") as f:
                    f.write(entry)
            except Exception as exc:
                logger.warning("Failed to write memory for %s: %s", agent_name, exc)

    def reflect(self, ticker: str, date: str, dispatch_fn=None, callbacks=None):
        import yfinance as yf
        from datetime import timedelta
        callbacks = callbacks or []
        db_path = self._resolve_path(self.config["paths"]["database"])
        # Add =F suffix for futures tickers
        futures = {"NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K", "GC", "SI", "CL"}
        ticker_yf = f"{ticker}=F" if ticker.upper() in futures else ticker
        stock = yf.Ticker(ticker_yf)
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        end_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        hist = stock.history(start=date, end=end_date, interval="1d")
        if hist.empty:
            return {"error": f"No price data for {ticker} on {date}"}
        actual_close = float(hist["Close"].iloc[0])
        from openclaw.database import get_db, init_db
        init_db(db_path)
        signal = None
        prev_close = None
        run_id = None
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT id, signal FROM runs WHERE ticker = ? AND trade_date = ? ORDER BY created_at DESC LIMIT 1",
                (ticker, date),
            ).fetchone()
            if row:
                signal = row["signal"]
                run_id = row["id"]
        prev_date = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_hist = stock.history(start=prev_date, end=date, interval="1d")
        if not prev_hist.empty:
            prev_close = float(prev_hist["Close"].iloc[0])
        actual_change_pct = 0.0
        if prev_close and prev_close > 0:
            actual_change_pct = ((actual_close - prev_close) / prev_close) * 100
        correct = None
        if signal == "BUY":
            correct = actual_change_pct > 0
        elif signal == "SELL":
            correct = actual_change_pct < 0
        elif signal in ("HOLD", "NEUTRAL", "BULLISH", "BEARISH", "OVERWEIGHT", "UNDERWEIGHT"):
            correct = None
        reflection = f"Signal {signal}, actual close {actual_close:.2f}, change {actual_change_pct:.2f}%"
        if run_id:
            with get_db(db_path) as conn:
                conn.execute(
                    "INSERT INTO outcomes (run_id, ticker, trade_date, signal, correct, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (run_id, ticker, date, signal or "", 1 if correct is True else 0 if correct is False else None, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()

        # Write outcome to agent MEMORY.md files
        agents_dir = self._resolve_path(self.config["paths"]["agents_dir"])
        outcome_text = "CORRECT" if correct is True else "WRONG" if correct is False else "N/A"
        for agent_name in self.memories:
            memory_file = os.path.join(agents_dir, agent_name, "MEMORY.md")
            if os.path.exists(memory_file):
                try:
                    entry = f"\n### Outcome: {ticker} {date} — {outcome_text}\n"
                    entry += f"- Signal: {signal}, Actual change: {actual_change_pct:.2f}%\n"
                    if correct is True:
                        entry += f"- Lesson: {signal} was correct. Reinforce this pattern.\n\n"
                    elif correct is False:
                        entry += f"- Lesson: {signal} was wrong. Actual moved {actual_change_pct:.2f}%. Review what was missed.\n\n"
                    else:
                        entry += f"- Lesson: Signal was {signal} (neutral). No directional lesson.\n\n"
                    with open(memory_file, "a") as f:
                        f.write(entry)
                except Exception:
                    pass

            # Also add to BM25 for runtime retrieval
            self.memories[agent_name].add_situations([
                (f"Outcome: {ticker} {date}, signal={signal}, change={actual_change_pct:.2f}%",
                 f"Signal {signal} was {'correct' if correct else 'wrong' if correct is False else 'neutral'}. Actual change: {actual_change_pct:.2f}%.")
            ])

        return {
            "ticker": ticker,
            "date": date,
            "actual_close": actual_close,
            "signal": signal,
            "correct": correct,
            "actual_change_pct": actual_change_pct,
            "reflection": reflection,
        }

    def halt(self):
        self.config["halt"] = True
        save_config(self.config, self.config_path)

    def resume(self):
        self.config["halt"] = False
        save_config(self.config, self.config_path)

    @property
    def status(self):
        state = "running" if self._running else "idle"
        if self.config.get("halt"):
            state = "halted"
        return {
            "state": state,
            "strategy": self.config.get("strategy"),
            "watchlist": self.config.get("watchlist", []),
            "config_path": self.config_path,
        }
