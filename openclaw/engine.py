"""Unified RunEngine: dispatches subagents in the 4-tier trading pipeline.

Features:
- Error recovery: try/except around each tier, persist partial state
- Parallel Tier 1: dispatch_parallel_fn for analysts
- Timeout: _dispatch_with_timeout using concurrent.futures
- BM25 memory: hydrate on init, inject into prompts, persist after run
- Config bridge: set_dataflow_config() at start of run()
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from openclaw.config import load_config, save_config, get_model_for_agent
from openclaw.memory import FinancialSituationMemory


# ---------- Data classes ----------

@dataclass
class RunResult:
    """Result of a complete trading analysis run."""
    ticker: str
    date: str
    signal: str  # BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
    market_report: str = ""
    sentiment_report: str = ""
    news_report: str = ""
    fundamentals_report: str = ""
    investment_debate: dict = field(default_factory=dict)
    risk_debate: dict = field(default_factory=dict)
    trader_plan: str = ""
    final_decision: str = ""
    duration_seconds: float = 0.0
    partial_state: Optional[dict] = field(default=None, repr=False)


class RunEngine:
    """Orchestrates the 4-tier trading analysis pipeline via subagent dispatch.

    This is the single entry point for all frontends (CLI, WebUI, OpenClaw, scripts).
    Each trading agent is defined as a .md file in agents/trading/.
    The engine reads the agent definition, constructs the prompt with context,
    and dispatches it as a subagent using whatever AI the caller provides.
    """

    def __init__(self, config_path: str = "trading-config.json"):
        self.config_path = os.path.abspath(config_path)
        self.config = load_config(config_path)
        self._running = False

        # BM25 memory stores — one per agent that uses memory
        self.memories = {
            "bull_memory": FinancialSituationMemory("bull_memory"),
            "bear_memory": FinancialSituationMemory("bear_memory"),
            "trader_memory": FinancialSituationMemory("trader_memory"),
            "invest_judge_memory": FinancialSituationMemory("invest_judge_memory"),
            "portfolio_manager_memory": FinancialSituationMemory("portfolio_manager_memory"),
        }

        # Hydrate memories from SQLite if database exists
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
        """Run a full trading analysis pipeline.

        Args:
            ticker: Stock/futures symbol (e.g., "NVDA", "NQ")
            date: Trade date (e.g., "2026-03-27")
            dispatch_fn: Callable(agent_name, prompt, model) -> str response.
                         This is how the caller's AI system dispatches subagents.
                         If None, uses a default print-based stub.
            dispatch_parallel_fn: Optional Callable([(agent_name, prompt, model), ...]) -> [str].
                                  If provided, Tier 1 analysts are dispatched in parallel.
            callbacks: Optional list of RunCallback objects for event streaming.

        Returns:
            RunResult with signal, reports, debates, and metadata.
        """
        # CC-9: Bridge config into dataflows singleton so route_to_vendor reads user settings
        from openclaw.dataflows.config import set_config as set_dataflow_config
        set_dataflow_config(self.config)

        if self.config.get("halt"):
            raise RuntimeError("Analysis is halted. Call engine.resume() to re-enable.")

        callbacks = callbacks or []
        dispatch = dispatch_fn or self._default_dispatch
        self._running = True
        start_time = datetime.now()

        # Partial state for error recovery (CC-3)
        partial = {
            "ticker": ticker,
            "date": date,
            "tier_completed": 0,
            "reports": {},
            "debate": {},
            "investment_plan": "",
            "trader_plan": "",
            "risk_debate": {},
            "final_decision": "",
        }

        for cb in callbacks:
            cb.on_run_start(ticker, date)

        try:
            strategy = self.config["strategy"]
            agents_dir = self.config["paths"]["agents_dir"]

            # ─── TIER 1: ANALYSTS ─────────────────────────────────
            try:
                reports = self._run_tier1_analysts(
                    agents_dir, strategy, ticker, date,
                    dispatch, dispatch_parallel_fn, callbacks,
                )
                partial["reports"] = reports
                partial["tier_completed"] = 1
            except Exception as e:
                self._save_partial_state(partial)
                for cb in callbacks:
                    cb.on_error(e)
                raise

            # ─── TIER 2: BULL/BEAR DEBATE ─────────────────────────
            try:
                debate = self._run_debate(
                    agents_dir, strategy, ticker, date, reports, dispatch, callbacks
                )
                partial["debate"] = debate
                partial["tier_completed"] = 2
            except Exception as e:
                self._save_partial_state(partial)
                for cb in callbacks:
                    cb.on_error(e)
                raise

            # ─── TIER 3: JUDGE + TRADER + RISK ────────────────────
            try:
                investment_plan, trader_plan, risk_debate = self._run_judge_trader_risk(
                    agents_dir, strategy, ticker, date, reports, debate, dispatch, callbacks
                )
                partial["investment_plan"] = investment_plan
                partial["trader_plan"] = trader_plan
                partial["risk_debate"] = risk_debate
                partial["tier_completed"] = 3
            except Exception as e:
                self._save_partial_state(partial)
                for cb in callbacks:
                    cb.on_error(e)
                raise

            # ─── TIER 4: PORTFOLIO MANAGER ────────────────────────
            try:
                final_decision = self._run_portfolio_manager(
                    agents_dir, strategy, ticker, date, reports, debate,
                    investment_plan, trader_plan, risk_debate, dispatch, callbacks
                )
                partial["final_decision"] = final_decision
                partial["tier_completed"] = 4
            except Exception as e:
                self._save_partial_state(partial)
                for cb in callbacks:
                    cb.on_error(e)
                raise

            # Extract signal
            signal = self._extract_signal(final_decision)

            for cb in callbacks:
                cb.on_signal(signal)

            duration = (datetime.now() - start_time).total_seconds()
            result = RunResult(
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

            # Persist BM25 memories to SQLite after successful run
            try:
                from openclaw.memory_persistence import persist_memories
                from openclaw.database import init_db
                db_path = self.config["paths"]["database"]
                init_db(db_path)
                persist_memories(self.memories, db_path, f"{ticker}_{date}")
            except Exception:
                pass  # Best-effort: don't let memory save failure kill the run

            for cb in callbacks:
                cb.on_run_complete(result)

            return result

        except Exception as e:
            # on_error may have already been called per-tier, but also catch
            # any unexpected errors here
            if partial["tier_completed"] == 0:
                for cb in callbacks:
                    cb.on_error(e)
            raise
        finally:
            self._running = False

    def _run_tier1_analysts(self, agents_dir, strategy, ticker, date,
                            dispatch, dispatch_parallel_fn, callbacks):
        """Run Tier 1 analysts, optionally in parallel (CC-4)."""
        reports = {}
        analyst_map = {
            "market": ("market-analyst", "market_report"),
            "social": ("social-analyst", "sentiment_report"),
            "news": ("news-analyst", "news_report"),
            "fundamentals": ("fundamentals-analyst", "fundamentals_report"),
        }
        selected = self.config["analysis"]["analysts"]

        # Filter to valid analysts
        tasks = []
        for analyst_key in selected:
            if analyst_key not in analyst_map:
                continue
            agent_name, report_field = analyst_map[analyst_key]
            model = get_model_for_agent(self.config, agent_name, "quick")
            prompt = self._build_analyst_prompt(
                agents_dir, agent_name, strategy, ticker, date
            )
            tasks.append((agent_name, report_field, prompt, model))

        if dispatch_parallel_fn and len(tasks) > 1:
            # Parallel dispatch (CC-4)
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
            # Sequential dispatch
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
        """Run the bull/bear debate loop for N rounds."""
        max_rounds = self.config["analysis"]["max_debate_rounds"]
        debate = {
            "history": "",
            "bull_history": "",
            "bear_history": "",
            "count": 0,
        }

        reports_context = self._format_reports(reports)

        for round_num in range(max_rounds):
            # Bull argues
            bull_prompt = self._build_researcher_prompt(
                agents_dir, "bull-researcher", strategy, ticker, date,
                reports_context, debate, "bull", reports=reports
            )
            model = get_model_for_agent(self.config, "bull-researcher", "quick")
            for cb in callbacks:
                cb.on_agent_status("bull-researcher", "running")

            bull_response = self._dispatch_with_timeout(dispatch, "bull-researcher", bull_prompt, model)
            debate["bull_history"] += f"\n{bull_response}"
            debate["history"] += f"\nBull Analyst: {bull_response}"
            debate["count"] += 1

            for cb in callbacks:
                cb.on_debate_turn("Bull Analyst", bull_response)
                cb.on_agent_status("bull-researcher", "completed")

            # Bear counters
            bear_prompt = self._build_researcher_prompt(
                agents_dir, "bear-researcher", strategy, ticker, date,
                reports_context, debate, "bear", reports=reports
            )
            model = get_model_for_agent(self.config, "bear-researcher", "quick")
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

    def _run_judge_trader_risk(self, agents_dir, strategy, ticker, date,
                                reports, debate, dispatch, callbacks):
        """Run research manager, trader, and risk debate."""
        reports_context = self._format_reports(reports)

        # Research Manager judges debate
        manager_prompt = self._build_prompt_with_context(
            agents_dir, "research-manager", strategy,
            ticker=ticker, date=date,
            reports=reports_context,
            debate_history=debate["history"],
            bull_history=debate["bull_history"],
            bear_history=debate["bear_history"],
            past_memory_str=self._get_memory_context("invest_judge_memory", ticker, date),
        )
        model = get_model_for_agent(self.config, "research-manager", "deep")
        for cb in callbacks:
            cb.on_agent_status("research-manager", "running")

        investment_plan = self._dispatch_with_timeout(dispatch, "research-manager", manager_prompt, model)

        for cb in callbacks:
            cb.on_agent_status("research-manager", "completed")

        # Trader proposes
        trader_prompt = self._build_prompt_with_context(
            agents_dir, "trader", strategy,
            ticker=ticker, date=date,
            reports=reports_context,
            investment_plan=investment_plan,
            past_memory_str=self._get_memory_context("trader_memory", ticker, date),
        )
        model = get_model_for_agent(self.config, "trader", "quick")
        for cb in callbacks:
            cb.on_agent_status("trader", "running")

        trader_plan = self._dispatch_with_timeout(dispatch, "trader", trader_prompt, model)

        for cb in callbacks:
            cb.on_agent_status("trader", "completed")

        # Risk debate: aggressive -> conservative -> neutral (N rounds)
        max_risk_rounds = self.config["analysis"]["max_risk_discuss_rounds"]
        risk_debate = {
            "history": "",
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "count": 0,
        }

        risk_agents = [
            ("aggressive-risk", "aggressive_history"),
            ("conservative-risk", "conservative_history"),
            ("neutral-risk", "neutral_history"),
        ]

        for round_num in range(max_risk_rounds):
            for agent_name, history_key in risk_agents:
                prompt = self._build_prompt_with_context(
                    agents_dir, agent_name, strategy,
                    ticker=ticker, date=date,
                    reports=reports_context,
                    trader_decision=trader_plan,
                    risk_history=risk_debate["history"],
                    aggressive_response=risk_debate.get("last_aggressive", ""),
                    conservative_response=risk_debate.get("last_conservative", ""),
                    neutral_response=risk_debate.get("last_neutral", ""),
                )
                model = get_model_for_agent(self.config, agent_name, "quick")
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

    def _run_portfolio_manager(self, agents_dir, strategy, ticker, date,
                                reports, debate, investment_plan, trader_plan,
                                risk_debate, dispatch, callbacks):
        """Run portfolio manager for final decision."""
        reports_context = self._format_reports(reports)
        prompt = self._build_prompt_with_context(
            agents_dir, "portfolio-manager", strategy,
            ticker=ticker, date=date,
            reports=reports_context,
            debate_history=debate["history"],
            investment_plan=investment_plan,
            trader_plan=trader_plan,
            risk_history=risk_debate["history"],
            aggressive_history=risk_debate["aggressive_history"],
            conservative_history=risk_debate["conservative_history"],
            neutral_history=risk_debate["neutral_history"],
            past_memory_str=self._get_memory_context("portfolio_manager_memory", ticker, date),
        )
        model = get_model_for_agent(self.config, "portfolio-manager", "deep")
        for cb in callbacks:
            cb.on_agent_status("portfolio-manager", "running")

        response = self._dispatch_with_timeout(dispatch, "portfolio-manager", prompt, model)

        for cb in callbacks:
            cb.on_agent_status("portfolio-manager", "completed")

        return response

    def _extract_signal(self, final_decision: str) -> str:
        """Extract BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL from portfolio manager response."""
        signals = ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
        text_upper = final_decision.upper()
        # Check for explicit signal patterns
        for signal in signals:
            if f"FINAL TRANSACTION PROPOSAL: **{signal}**" in text_upper:
                return signal
            if f"RATING: {signal}" in text_upper:
                return signal
        # Fallback: find last occurrence of any signal word
        last_pos = -1
        last_signal = "HOLD"
        for signal in signals:
            pos = text_upper.rfind(signal)
            if pos > last_pos:
                last_pos = pos
                last_signal = signal
        return last_signal

    def _build_analyst_prompt(self, agents_dir, agent_name, strategy, ticker, date):
        """Build a prompt for an analyst agent from its .md definition."""
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)

        # Substitute {placeholders} in the template
        context = {
            "ticker": ticker, "current_date": date, "company_name": ticker,
            "instrument_context": f"Instrument: {ticker}",
        }
        prompt_text = self._substitute_placeholders(prompt_text, context)

        return f"""Analyze {ticker} for trade date {date}.

{prompt_text}

Company/Instrument: {ticker}
Trade Date: {date}
"""

    def _build_researcher_prompt(self, agents_dir, agent_name, strategy,
                                  ticker, date, reports_context, debate, side,
                                  reports=None):
        """Build a prompt for bull/bear researcher."""
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        opponent_history = debate["bear_history"] if side == "bull" else debate["bull_history"]
        reports = reports or {}

        # Retrieve BM25 memories for this agent
        memory_name = "bull_memory" if side == "bull" else "bear_memory"
        past_memory_str = self._get_memory_context(memory_name, ticker, date)

        # Substitute {placeholders} in the template
        context = {
            "ticker": ticker, "current_date": date, "company_name": ticker,
            "market_research_report": reports.get("market_report", ""),
            "market_report": reports.get("market_report", ""),
            "sentiment_report": reports.get("sentiment_report", ""),
            "news_report": reports.get("news_report", ""),
            "fundamentals_report": reports.get("fundamentals_report", ""),
            "history": debate.get("history", ""),
            "current_response": opponent_history[-2000:] if opponent_history else "",
            "past_memory_str": past_memory_str,
        }
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
        """Build a prompt for any agent with arbitrary context fields.

        First substitutes {variable} placeholders in the .md prompt template,
        then appends any remaining context as key: value lines.
        """
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)

        # Substitute {placeholders} in the prompt template with context values
        prompt_text = self._substitute_placeholders(prompt_text, context)

        # Also append context as labeled sections for anything not in a placeholder
        context_str = "\n".join(f"{k}: {v}" for k, v in context.items() if v)
        return f"""{prompt_text}

{context_str}
"""

    @staticmethod
    def _substitute_placeholders(template: str, context: dict) -> str:
        """Safely substitute {variable} placeholders in a prompt template.

        Uses format_map with a defaultdict so unmatched {keys} are left as-is
        rather than raising KeyError. This handles the JadeCap prompts which have
        dozens of runtime variables like {bull_req}, {hard_rules_str}, etc.
        """
        from collections import defaultdict

        class SafeDict(defaultdict):
            def __missing__(self, key):
                return "{" + key + "}"  # leave unmatched placeholders as-is

        safe = SafeDict(str, context)
        try:
            return template.format_map(safe)
        except (ValueError, IndexError):
            # If format_map fails (e.g., malformed braces), return raw template
            return template

    def _read_strategy_prompt(self, md_path: str, strategy: str) -> str:
        """Read the appropriate strategy prompt section from an agent .md file."""
        if not os.path.exists(md_path):
            return f"Agent definition not found: {md_path}"

        with open(md_path, "r") as f:
            content = f.read()

        # Parse: find the strategy-specific section
        if strategy == "jadecap":
            section = "## JadeCap Strategy Prompt"
        else:
            section = "## Default Strategy Prompt"

        # Extract the section content
        if section in content:
            start = content.index(section) + len(section)
            # Find next ## heading or end of file
            next_heading = content.find("\n## ", start)
            if next_heading == -1:
                return content[start:].strip()
            return content[start:next_heading].strip()

        # Fallback: return everything after frontmatter
        if "---" in content:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content

    def _format_reports(self, reports: dict) -> str:
        """Format all analyst reports into a single context string."""
        parts = []
        for key, value in reports.items():
            label = key.replace("_", " ").title()
            parts.append(f"=== {label} ===\n{value}")
        return "\n\n".join(parts)

    def _get_memory_context(self, memory_name: str, ticker: str, date: str) -> str:
        """Retrieve relevant BM25 memories for an agent as a formatted string."""
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

    def _dispatch_with_timeout(self, dispatch_fn, agent_name: str,
                                prompt: str, model: str) -> str:
        """Wrap dispatch call with concurrent.futures timeout (CC-4b).

        Uses the agent_timeout_seconds from config. Falls back to 300s.
        """
        timeout = self.config.get("analysis", {}).get("agent_timeout_seconds", 300)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(dispatch_fn, agent_name, prompt, model)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError:
                raise TimeoutError(
                    f"Agent '{agent_name}' timed out after {timeout}s"
                )

    def _save_partial_state(self, partial: dict) -> None:
        """Save partial run state for error recovery (CC-3).

        Writes to results_dir/<ticker>_<date>_partial.json.
        """
        results_dir = self.config.get("paths", {}).get("results_dir", "results")
        try:
            os.makedirs(results_dir, exist_ok=True)
            filename = f"{partial['ticker']}_{partial['date']}_partial.json"
            filepath = os.path.join(results_dir, filename)
            with open(filepath, "w") as f:
                json.dump(partial, f, indent=2, default=str)
        except Exception:
            # Best-effort: don't let save failure mask the original error
            pass

    def _default_dispatch(self, agent_name: str, prompt: str, model: str) -> str:
        """Default dispatch stub -- prints and returns placeholder."""
        print(f"[DISPATCH] {agent_name} (model: {model})")
        print(f"[PROMPT] {prompt[:200]}...")
        return f"[Stub response from {agent_name}]"

    def reflect(self, ticker: str, date: str, dispatch_fn=None, callbacks=None):
        """Post-session: fetch actual price, compare signal, reflect, persist.

        Args:
            ticker: Stock/futures symbol.
            date: Trade date to reflect on.
            dispatch_fn: Optional AI dispatch for reflection subagent.
            callbacks: Optional list of RunCallback objects.

        Returns:
            Dict with reflection results including actual_close, signal, correct, reflection.
        """
        import yfinance as yf
        from datetime import datetime, timezone, timedelta

        callbacks = callbacks or []
        db_path = self.config["paths"]["database"]

        # Fetch actual closing price
        stock = yf.Ticker(ticker)
        # yfinance needs end date to be day after for single-day fetch
        from datetime import datetime as dt
        date_obj = dt.strptime(date, "%Y-%m-%d")
        end_date = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        hist = stock.history(start=date, end=end_date, interval="1d")
        if hist.empty:
            return {"error": f"No price data for {ticker} on {date}"}

        actual_close = float(hist["Close"].iloc[0])

        # Load today's signal from database
        from openclaw.database import get_db, init_db
        init_db(db_path)
        signal = None
        prev_close = None
        run_id = None

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT id, signal FROM runs WHERE ticker = ? AND trade_date = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (ticker, date),
            ).fetchone()
            if row:
                signal = row["signal"]
                run_id = row["id"]

        # Try to get previous close for comparison
        prev_date = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        prev_hist = stock.history(start=prev_date, end=date, interval="1d")
        if not prev_hist.empty:
            prev_close = float(prev_hist["Close"].iloc[0])

        # Compare signal vs actual price movement
        actual_change_pct = 0.0
        if prev_close and prev_close > 0:
            actual_change_pct = ((actual_close - prev_close) / prev_close) * 100

        price_went_up = actual_change_pct > 0
        correct = None
        if signal:
            bullish_signals = {"BUY", "OVERWEIGHT"}
            bearish_signals = {"SELL", "UNDERWEIGHT"}
            if signal in bullish_signals:
                correct = price_went_up
            elif signal in bearish_signals:
                correct = not price_went_up
            else:  # HOLD
                correct = abs(actual_change_pct) < 1.0  # small move = HOLD correct

        # Dispatch reflection subagent if dispatch_fn provided
        reflection_text = ""
        if dispatch_fn and signal:
            reflection_prompt = f"""Reflect on this trading analysis outcome:

Ticker: {ticker}
Date: {date}
Signal: {signal}
Previous Close: {prev_close}
Actual Close: {actual_close}
Change: {actual_change_pct:+.2f}%
Correct: {correct}

What lessons can be learned? What went right or wrong? Keep it concise (2-3 paragraphs)."""

            model = get_model_for_agent(self.config, "portfolio-manager", "quick")
            try:
                reflection_text = self._dispatch_with_timeout(
                    dispatch_fn, "reflection", reflection_prompt, model
                )
            except Exception:
                reflection_text = f"Signal: {signal}, Actual: {actual_change_pct:+.2f}%, Correct: {correct}"

        # Persist outcome to database
        now = datetime.now(timezone.utc).isoformat()
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO outcomes (run_id, ticker, trade_date, signal, "
                "actual_close, actual_change_pct, correct, reflection, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, ticker, date, signal, actual_close, actual_change_pct,
                 1 if correct else 0 if correct is not None else None,
                 reflection_text, now),
            )
            conn.commit()

        # Write summary to memory/YYYY-MM-DD.md
        memory_dir = self.config["paths"]["memory_dir"]
        os.makedirs(memory_dir, exist_ok=True)
        summary_path = os.path.join(memory_dir, f"{date}.md")
        with open(summary_path, "a") as f:
            f.write(f"\n\n## Reflection: {ticker}\n")
            f.write(f"- Signal: {signal}\n")
            f.write(f"- Actual Close: ${actual_close:.2f} ({actual_change_pct:+.2f}%)\n")
            f.write(f"- Correct: {'Yes' if correct else 'No' if correct is not None else 'N/A'}\n")
            if reflection_text:
                f.write(f"\n{reflection_text}\n")

        return {
            "ticker": ticker,
            "date": date,
            "signal": signal,
            "actual_close": actual_close,
            "actual_change_pct": actual_change_pct,
            "correct": correct,
            "reflection": reflection_text,
            "run_id": run_id,
        }

    def halt(self):
        """Halt all analysis. Persists to config file."""
        self.config["halt"] = True
        save_config(self.config, self.config_path)

    def resume(self):
        """Resume analysis. Requires explicit call."""
        self.config["halt"] = False
        save_config(self.config, self.config_path)

    @property
    def status(self) -> dict:
        return {
            "state": "running" if self._running else ("halted" if self.config.get("halt") else "idle"),
            "strategy": self.config["strategy"],
            "watchlist": self.config.get("watchlist", []),
            "config_path": self.config_path,
        }
