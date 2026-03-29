"""Unified RunEngine: dispatches subagents in the 4-tier trading pipeline.

Features:
- Error recovery: try/except around each tier, persist partial state
- Parallel Tier 1: dispatch_parallel_fn for analysts
- Timeout: _dispatch_with_timeout using concurrent.futures
- BM25 memory: hydrate on init, inject into prompts, persist after run
- Config bridge: set_dataflow_config() at start of run()
"""

import json
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
    signal: str = ""  # BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
    market_report: str = ""
    sentiment_report: str = ""
    news_report: str = ""
    fundamentals_report: str = ""
    investment_debate: dict = field(default_factory=dict)
    risk_debate: dict = field(default_factory=dict)
    trader_plan: str = ""
    final_decision: str = ""
    duration_seconds: float = 0.0


class RunEngine:
    """Orchestrates the 4-tier trading analysis pipeline via subagent dispatch."""

    def __init__(self, config_path: str = "trading-config.json"):
        self.config_path = os.path.abspath(config_path)
        self.config = load_config(config_path)
        self._running = False

        self.memories = {
            "bull_memory": FinancialSituationMemory("bull_memory"),
            "bear_memory": FinancialSituationMemory("bear_memory"),
            "trader_memory": FinancialSituationMemory("trader_memory"),
            "invest_judge_memory": FinancialSituationMemory("invest_judge_memory"),
            "portfolio_manager_memory": FinancialSituationMemory("portfolio_manager_memory"),
        }

        db_path = self.config["paths"]["database"]
        if os.path.exists(db_path):
            from openclaw.memory_persistence import hydrate_memories
            hydrate_memories(self.memories, db_path)

    def run(
        self,
        ticker: str,
        date: str,
        dispatch_fn: Optional[Callable] = None,
        dispatch_parallel_fn: Optional[Callable] = None,
        callbacks: Optional[list] = None,
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

        run_id = str(uuid.uuid4())[:8]
        db_path = self.config["paths"]["database"]
        init_db(db_path)
        now = datetime.now(timezone.utc).isoformat()
        strategy = self.config["strategy"]
        agents_dir = self.config["paths"]["agents_dir"]

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
                    agents_dir, strategy, ticker, date, reports, debate, dispatch, callbacks
                )
                self._persist_debate(db_path, run_id, "risk", risk_debate,
                                     judge_decision=investment_plan)
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

            signal = self._extract_signal(final_decision)
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
                sentiment_report=reports.get("sentiment_report", ""),
                news_report=reports.get("news_report", ""),
                fundamentals_report=reports.get("fundamentals_report", ""),
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

            for cb in callbacks:
                cb.on_run_complete(result)
            return result

        except Exception as e:
            for cb in callbacks:
                cb.on_error(e)
            raise
        finally:
            self._running = False

    def _run_tier1_analysts(self, agents_dir, strategy, ticker, date, dispatch, dispatch_parallel_fn, callbacks):
        reports = {}
        analyst_map = {
            "market": ("market-analyst", "market_report"),
            "social": ("social-analyst", "sentiment_report"),
            "news": ("news-analyst", "news_report"),
            "fundamentals": ("fundamentals-analyst", "fundamentals_report"),
        }
        selected = self.config["analysis"]["analysts"]
        tasks = []
        for analyst_key in selected:
            if analyst_key not in analyst_map:
                continue
            agent_name, report_field = analyst_map[analyst_key]
            frontmatter = self._parse_frontmatter(os.path.join(agents_dir, f"{agent_name}.md"))
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
            fm = self._parse_frontmatter(os.path.join(agents_dir, "bull-researcher.md"))
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
            fm = self._parse_frontmatter(os.path.join(agents_dir, "bear-researcher.md"))
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

    def _run_judge_trader_risk(self, agents_dir, strategy, ticker, date, reports, debate, dispatch, callbacks):
        reports_context = self._format_reports(reports)
        manager_prompt = self._build_prompt_with_context(
            agents_dir, "research-manager", strategy,
            ticker=ticker, date=date,
            reports=reports_context,
            market_report=reports.get("market_report", ""),
            sentiment_report=reports.get("sentiment_report", ""),
            news_report=reports.get("news_report", ""),
            fundamentals_report=reports.get("fundamentals_report", ""),
            debate_history=debate["history"],
            history=debate["history"],
            bull_history=debate["bull_history"],
            bear_history=debate["bear_history"],
            past_memory_str=self._get_memory_context("invest_judge_memory", ticker, date),
        )
        fm = self._parse_frontmatter(os.path.join(agents_dir, "research-manager.md"))
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
            sentiment_report=reports.get("sentiment_report", ""),
            news_report=reports.get("news_report", ""),
            fundamentals_report=reports.get("fundamentals_report", ""),
            investment_plan=investment_plan,
            past_memory_str=self._get_memory_context("trader_memory", ticker, date),
        )
        fm = self._parse_frontmatter(os.path.join(agents_dir, "trader.md"))
        model = get_model_for_agent(self.config, "trader", fm.get("tier", "quick") or "quick")
        for cb in callbacks:
            cb.on_agent_status("trader", "running")
        trader_plan = self._dispatch_with_timeout(dispatch, "trader", trader_prompt, model)
        for cb in callbacks:
            cb.on_agent_status("trader", "completed")

        max_risk_rounds = self.config["analysis"]["max_risk_discuss_rounds"]
        risk_debate = {"history": "", "aggressive_history": "", "conservative_history": "", "neutral_history": "", "count": 0}
        risk_agents = [("aggressive-risk", "aggressive_history"), ("conservative-risk", "conservative_history"), ("neutral-risk", "neutral_history")]
        for _ in range(max_risk_rounds):
            for agent_name, history_key in risk_agents:
                prompt = self._build_prompt_with_context(
                    agents_dir, agent_name, strategy,
                    ticker=ticker, date=date,
                    reports=reports_context,
                    market_research_report=reports.get("market_report", ""),
                    market_report=reports.get("market_report", ""),
                    sentiment_report=reports.get("sentiment_report", ""),
                    news_report=reports.get("news_report", ""),
                    fundamentals_report=reports.get("fundamentals_report", ""),
                    trader_decision=trader_plan,
                    trader_plan=trader_plan,
                    risk_history=risk_debate["history"],
                    history=risk_debate["history"],
                    current_aggressive_response=risk_debate.get("last_aggressive", ""),
                    current_conservative_response=risk_debate.get("last_conservative", ""),
                    current_neutral_response=risk_debate.get("last_neutral", ""),
                )
                fm = self._parse_frontmatter(os.path.join(agents_dir, f"{agent_name}.md"))
                model = get_model_for_agent(self.config, agent_name, fm.get("tier", "quick") or "quick")
                for cb in callbacks:
                    cb.on_agent_status(agent_name, "running")
                response = self._dispatch_with_timeout(dispatch, agent_name, prompt, model)
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
            sentiment_report=reports.get("sentiment_report", ""),
            news_report=reports.get("news_report", ""),
            fundamentals_report=reports.get("fundamentals_report", ""),
            history=risk_debate["history"],
            debate_history=debate["history"],
            investment_plan=investment_plan,
            research_plan=investment_plan,
            trader_plan=trader_plan,
            risk_history=risk_debate["history"],
            aggressive_history=risk_debate["aggressive_history"],
            conservative_history=risk_debate["conservative_history"],
            neutral_history=risk_debate["neutral_history"],
            past_memory_str=self._get_memory_context("portfolio_manager_memory", ticker, date),
        )
        fm = self._parse_frontmatter(os.path.join(agents_dir, "portfolio-manager.md"))
        model = get_model_for_agent(self.config, "portfolio-manager", fm.get("tier", "deep") or "deep")
        for cb in callbacks:
            cb.on_agent_status("portfolio-manager", "running")
        response = self._dispatch_with_timeout(dispatch, "portfolio-manager", prompt, model)
        for cb in callbacks:
            cb.on_agent_status("portfolio-manager", "completed")
        return response

    def _extract_signal(self, final_decision: str) -> str:
        signals = ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
        text_upper = final_decision.upper()
        for signal in signals:
            if f"FINAL TRANSACTION PROPOSAL: **{signal}**" in text_upper:
                return signal
            if f"RATING: {signal}" in text_upper:
                return signal
        last_pos = -1
        last_signal = "HOLD"
        for signal in signals:
            pos = text_upper.rfind(signal)
            if pos > last_pos:
                last_pos = pos
                last_signal = signal
        return last_signal

    def _build_analyst_prompt(self, agents_dir, agent_name, strategy, ticker, date):
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        frontmatter = self._parse_frontmatter(md_path)
        tools_key = "tools_jadecap" if strategy == "jadecap" else "tools"
        tool_names = frontmatter.get(tools_key, [])
        tool_data = self._prefetch_tool_data(tool_names, ticker, date)

        context = {
            "ticker": ticker,
            "current_date": date,
            "company_name": ticker,
            "instrument_context": f"Instrument: {ticker}",
        }
        if strategy == "jadecap":
            context.update(self._build_jadecap_context(ticker, date))
        prompt_text = self._substitute_placeholders(prompt_text, context)

        data_sections = ""
        if tool_data:
            data_sections = "\n\n=== PRE-FETCHED DATA ===\n"
            for tool_name, result in tool_data.items():
                data_sections += f"\n--- {tool_name} ---\n{result}\n"

        return f"""Analyze {ticker} for trade date {date}.

{prompt_text}

Company/Instrument: {ticker}
Trade Date: {date}
{data_sections}
"""

    def _build_researcher_prompt(self, agents_dir, agent_name, strategy, ticker, date, reports_context, debate, side, reports=None):
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        opponent_history = debate["bear_history"] if side == "bull" else debate["bull_history"]
        reports = reports or {}
        frontmatter = self._parse_frontmatter(md_path)
        memory_key = "memory_jadecap" if self.config["strategy"] == "jadecap" else "memory"
        memory_name = frontmatter.get(memory_key) or ("bull_memory" if side == "bull" else "bear_memory")
        past_memory_str = self._get_memory_context(memory_name, ticker, date)
        context = {
            "ticker": ticker,
            "current_date": date,
            "company_name": ticker,
            "market_research_report": reports.get("market_report", ""),
            "market_report": reports.get("market_report", ""),
            "sentiment_report": reports.get("sentiment_report", ""),
            "news_report": reports.get("news_report", ""),
            "fundamentals_report": reports.get("fundamentals_report", ""),
            "history": debate.get("history", ""),
            "current_response": opponent_history[-2000:] if opponent_history else "",
            "past_memory_str": past_memory_str,
        }
        if strategy == "jadecap":
            context.update(self._build_jadecap_context(ticker, date))
        prompt_text = self._substitute_placeholders(prompt_text, context)
        return f"""{prompt_text}

Company/Instrument: {ticker}
Trade Date: {date}

{reports_context}

Debate History:
{debate['history']}

Opponent's Last Argument:
{opponent_history[-2000:] if opponent_history else 'No argument yet — you go first.'}
"""

    def _build_prompt_with_context(self, agents_dir, agent_name, strategy, **context):
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        base_context = context.copy()
        if strategy == "jadecap":
            ticker = context.get("ticker") or context.get("company_name") or ""
            current_date = context.get("date") or context.get("current_date") or ""
            base_context.update(self._build_jadecap_context(str(ticker), str(current_date)))
        prompt_text = self._substitute_placeholders(prompt_text, base_context)
        context_str = "\n".join(f"{k}: {v}" for k, v in base_context.items() if v)
        return f"""{prompt_text}

{context_str}
"""

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
        half_risk_losses = RISK.get("half_risk_after_losses", 2)
        max_streak = RISK.get("max_consecutive_losses", self.config.get("risk", {}).get("max_consecutive_losses", 3))
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
        return context

    def _safe_live_price(self, symbol: str) -> str:
        try:
            import openclaw.tools  # ensure registration/import side effects
            from openclaw.indicators import fetch_live_price
            return fetch_live_price(symbol)
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
            lines.append(f"- {label}: {start}-{end} EST ({'active' if active else 'disabled'})")
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
        from openclaw.tool_registry import registry
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

    def _default_dispatch(self, agent_name: str, prompt: str, model: str) -> str:
        print(f"[DISPATCH] {agent_name} (model: {model})")
        print(f"[PROMPT] {prompt[:200]}...")
        return f"[Stub response from {agent_name}]"

    def reflect(self, ticker: str, date: str, dispatch_fn=None, callbacks=None):
        import yfinance as yf
        from datetime import timedelta
        callbacks = callbacks or []
        db_path = self.config["paths"]["database"]
        stock = yf.Ticker(ticker)
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
        elif signal in ("HOLD", "OVERWEIGHT", "UNDERWEIGHT"):
            correct = None
        reflection = f"Signal {signal}, actual close {actual_close:.2f}, change {actual_change_pct:.2f}%"
        if run_id:
            with get_db(db_path) as conn:
                conn.execute(
                    "INSERT INTO outcomes (run_id, ticker, trade_date, signal, correct, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (run_id, ticker, date, signal or "", 1 if correct is True else 0 if correct is False else None, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
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
