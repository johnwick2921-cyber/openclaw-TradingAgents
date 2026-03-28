# OpenClaw + TradingAgents Merge — Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Dissolve TradingAgents into OpenClaw as a trading module. Full subagent architecture — each trading agent becomes an AI-agnostic .md file dispatched by OpenClaw's main agent. No LangGraph. No duplicate infrastructure. OpenClaw is main.

**Architecture:** 12 trading agent .md files in `agents/trading/`, dispatched sequentially by a RunEngine orchestrator in the original 4-tier pipeline (analysts → debate → risk → trader). Data tools (yfinance, databento, ICT indicators) stay as Python. Config in `trading-config.json`. Memory in SQLite + markdown. Dashboard in Rich terminal + React web.

**Tech Stack:** Python 3.10+, rank_bm25, aiosqlite, yfinance, Rich

**Phase Dependencies:**
```
Phase 1 (bug fixes) ──→ no dependencies, do first
Phase 2 (config) ──────→ no dependencies
Phase 3 (agent .md) ───→ needs Phase 2 (agents reference config schema)
Phase 4 (RunEngine) ───→ needs Phase 2 + 3 (reads config + agent .md files)
Phase 5 (memory) ──────→ needs Phase 4 (wired into RunEngine)
Phase 6 (dashboard) ───→ needs Phase 4 + 5 (reads from RunEngine + trading.db)
Phase 7 (OpenClaw) ────→ needs Phase 4 (references RunEngine in docs)
Phase 8 (cleanup) ─────→ needs Phase 4 + 7 (all new code in place before deleting old)
Phase 9 (review) ──────→ needs ALL prior phases
```

**Parallel opportunities:**
- Phase 1 + 2 can run in parallel (independent)
- Phase 3 tasks (12 agent files) can run in parallel with each other
- Phase 6 (dashboard) can start after Phase 5, in parallel with Phase 7
- Phase 7 tasks (5 file updates) can run in parallel with each other

**Estimated scope:** ~25 files created, ~12 files modified, ~30 files deleted. The merge is NET negative in file count.

**Source repo:** `github.com/johnwick2921-cyber/openclaw-TradingAgents` (main branch)
**Working directory:** `/home/hoang/.openclaw/`
**OpenClaw framework files:** `/home/hoang/.openclaw/workspace/` (SOUL.md, AGENTS.md, HEARTBEAT.md, TOOLS.md, USER.md, IDENTITY.md, MEMORY.md, BOOTSTRAP.md)
**TradingAgents source:** `/home/hoang/.openclaw/workspace/TradingAgents/`

**Key Design Decisions (locked in during brainstorming):**
1. **OpenClaw is main** — TradingAgents dissolves into it, not the other way around
2. **Full subagent** — no LangGraph. Each trading agent = .md file dispatched by OpenClaw's AI
3. **AI-agnostic** — agent definitions in `agents/trading/`, not `.claude/agents/` (works with any AI, not just Claude)
4. **Multi-LLM preserved** — each agent can use a different model via `per_agent` config
5. **No duplication** — OpenClaw's existing tools (WebSearch, WebFetch, Bash) available to all subagents. Only NEW tools are the market data APIs
6. **Unified tools** — subagents can use both OpenClaw tools AND trading data tools (yfinance, ICT indicators, etc.)
7. **Original pipeline logic preserved** — same 4 tiers, same debate rules, same signals, same tools
8. **Config: trading-config.json** — single JSON file replaces 3 old config systems
9. **Memory: SQLite + markdown** — BM25 persisted in SQLite, human-readable summaries in markdown
10. **Dashboard: terminal + web** — Rich signal board + migrated React WebUI as OpenClaw module

**What MOVES from TradingAgents into openclaw/ (unique trading value):**
- `tradingagents/dataflows/` → `openclaw/dataflows/` (yfinance, databento, alpha vantage, ICT indicators, stockstats)
- `tradingagents/agents/utils/memory.py` → `openclaw/memory.py` (BM25 FinancialSituationMemory)
- `tradingagents/agents/utils/*_tools.py` → `openclaw/tools/` (get_stock_data, get_indicators, get_news, etc.)
- `tradingagents/agents/utils/ict_tools.py` → `openclaw/tools/ict_tools.py` (ICT-specific tools)
- `tradingagents/agents/utils/agent_states.py` → `openclaw/agent_states.py`
- `tradingagents/agents/utils/agent_utils.py` → `openclaw/tools/__init__.py` (re-exports)

**After move: `TradingAgents/` directory is FULLY DELETED** — nothing remains. OpenClaw owns everything.

**Import path changes:**
- `from tradingagents.dataflows.interface import route_to_vendor` → `from openclaw.dataflows.interface import route_to_vendor`
- `from tradingagents.agents.utils.memory import FinancialSituationMemory` → `from openclaw.memory import FinancialSituationMemory`
- `from tradingagents.agents.utils.core_stock_tools import get_stock_data` → `from openclaw.tools.core_stock_tools import get_stock_data`

**What's DELETED (OpenClaw already provides or no longer needed):**
- `tradingagents/graph/` — entire LangGraph orchestration (7 files) → replaced by RunEngine subagent dispatch
- `tradingagents/llm_clients/` — entire module (8 files) → subagents use OpenClaw's configured AI
- `cli/` — entire directory (8 files) → OpenClaw IS the CLI
- `default_config.py` → replaced by trading-config.json + SCHEMA_DEFAULTS
- `jadecap_config.py` → module globals eliminated, config sections in JSON
- All `*_jadecap.py` agent variants (10 files) → merged into single .md files with strategy sections
- All default agent `.py` files (12 files) → prompts extracted to .md, then deleted
- `main.py`, `test.py`, `run_webui.py` → entry points replaced by RunEngine
- **The entire `TradingAgents/` directory** — after extraction, nothing remains

## Final File Structure (after merge — OpenClaw owns everything)

```
/home/hoang/.openclaw/
├── workspace/                          ← OpenClaw framework (8 files)
│   ├── SOUL.md, AGENTS.md, HEARTBEAT.md, TOOLS.md
│   ├── USER.md, IDENTITY.md, MEMORY.md, BOOTSTRAP.md
│   └── .gitignore
│
├── agents/trading/                     ← 12 subagent definitions (.md)
│   ├── market-analyst.md
│   ├── news-analyst.md
│   ├── social-analyst.md
│   ├── fundamentals-analyst.md
│   ├── bull-researcher.md
│   ├── bear-researcher.md
│   ├── research-manager.md
│   ├── trader.md
│   ├── aggressive-risk.md
│   ├── conservative-risk.md
│   ├── neutral-risk.md
│   └── portfolio-manager.md
│
├── openclaw/                           ← THE Python package (everything)
│   ├── __init__.py
│   ├── config.py                       ← load/save trading-config.json
│   ├── engine.py                       ← RunEngine: dispatch subagents
│   ├── callbacks.py                    ← RunCallback protocol
│   ├── database.py                     ← SQLite schema
│   ├── memory_persistence.py           ← BM25 ↔ SQLite sync
│   ├── memory.py                       ← MOVED from tradingagents/agents/utils/memory.py
│   ├── agent_states.py                 ← MOVED from tradingagents/agents/utils/agent_states.py
│   ├── dataflows/                      ← MOVED from tradingagents/dataflows/ (all 15 files)
│   │   ├── __init__.py
│   │   ├── interface.py                ← vendor routing (route_to_vendor)
│   │   ├── config.py                   ← thread-safe dataflow config singleton
│   │   ├── y_finance.py                ← yfinance OHLCV + stats
│   │   ├── yfinance_news.py            ← yfinance news
│   │   ├── alpha_vantage.py            ← alpha vantage entry
│   │   ├── alpha_vantage_common.py     ← shared AV utilities
│   │   ├── alpha_vantage_fundamentals.py
│   │   ├── alpha_vantage_indicator.py
│   │   ├── alpha_vantage_news.py
│   │   ├── alpha_vantage_stock.py
│   │   ├── databento_nq.py             ← databento futures data
│   │   ├── ict_indicators.py           ← 23 ICT indicator calculations
│   │   ├── stockstats_utils.py         ← stockstats wrappers
│   │   └── utils.py                    ← ticker mapping, date utils
│   └── tools/                          ← MOVED from tradingagents/agents/utils/*_tools.py
│       ├── __init__.py                 ← re-exports all tool functions
│       ├── core_stock_tools.py         ← get_stock_data (plain function, no @tool)
│       ├── technical_indicators_tools.py ← get_indicators
│       ├── fundamental_data_tools.py   ← get_fundamentals, get_balance_sheet, etc.
│       ├── news_data_tools.py          ← get_news, get_global_news, get_insider_transactions
│       └── ict_tools.py               ← get_ict_levels, get_live_price, etc.
│
├── dashboard/                          ← monitoring UI
│   ├── terminal/monitor.py             ← Rich: signal board
│   ├── terminal/analysis_viewer.py     ← Rich: full analysis view
│   └── web/                            ← MOVED from TradingAgents/webui/ (React + FastAPI)
│
├── tests/                              ← test suite
│   ├── test_config.py
│   ├── test_engine.py
│   ├── test_memory.py
│   └── test_dashboard.py
│
├── trading-config.json                 ← single config source
├── trading.db                          ← created at runtime
├── heartbeat-state.json                ← created at runtime
├── memory/                             ← daily markdown summaries
│
├── docs/                               ← kept reference docs
│   └── JADECAP_AGENTS.md
├── assets/                             ← kept documentation images
├── .env.example                        ← API key reference
├── LICENSE
└── README.md                           ← updated for merged system
```

**`TradingAgents/` directory: FULLY DELETED after extraction.** Nothing remains.

---

**Critical hook: `dispatch_fn`** — The RunEngine doesn't call LLMs directly. It accepts a `dispatch_fn(agent_name, prompt, model) -> response` callable. This is how OpenClaw (or any AI system) plugs in. Claude Code's Agent tool, GPT's function calling, or any custom dispatch can be used. The engine doesn't care HOW the AI runs — it only orchestrates WHAT runs in WHAT order with WHAT context.

**Pipeline (unchanged logic):**
```
TIER 1: Analysts (sequential)
  market-analyst → market_report
  social-analyst → sentiment_report
  news-analyst → news_report
  fundamentals-analyst → fundamentals_report

TIER 2: Bull/Bear Debate (N rounds)
  bull-researcher → "Bull Analyst: ..." argument
  bear-researcher → "Bear Analyst: ..." counter
  (repeat for max_debate_rounds)

TIER 3: Judge + Trader + Risk Debate
  research-manager → investment_plan
  trader → trader_investment_plan (BUY/HOLD/SELL proposal)
  aggressive-risk → aggressive view
  conservative-risk → conservative view
  neutral-risk → neutral view
  (repeat for max_risk_discuss_rounds)

TIER 4: Final Decision
  portfolio-manager → BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
```

---

## Cross-Cutting Concerns (built into relevant phases)

These 12 items must be addressed across the implementation. Each is assigned to a specific phase/task.

### CC-1: Environment Variables (.env loading) → Phase 2

After CLI deletion, `load_dotenv()` from `cli/main.py` is gone. API keys (ALPHA_VANTAGE_API_KEY, DATABENTO_API_KEY, OPENAI_API_KEY, etc.) must still be loadable.

**Solution:** Add `load_dotenv()` call to `openclaw/__init__.py`:
```python
# openclaw/__init__.py
from dotenv import load_dotenv
load_dotenv()  # Loads .env file at import time
```
This runs whenever any openclaw module is imported. The `.env` file at workspace root provides the keys.

**Add to Task 2.2** (create config loader): include dotenv loading in `openclaw/__init__.py`.

---

### CC-2: Data Cache Path → Phase 8.0

The old system cached market data at `TradingAgents/tradingagents/dataflows/data_cache/`. After moving dataflows to `openclaw/dataflows/`, the cache path changes.

**Solution:** In `trading-config.json`, add:
```json
"paths": {
    "data_cache_dir": "data_cache"
}
```
Update `openclaw/dataflows/config.py` (the thread-safe singleton) to read `data_cache_dir` from config instead of computing it relative to `__file__`. The `data_cache/` directory lives at workspace root.

**Add to Task 8.0** (move files): after moving dataflows, update the cache path reference in `dataflows/config.py`.

---

### CC-3: Error Recovery — No Lost Prior Work → Phase 4

If subagent #7 (trader) fails mid-pipeline, the 6 prior subagent outputs (4 reports + bull/bear debate) must NOT be lost.

**Solution:** RunEngine saves partial state to SQLite after EACH tier completes:
- After Tier 1: save all 4 reports to `reports` table
- After Tier 2: save debate history to `debates` table
- After Tier 3: save investment_plan + trader_plan + risk debate
- After Tier 4: save final_decision + signal

If any tier fails:
1. Save whatever was completed so far to SQLite (run status = "partial")
2. Write partial results to `memory/YYYY-MM-DD.md` with note: "Run failed at Tier X"
3. Return a RunResult with `signal="ERROR"` and `error_message` field
4. The partial run can be viewed in the dashboard (all completed reports visible)
5. User can choose to re-run (starts fresh) or inspect partial results

**Add to Task 4.2** (implement run): wrap each tier in try/except, persist partial state on failure.

```python
# In engine.run():
try:
    reports = self._run_tier1_analysts(...)
    self._persist_partial(run_id, "tier1", reports=reports)
except Exception as e:
    self._persist_partial(run_id, "tier1_failed", error=str(e))
    raise

try:
    debate = self._run_tier2_debate(...)
    self._persist_partial(run_id, "tier2", debate=debate)
except Exception as e:
    self._persist_partial(run_id, "tier2_failed", error=str(e))
    # reports from tier1 are ALREADY saved — not lost
    raise
```

---

### CC-4: Parallel Dispatch + Pipeline Flow → Phase 4

Within a single pipeline run, dispatch agents in parallel when they don't depend on each other. When they must wait, they wait.

**Parallel opportunities:**
- **Tier 1 (4 analysts):** ALL 4 dispatch simultaneously — they don't read each other's output. Wait for all to finish before Tier 2.
- **Tier 2 (debate):** Sequential — bear needs bull's argument to counter it.
- **Tier 3 (risk debate):** Sequential — conservative counters aggressive, neutral counters both.
- **Tier 4 (portfolio manager):** Sequential — needs everything.

**Solution:** `dispatch_fn` gets a parallel variant: `dispatch_parallel_fn`

```python
# RunEngine.run() accepts both:
def run(self, ticker, date, dispatch_fn=None, dispatch_parallel_fn=None, callbacks=None):
    ...

# dispatch_parallel_fn signature:
def dispatch_parallel_fn(agents: list[tuple[str, str, str]]) -> list[str]:
    """Dispatch multiple agents simultaneously.
    Args: list of (agent_name, prompt, model) tuples
    Returns: list of responses in same order
    """
```

**How Tier 1 uses it:**
```python
# If parallel dispatch available, use it for Tier 1:
if dispatch_parallel_fn:
    agent_calls = [
        ("market-analyst", market_prompt, market_model),
        ("social-analyst", social_prompt, social_model),
        ("news-analyst", news_prompt, news_model),
        ("fundamentals-analyst", fund_prompt, fund_model),
    ]
    responses = dispatch_parallel_fn(agent_calls)
    reports["market_report"] = responses[0]
    reports["sentiment_report"] = responses[1]
    reports["news_report"] = responses[2]
    reports["fundamentals_report"] = responses[3]
else:
    # Fallback: sequential dispatch (still works, just slower)
    for analyst_key in selected:
        ...
```

**How Claude Code provides parallel dispatch:**
```python
def claude_parallel_dispatch(agents):
    """Use Claude Code's Agent tool with run_in_background for parallel execution."""
    # Launch all agents in background
    tasks = []
    for name, prompt, model in agents:
        task = Agent(prompt=prompt, model=model, run_in_background=True)
        tasks.append(task)
    # Wait for all to complete, collect results
    return [task.result for task in tasks]
```

**Pipeline timing improvement:**
```
BEFORE (sequential):  Tier 1 = 4 × agent_time  →  ~8 min total
AFTER (parallel):     Tier 1 = 1 × agent_time  →  ~2 min total
Tier 2-4 unchanged:   always sequential          →  ~6 min
                                                    --------
Total:                                              ~8 min (was ~14 min)
```

**Each run still gets its own state** — local variables, not shared class state. SQLite WAL mode for concurrent DB writes if multiple pipeline runs happen to overlap.

**Add to Task 4.1:** Add `dispatch_parallel_fn` parameter to `RunEngine.run()`.
**Add to Task 4.2:** Implement Tier 1 parallel dispatch with sequential fallback.
**Add to Task 4.1:** Enable SQLite WAL mode in `init_db()`:
```python
conn.execute("PRAGMA journal_mode=WAL")
```

---

### CC-4b: Dispatch Timeout — No Stuck Agents → Phase 4

A subagent could hang forever (LLM API timeout, network issue). The pipeline must not get stuck.

**Solution:** `dispatch_fn` and `dispatch_parallel_fn` must have a timeout. If a subagent doesn't respond within the timeout, the engine treats it as a failure (triggers CC-3 error recovery — partial state saved, run marked as failed).

```python
# In RunEngine.run(), wrap every dispatch call:
import signal as signal_module

def _dispatch_with_timeout(self, dispatch_fn, agent_name, prompt, model, timeout_seconds=300):
    """Dispatch with a 5-minute timeout per agent. Raises TimeoutError if exceeded."""
    # For thread-based timeout:
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(dispatch_fn, agent_name, prompt, model)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Agent '{agent_name}' did not respond within {timeout_seconds}s")
```

**Default timeouts:**
- Analysts (Tier 1): 5 min each (they call data tools which can be slow)
- Researchers (Tier 2): 3 min each (LLM reasoning only, no tools)
- Managers (Tier 3): 5 min each (deep_think model, longer reasoning)
- Portfolio Manager (Tier 4): 5 min

**Configurable via trading-config.json:**
```json
"analysis": {
    "agent_timeout_seconds": 300
}
```

**Add to Task 4.2:** Wrap all dispatch calls with timeout. On timeout, trigger error recovery (CC-3).

---

### CC-4c: Sequential Reports — One at a Time Won't Stuck → Phase 4

For Tier 1 parallel dispatch: if one analyst is slow, the others don't wait for it individually. But if yfinance rate-limits during parallel calls, we need a fallback.

**Solution:** If `dispatch_parallel_fn` is not provided, Tier 1 runs sequentially (one at a time). This avoids yfinance rate-limiting from simultaneous calls. The parallel path is opt-in.

When running sequentially, each analyst completes fully before the next starts. If one gets stuck, the timeout (CC-4b) kills it and error recovery (CC-3) saves prior work.

```
Sequential Tier 1 (safe, no rate-limit risk):
  market-analyst → done → save report
  social-analyst → done → save report
  news-analyst → done → save report
  fundamentals → done → save report

If news-analyst times out:
  market_report: SAVED ✓
  sentiment_report: SAVED ✓
  news_report: FAILED ✗ (timeout)
  fundamentals: NOT STARTED (but prior 2 reports safe)
  Run status: "partial" — user sees 2 reports in dashboard
```

**Add to Task 4.2:** Sequential is the default. Parallel only when `dispatch_parallel_fn` explicitly provided.

---

### CC-5: API Key Validation → Phase 4

Before dispatching 12 subagents (expensive AI calls), validate that required API keys are set.

**Solution:** Add `_validate_keys()` check at the start of `run()`:
```python
def _validate_keys(self):
    """Check required API keys before running."""
    missing = []
    vendors = self.config.get("data_vendors", {})

    if "alpha_vantage" in str(vendors):
        if not os.environ.get("ALPHA_VANTAGE_API_KEY"):
            missing.append("ALPHA_VANTAGE_API_KEY")

    if "databento" in str(vendors):
        if not os.environ.get("DATABENTO_API_KEY"):
            missing.append("DATABENTO_API_KEY")

    # yfinance doesn't need an API key

    if missing:
        raise RuntimeError(f"Missing API keys: {', '.join(missing)}. Set them in .env file.")
```

**Add to Task 4.2:** Call `_validate_keys()` at start of `run()`, after halt check.

---

### CC-6: Heartbeat Handler Code → Phase 7 (new task)

HEARTBEAT.md describes the day-cycle schedule, but there's no Python code to actually execute it. The OpenClaw agent reads HEARTBEAT.md and acts on it, but it needs a helper.

**Solution:** Create `openclaw/heartbeat.py` with:
```python
def should_run_phase(config, heartbeat_state, phase):
    """Check if a heartbeat phase should run now.
    phase: 'pre_session' | 'during_session' | 'post_session'
    Returns: (should_run: bool, reason: str)
    """
    # Check halt flag
    # Check market hours vs current time
    # Check last run timestamp from heartbeat_state
    # Check if enough time elapsed since last check

def get_market_phase(config):
    """Return current market phase: 'pre' | 'open' | 'midday' | 'close' | 'post' | 'closed'"""
    # Based on config schedule.market_open/close and current time in config timezone

def update_heartbeat_state(state_path, phase, result):
    """Update heartbeat-state.json with latest check timestamp and results."""
```

The OpenClaw agent calls these during heartbeat polls to decide what to do.

**Add as Task 7.6:** Create `openclaw/heartbeat.py` with market phase detection and heartbeat state management.

---

### CC-7: Data Migration (existing WebUI users) → Phase 8 (new task)

Users who have existing `TradingAgents/webui/data/tradingagents.db` from the WebUI need their run history and memories migrated to the new `trading.db`.

**Solution:** Create `openclaw/migrate.py`:
```python
def migrate_from_webui(old_db_path, new_db_path):
    """Migrate existing WebUI database to new unified database.
    Copies: runs, reports, debates, memories tables.
    Skips: settings table (replaced by trading-config.json).
    """
```

**Add as Task 8.0.5** (between move and delete): Run migration script if old DB exists.

---

### CC-8: Logging → Phase 4

Old system used `print()` scattered throughout. New system needs structured logging.

**Solution:** Use Python's built-in `logging` module. Create logger in `openclaw/__init__.py`:
```python
import logging
logger = logging.getLogger("openclaw")
```

Each module uses `from openclaw import logger`. The RunEngine logs:
- INFO: run start/complete, signal produced, tier transitions
- WARNING: API key missing, subagent slow response, partial state saved
- ERROR: subagent failure, database write failure
- DEBUG: full prompts sent (useful for debugging, off by default)

The dashboard terminal monitor can tap into the logger for real-time display.

**Add to Task 4.1:** Set up logging in `openclaw/__init__.py`. Use `logger.info()` in engine.py instead of callbacks for internal events. Callbacks are for external consumers (UI), logging is for debugging.

---

### CC-9: Internal Dataflow Config Singleton → Phase 8.0

`dataflows/config.py` has a `get_config()` / `set_config()` singleton that `interface.py` calls internally. After moving to `openclaw/dataflows/`, this singleton needs to know about the new config system.

**Solution:** In `openclaw/engine.py`, before running any analysis, call:
```python
from openclaw.dataflows.config import set_config
set_config({
    "data_vendors": self.config["data_vendors"],
    "tool_vendors": self.config.get("tool_vendors", {}),
    "data_cache_dir": self.config["paths"].get("data_cache_dir", "data_cache"),
})
```

This bridges the new `trading-config.json` config into the old dataflow config singleton. The dataflows code doesn't need to change — it still calls `get_config()` internally.

**Add to Task 4.2:** Add `set_config()` call at start of `run()`.

---

### CC-10: WebUI memory_bridge.py Replacement → Phase 6.3

The existing `webui/backend/memory_bridge.py` does SQLite↔BM25 sync for the WebUI. After migration, `openclaw/memory_persistence.py` does the same thing. The WebUI's memory_bridge becomes dead code.

**Solution:** In Task 6.3 (migrate WebUI), update `dashboard/web/backend/runner.py` to:
- Import `from openclaw.memory_persistence import persist_memories, hydrate_memories` instead of using memory_bridge.py
- Delete `memory_bridge.py` from `dashboard/web/backend/`

**Add to Task 6.3:** explicit step to replace memory_bridge.py imports.

---

### CC-11: Real Dispatch Testing Guide → Phase 9

Tests use stub dispatch. Developers need guidance on testing with real AI.

**Solution:** Add to Phase 9 preamble:

**Testing with real dispatch (Claude Code):**
```python
from openclaw.engine import RunEngine

def claude_dispatch(agent_name, prompt, model):
    """Dispatch via Claude Code's Agent tool."""
    # This runs inside a Claude Code session
    # The Agent tool dispatches a subagent with the prompt
    result = Agent(prompt=prompt, model=model)
    return result

engine = RunEngine()
result = engine.run("NVDA", "2026-03-28", dispatch_fn=claude_dispatch)
```

**Testing with real dispatch (direct API):**
```python
import anthropic

client = anthropic.Anthropic()

def api_dispatch(agent_name, prompt, model):
    """Dispatch via direct Anthropic API call."""
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

engine = RunEngine()
result = engine.run("NVDA", "2026-03-28", dispatch_fn=api_dispatch)
```

---

### CC-12: BOOTSTRAP.md Disposition → Phase 7

BOOTSTRAP.md still exists in the repo (designed to be deleted after first onboarding). The merge doesn't trigger bootstrap — that's an OpenClaw lifecycle event, not a code merge.

**Solution:** Leave BOOTSTRAP.md as-is. It will be deleted when the user completes the OpenClaw onboarding conversation (per AGENTS.md protocol). The merge adds trading capabilities but doesn't replace the identity setup flow.

**No action needed.** Document this decision in the plan for clarity.

---

## Phase 1: Bug Fixes + Tool Cleanup (4 tasks)

**Why first:** These bugs are in `dataflows/` code we're KEEPING. If we don't fix them now, the merged system inherits them. The vendor fallback bug means a yfinance timeout crashes the entire pipeline instead of trying alpha_vantage. The ICT bug means 3 indicator functions are broken whenever columns are lowercase (which is the normal case after `_to_smc_format`). Task 1.4 removes the `@tool` LangChain decorator from all tool files — this is required for full subagent mode (zero LangChain dependency).

**Prerequisite:** Clone the repo locally. Ensure `cd TradingAgents && pip install -e .` works.

**Verification hook:** After this phase, run `python -m pytest tests/test_vendor_fallback.py tests/test_ict_columns.py -v` — all must pass.

### Task 1.1: Broaden vendor fallback

**Files:**
- Modify: `TradingAgents/tradingagents/dataflows/interface.py`
- Create: `tests/test_vendor_fallback.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vendor_fallback.py
import pytest
from unittest.mock import patch, MagicMock
from tradingagents.dataflows.interface import route_to_vendor


def test_fallback_on_network_error():
    """Vendor fallback should trigger on any exception, not just AlphaVantageRateLimitError."""
    with patch("tradingagents.dataflows.interface.get_config") as mock_config:
        mock_config.return_value = {
            "data_vendors": {"core_stock_apis": "alpha_vantage"},
            "tool_vendors": {},
        }
        with patch("tradingagents.dataflows.interface.VENDOR_METHODS", {
            "get_stock_data": {
                "alpha_vantage": MagicMock(side_effect=ConnectionError("timeout")),
                "yfinance": MagicMock(return_value="yfinance_data"),
            }
        }):
            result = route_to_vendor("get_stock_data", "AAPL", "2026-03-27")
            assert result == "yfinance_data"


def test_fallback_on_auth_error():
    """Vendor fallback should trigger on authentication errors."""
    with patch("tradingagents.dataflows.interface.get_config") as mock_config:
        mock_config.return_value = {
            "data_vendors": {"core_stock_apis": "alpha_vantage"},
            "tool_vendors": {},
        }
        with patch("tradingagents.dataflows.interface.VENDOR_METHODS", {
            "get_stock_data": {
                "alpha_vantage": MagicMock(side_effect=PermissionError("bad key")),
                "yfinance": MagicMock(return_value="yfinance_data"),
            }
        }):
            result = route_to_vendor("get_stock_data", "AAPL", "2026-03-27")
            assert result == "yfinance_data"


def test_all_vendors_fail_raises():
    """When all vendors fail, RuntimeError should be raised."""
    with patch("tradingagents.dataflows.interface.get_config") as mock_config:
        mock_config.return_value = {
            "data_vendors": {"core_stock_apis": "yfinance"},
            "tool_vendors": {},
        }
        with patch("tradingagents.dataflows.interface.VENDOR_METHODS", {
            "get_stock_data": {
                "yfinance": MagicMock(side_effect=ConnectionError("down")),
            }
        }):
            with pytest.raises(RuntimeError, match="No available vendor"):
                route_to_vendor("get_stock_data", "AAPL", "2026-03-27")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd TradingAgents && python -m pytest tests/test_vendor_fallback.py -v
```
Expected: `test_fallback_on_network_error` FAILS (ConnectionError propagates), `test_fallback_on_auth_error` FAILS (PermissionError propagates), `test_all_vendors_fail_raises` PASSES.

- [ ] **Step 3: Fix route_to_vendor**

In `TradingAgents/tradingagents/dataflows/interface.py`, find the `route_to_vendor` function and change:

```python
        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue  # Only rate limits trigger fallback
```

To:

```python
        try:
            return impl_func(*args, **kwargs)
        except Exception:
            continue  # Any failure triggers fallback to next vendor
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd TradingAgents && python -m pytest tests/test_vendor_fallback.py -v
```
Expected: ALL 3 PASS

- [ ] **Step 5: Commit**

```bash
git add TradingAgents/tradingagents/dataflows/interface.py tests/test_vendor_fallback.py
git commit -m "fix: broaden vendor fallback to catch all exceptions"
```

---

### Task 1.2: Fix ICT indicator Title-Case KeyError

**Files:**
- Modify: `TradingAgents/tradingagents/dataflows/ict_indicators.py`
- Create: `tests/test_ict_columns.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ict_columns.py
import pandas as pd
import pytest


def test_displacement_candle_lowercase_columns():
    """calc_displacement_candle should work with lowercase column names."""
    from tradingagents.dataflows.ict_indicators import calc_displacement_candle

    df = pd.DataFrame({
        "open": [100.0, 101.0, 105.0, 103.0, 108.0],
        "high": [102.0, 106.0, 110.0, 107.0, 112.0],
        "low": [99.0, 100.0, 104.0, 102.0, 106.0],
        "close": [101.0, 105.0, 109.0, 106.0, 111.0],
        "volume": [1000, 1200, 1500, 1100, 1800],
    }, index=pd.date_range("2026-03-23", periods=5, freq="1D"))

    # Should not raise KeyError
    result = calc_displacement_candle(df)
    assert result is not None


def test_liquidity_sweep_lowercase_columns():
    """calc_liquidity_sweep should work with lowercase column names."""
    from tradingagents.dataflows.ict_indicators import calc_liquidity_sweep

    df = pd.DataFrame({
        "open": [100.0, 101.0, 99.0, 102.0, 103.0],
        "high": [102.0, 103.0, 101.0, 104.0, 105.0],
        "low": [99.0, 100.0, 97.0, 101.0, 102.0],
        "close": [101.0, 102.0, 100.0, 103.0, 104.0],
        "volume": [1000, 1200, 1500, 1100, 1800],
    }, index=pd.date_range("2026-03-23", periods=5, freq="1D"))

    result = calc_liquidity_sweep(df)
    assert result is not None


def test_breaker_block_lowercase_columns():
    """calc_breaker_block should work with lowercase column names."""
    from tradingagents.dataflows.ict_indicators import calc_breaker_block

    df = pd.DataFrame({
        "open": [100.0, 103.0, 101.0, 104.0, 102.0, 105.0],
        "high": [104.0, 105.0, 103.0, 106.0, 104.0, 107.0],
        "low": [99.0, 101.0, 99.0, 102.0, 100.0, 103.0],
        "close": [103.0, 102.0, 102.0, 105.0, 103.0, 106.0],
        "volume": [1000, 1200, 1500, 1100, 1800, 2000],
    }, index=pd.date_range("2026-03-22", periods=6, freq="1D"))

    result = calc_breaker_block(df)
    assert result is not None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd TradingAgents && python -m pytest tests/test_ict_columns.py -v
```
Expected: FAIL with `KeyError: 'Open'` or `KeyError: 'High'`

- [ ] **Step 3: Fix the 3 functions**

In `TradingAgents/tradingagents/dataflows/ict_indicators.py`:

For `calc_displacement_candle`: add `df = _to_smc_format(df)` as the first line. Change all `row["Open"]` → `row["open"]`, `row["High"]` → `row["high"]`, `row["Low"]` → `row["low"]`, `row["Close"]` → `row["close"]`.

For `calc_liquidity_sweep`: same — add `df = _to_smc_format(df)`, change all Title-Case to lowercase.

For `calc_breaker_block`: same — add `df = _to_smc_format(df)`, change all Title-Case to lowercase.

- [ ] **Step 4: Run tests — expect PASS**

```bash
cd TradingAgents && python -m pytest tests/test_ict_columns.py -v
```

- [ ] **Step 5: Commit**

```bash
git add TradingAgents/tradingagents/dataflows/ict_indicators.py tests/test_ict_columns.py
git commit -m "fix: use lowercase column names in 3 ICT indicator functions"
```

---

### Task 1.3: Fix .gitignore

**Files:**
- Modify: `workspace/.gitignore` (or root `.gitignore`)

- [ ] **Step 1: Append entries**

Add these lines to `.gitignore`:

```
# OpenClaw private data
MEMORY.md
memory/
.claude/agent-memory/
.openclaw/
heartbeat-state.json

# Trading module runtime data
trading.db
trading-config.json
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "fix: protect memory files, trading DB, and config from git"
```

---

### Task 1.4: Remove @tool decorators from all tool files (zero LangChain)

**Why:** Full subagent mode means NO LangChain at all. The `@tool` decorator from `langchain_core.tools` wraps functions for LangChain agent consumption. Our subagents don't use LangChain — they call tools via Bash/Python or OpenClaw's tool system. The decorator is dead weight and keeps langchain-core as a dependency.

**Files to modify (8 files):**
- `TradingAgents/tradingagents/agents/utils/core_stock_tools.py`
- `TradingAgents/tradingagents/agents/utils/technical_indicators_tools.py`
- `TradingAgents/tradingagents/agents/utils/fundamental_data_tools.py`
- `TradingAgents/tradingagents/agents/utils/news_data_tools.py`
- `TradingAgents/tradingagents/agents/utils/ict_tools.py`
- `TradingAgents/tradingagents/agents/utils/agent_utils.py` (re-exports tools)
- `TradingAgents/tradingagents/agents/__init__.py` (imports from above)
- `TradingAgents/tradingagents/dataflows/config.py` (uses threading.Lock — check for langchain imports)

**In each tool file:**
- [ ] Remove `from langchain_core.tools import tool` import
- [ ] Remove `@tool` decorator from every function (keep the function + docstring as-is)
- [ ] The functions become plain Python functions — same signature, same behavior, no wrapper
- [ ] In `agent_utils.py`: remove any langchain re-exports, keep plain function re-exports
- [ ] In `agents/__init__.py`: remove any langchain-specific imports (like `create_react_agent` references)

**Also check for langchain imports in kept files:**
- [ ] `grep -r "langchain" TradingAgents/tradingagents/dataflows/` — should find nothing (dataflows don't use langchain)
- [ ] `grep -r "langchain" TradingAgents/tradingagents/agents/utils/` — after cleanup, should find nothing
- [ ] If any remaining langchain imports found in kept files, remove them

**Verification:**
- [ ] `python -c "from tradingagents.agents.utils.core_stock_tools import get_stock_data; print(type(get_stock_data))"` — should print `<class 'function'>` (not `StructuredTool`)
- [ ] `python -c "from tradingagents.agents.utils.ict_tools import get_ict_levels; print(type(get_ict_levels))"` — should print `<class 'function'>`
- [ ] `python -c "import tradingagents.agents.utils.core_stock_tools"` — should NOT trigger any langchain import
- [ ] `grep -r "from langchain" TradingAgents/tradingagents/agents/utils/` — should return NOTHING

**Test:**
- [ ] Create `tests/test_tool_cleanup.py`:
  - `test_no_langchain_import`: import each tool module, verify no `langchain` in `sys.modules`
  - `test_functions_are_plain`: verify `get_stock_data`, `get_indicators`, `get_news` are plain `function` type, not `StructuredTool`
  - `test_tools_still_callable`: call `get_stock_data("AAPL", "2026-03-27")` with mocked dataflow — verify it still returns data
- [ ] Run: `python -m pytest tests/test_tool_cleanup.py -v` — expect ALL PASS

- [ ] Commit

```bash
git add TradingAgents/tradingagents/agents/utils/ TradingAgents/tradingagents/agents/__init__.py
git commit -m "refactor: remove @tool langchain decorators from all tool files — plain Python functions"
```

---

### GATE 1: Verify before proceeding to Phase 2

**Run ALL of these. If ANY fails, fix before moving on.**

```bash
# 1. Vendor fallback test
cd TradingAgents && python -m pytest tests/test_vendor_fallback.py -v
# Expected: 3 PASSED

# 2. ICT column test
python -m pytest tests/test_ict_columns.py -v
# Expected: 3 PASSED

# 3. Tool cleanup test
python -m pytest tests/test_tool_cleanup.py -v
# Expected: 3 PASSED

# 4. Verify no langchain in tool files
grep -r "from langchain" TradingAgents/tradingagents/agents/utils/ --include="*.py"
# Expected: NO OUTPUT (nothing found)

# 5. Verify .gitignore has trading entries
grep "trading.db" .gitignore
# Expected: trading.db (found)
```

**Dispatch code-reviewer agent** on Phase 1 changes only. Fix any issues before continuing.

---

## Phase 2: Config System (3 tasks)

**Why:** Currently 3 separate config systems exist: `default_config.py` (Python dict), `jadecap_config.py` (module globals mutated by `apply_settings()`), and WebUI SQLite settings table. All three will be deleted. One JSON file replaces all of them.

**Key design:** `trading-config.json` is the user-editable file. `SCHEMA_DEFAULTS` in `config.py` provides defaults for every field. `load_config()` does a deep merge — user values override defaults, unspecified fields get defaults. This means the user only needs to specify what they want to change.

**Per-agent model resolution order:** `per_agent[agent_name]` > `deep_think`/`quick_think` (tier default) > `default` (global fallback). This preserves the old `deep_think_llm`/`quick_think_llm` split while adding per-agent granularity.

**Integration hook:** Every other phase reads config via `load_config()`. If the config schema changes, all downstream code adapts automatically because of the deep merge with defaults.

**Verification hook:** `python -m pytest tests/test_config.py -v` — all must pass. Also manually verify: edit `trading-config.json`, change strategy to "jadecap", reload config, verify strategy field changed.

### Task 2.1: Create trading-config.json

**Files:**
- Create: `trading-config.json`

- [ ] **Step 1: Write the config file**

```json
{
  "strategy": "default",
  "watchlist": [],

  "llm": {
    "default": "gpt-4o",
    "deep_think": "claude-opus-4-6",
    "quick_think": "gpt-4o-mini",
    "per_agent": {}
  },

  "data_vendors": {
    "core_stock_apis": "yfinance",
    "technical_indicators": "yfinance",
    "fundamental_data": "yfinance",
    "news_data": "yfinance"
  },

  "analysis": {
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "analysts": ["market", "social", "news", "fundamentals"]
  },

  "risk": {
    "max_loss_per_trade": 500,
    "daily_loss_limit": 1000,
    "max_drawdown_pct": 5,
    "max_consecutive_losses": 3,
    "min_risk_reward": 3
  },

  "jadecap": {
    "active_instrument": "NQ",
    "prop_firm": "apex",
    "hard_close_time": "15:45",
    "atr_stop_multiplier": 1.5,
    "t1_close_pct": 0.5,
    "sessions": {
      "asia": {"start": "20:00", "end": "00:00"},
      "london": {"start": "02:00", "end": "05:00"},
      "ny_am": {"start": "09:30", "end": "11:30"},
      "ny_pm": {"start": "13:00", "end": "16:00"}
    },
    "kill_zones": {
      "ny_am": {"start": "09:30", "end": "11:30"},
      "ny_pm": {"start": "13:00", "end": "16:00"},
      "silver_bullet_1": {"start": "10:00", "end": "11:00"},
      "silver_bullet_2": {"start": "14:00", "end": "15:00"}
    },
    "midday_avoidance": {"start": "11:30", "end": "13:00"},
    "instruments": {
      "NQ": {"ticker": "NQ=F", "point_value": 20, "description": "Nasdaq 100 E-mini Futures"},
      "ES": {"ticker": "ES=F", "point_value": 50, "description": "S&P 500 E-mini Futures"},
      "MNQ": {"ticker": "MNQ=F", "point_value": 2, "description": "Micro Nasdaq Futures"}
    }
  },

  "halt": false,

  "schedule": {
    "pre_session_analysis": false,
    "monitor_interval_min": 30,
    "post_session_reflect": false,
    "market_hours": {
      "stock": {"open": "09:30", "close": "16:00"},
      "futures": {"open": "18:00", "close": "17:00", "note": "nearly 24h, Sun 6PM - Fri 5PM ET"},
      "timezone": "US/Eastern",
      "use": "auto"
    }
  },

  "paths": {
    "database": "trading.db",
    "memory_dir": "memory",
    "results_dir": "results",
    "agents_dir": "agents/trading"
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add trading-config.json
git commit -m "feat: add trading-config.json as single config source"
```

---

### Task 2.2: Create config loader

**Files:**
- Create: `openclaw/__init__.py`
- Create: `openclaw/config.py`

- [ ] **Step 1: Create package init**

```python
# openclaw/__init__.py
"""OpenClaw trading module — subagent-based market analysis pipeline."""
```

- [ ] **Step 2: Write config.py**

```python
# openclaw/config.py
"""Unified config: JSON file + schema defaults.
Replaces default_config.py, jadecap_config.py globals, and WebUI settings table.
"""

import json
import os
import copy
from typing import Any, Dict, Optional


SCHEMA_DEFAULTS: Dict[str, Any] = {
    "strategy": "default",
    "watchlist": [],
    "llm": {
        "default": "gpt-4o",
        "deep_think": "claude-opus-4-6",
        "quick_think": "gpt-4o-mini",
        "per_agent": {},
    },
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "analysis": {
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "analysts": ["market", "social", "news", "fundamentals"],
    },
    "risk": {
        "max_loss_per_trade": 500,
        "daily_loss_limit": 1000,
        "max_drawdown_pct": 5,
        "max_consecutive_losses": 3,
        "min_risk_reward": 3,
    },
    "jadecap": {
        "active_instrument": "NQ",
        "prop_firm": "apex",
        "hard_close_time": "15:45",
        "atr_stop_multiplier": 1.5,
        "t1_close_pct": 0.5,
    },
    "halt": False,
    "schedule": {
        "pre_session_analysis": False,
        "monitor_interval_min": 30,
        "post_session_reflect": False,
        "market_open": "09:30",
        "market_close": "16:00",
        "timezone": "US/Eastern",
    },
    "paths": {
        "database": "trading.db",
        "memory_dir": "memory",
        "results_dir": "results",
        "agents_dir": "agents/trading",
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values win."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: str = "trading-config.json") -> Dict[str, Any]:
    """Load JSON config file, merge with schema defaults.
    If the file doesn't exist, returns schema defaults.
    """
    user_config: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r") as f:
            user_config = json.load(f)
    return deep_merge(SCHEMA_DEFAULTS, user_config)


def save_config(config: Dict[str, Any], path: str = "trading-config.json") -> None:
    """Save config to JSON file."""
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


def get_model_for_agent(config: Dict[str, Any], agent_name: str, tier: str = "quick") -> str:
    """Resolve which LLM model an agent should use.

    Priority: per_agent override > tier default > global default.

    Args:
        config: The loaded config dict
        agent_name: e.g., "market-analyst", "portfolio-manager"
        tier: "deep" for managers/PM, "quick" for analysts/researchers/debaters
    """
    llm = config.get("llm", {})
    # Check per-agent override first
    per_agent = llm.get("per_agent", {})
    if agent_name in per_agent:
        return per_agent[agent_name]
    # Fall back to tier default
    if tier == "deep":
        return llm.get("deep_think", llm.get("default", "gpt-4o"))
    return llm.get("quick_think", llm.get("default", "gpt-4o"))
```

- [ ] **Step 3: Commit**

```bash
git add openclaw/__init__.py openclaw/config.py
git commit -m "feat: add config loader with schema defaults and per-agent model resolution"
```

---

### Task 2.3: Test config

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_config.py
import json
import os
import tempfile
import pytest
from openclaw.config import load_config, save_config, deep_merge, get_model_for_agent, SCHEMA_DEFAULTS


def test_load_config_defaults():
    """Loading an empty config should return schema defaults."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        path = f.name
    try:
        config = load_config(path)
        assert config["strategy"] == "default"
        assert config["llm"]["default"] == "gpt-4o"
        assert config["analysis"]["max_debate_rounds"] == 1
        assert config["data_vendors"]["core_stock_apis"] == "yfinance"
        assert config["halt"] is False
        assert config["paths"]["database"] == "trading.db"
    finally:
        os.unlink(path)


def test_load_config_overrides():
    """User config should override defaults."""
    user = {"strategy": "jadecap", "llm": {"default": "claude-sonnet-4-6"}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(user, f)
        path = f.name
    try:
        config = load_config(path)
        assert config["strategy"] == "jadecap"
        assert config["llm"]["default"] == "claude-sonnet-4-6"
        # Non-overridden nested fields preserved
        assert config["llm"]["deep_think"] == "claude-opus-4-6"
        assert config["llm"]["quick_think"] == "gpt-4o-mini"
    finally:
        os.unlink(path)


def test_load_config_missing_file():
    """Missing config file should return defaults without error."""
    config = load_config("/nonexistent/path/config.json")
    assert config["strategy"] == "default"
    assert config["halt"] is False


def test_deep_merge_nested():
    """deep_merge should recursively merge nested dicts."""
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    override = {"a": {"b": 10, "e": 5}}
    result = deep_merge(base, override)
    assert result == {"a": {"b": 10, "c": 2, "e": 5}, "d": 3}


def test_deep_merge_does_not_mutate_base():
    """deep_merge should not modify the base dict."""
    base = {"a": {"b": 1}}
    override = {"a": {"b": 2}}
    deep_merge(base, override)
    assert base["a"]["b"] == 1


def test_save_and_reload(tmp_path):
    """save_config then load_config should roundtrip."""
    path = str(tmp_path / "test.json")
    config = load_config("/nonexistent")
    config["strategy"] = "jadecap"
    config["watchlist"] = ["NVDA", "AAPL"]
    save_config(config, path)
    reloaded = load_config(path)
    assert reloaded["strategy"] == "jadecap"
    assert reloaded["watchlist"] == ["NVDA", "AAPL"]


def test_get_model_for_agent_default():
    """Agent without per_agent override uses tier default."""
    config = SCHEMA_DEFAULTS.copy()
    assert get_model_for_agent(config, "market-analyst", "quick") == "gpt-4o-mini"
    assert get_model_for_agent(config, "portfolio-manager", "deep") == "claude-opus-4-6"


def test_get_model_for_agent_per_agent_override():
    """per_agent config overrides tier default."""
    config = deep_merge(SCHEMA_DEFAULTS, {
        "llm": {"per_agent": {"bull-researcher": "claude-sonnet-4-6"}}
    })
    assert get_model_for_agent(config, "bull-researcher", "quick") == "claude-sonnet-4-6"
    # Other agents still use tier default
    assert get_model_for_agent(config, "bear-researcher", "quick") == "gpt-4o-mini"
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_config.py -v
```
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_config.py
git commit -m "test: add config loader tests with defaults, overrides, merge, model resolution"
```

---

### GATE 2: Verify before proceeding to Phase 3

```bash
# 1. Config tests
python -m pytest tests/test_config.py -v
# Expected: ALL PASSED (defaults, overrides, missing file, deep merge, per-agent model)

# 2. Config file exists and is valid JSON
python -c "import json; json.load(open('trading-config.json')); print('VALID JSON')"
# Expected: VALID JSON

# 3. Config loader works
python -c "from openclaw.config import load_config; c = load_config(); print(c['strategy'], c['llm']['default'])"
# Expected: default gpt-4o

# 4. Per-agent model resolution
python -c "from openclaw.config import load_config, get_model_for_agent; c = load_config(); print(get_model_for_agent(c, 'portfolio-manager', 'deep'))"
# Expected: claude-opus-4-6 (or whatever deep_think is set to)
```

---

## Phase 3: Agent .md Files (12 tasks)

**Why:** This is the core of the subagent conversion. Each trading agent currently exists as a Python function (e.g., `create_market_analyst()`) that builds a LangChain agent with a system prompt, tools, and memory. We're converting each into a `.md` file that any AI system can read and execute.

**Critical:** The prompts MUST be copied VERBATIM from the existing Python files. Do NOT summarize, truncate, or rewrite them. The prompts contain carefully designed instructions (especially the JadeCap ICT prompts which are 200-300 lines with exact steps, scoring systems, and hard rules). Changing even one word could alter trading behavior.

**Where to get the prompts:** The full verbatim prompts were extracted by two background agents earlier in this session:
- Analysts + researchers (10 files): Look for the system prompt string in each `create_*` function. It's the f-string passed to `SystemMessage` or directly to `llm.invoke()`.
- Managers + risk + trader (12 files): Same pattern — find the prompt string.

**If the extracted outputs are lost** (session ended): Re-fetch each Python file from GitHub using `gh api repos/johnwick2921-cyber/openclaw-TradingAgents/contents/<PATH> --jq '.content' | base64 -d` and extract the prompt string manually.

**Strategy handling:** Each .md file has TWO prompt sections: `## Default Strategy Prompt` and `## JadeCap Strategy Prompt`. The RunEngine reads the appropriate section based on `config["strategy"]`. Agents without a JadeCap variant (social-analyst, fundamentals-analyst) have `N/A` for the JadeCap section.

**Frontmatter fields explained:**
- `model: null` — uses config default. Set to a specific model ID to override per-agent.
- `tools` — which Python @tool functions this agent can call. The RunEngine makes these available.
- `tools_jadecap` — different tool set for JadeCap strategy (some agents use ICT tools instead).
- `memory` — which BM25 memory store this agent queries. `null` = no memory.
- `tier: quick|deep` — determines which tier default model to use (`quick_think` or `deep_think`).
- `input` — what data this agent receives from prior pipeline stages.
- `output` — what state field this agent produces.

**Verification hook:** After creating all 12 files, verify: `ls agents/trading/*.md | wc -l` should output `12`. Open each file and confirm it has both strategy prompt sections and the frontmatter is valid YAML.

Each task creates one agent definition in `agents/trading/`. The prompts are extracted VERBATIM from the existing Python agent files.

### .md Agent File Format

```markdown
---
name: <agent-name>
model: null
tools: [tool1, tool2]
strategy_variants: [default, jadecap]
memory: <memory_store_name or null>
tier: quick|deep
input: [field1, field2]
output: field_name
---

# <Agent Role Name>

## Default Strategy Prompt
<full verbatim prompt>

## JadeCap Strategy Prompt
<full verbatim prompt or "N/A">

## Tools
- tool1: description

## Input Contract
- field1: description

## Output Contract
- field_name: description
```

### Task 3.1: market-analyst.md

- [ ] **Step 1: Create directory**

```bash
mkdir -p agents/trading
```

- [ ] **Step 2: Create agents/trading/market-analyst.md**

Write the file with frontmatter:
```yaml
---
name: market-analyst
model: null
tools: [get_stock_data, get_indicators]
tools_jadecap: [get_ict_levels, get_midnight_open_tool, get_killzone_status_tool, get_contract_size, get_live_price]
strategy_variants: [default, jadecap]
memory: null
memory_jadecap: invest_judge_memory
tier: quick
input: [company_of_interest, trade_date]
output: market_report
---
```

Then include the FULL verbatim default prompt (from `market_analyst.py` — the "You are a trading assistant tasked with analyzing financial markets..." prompt, ~40 lines).

Then include the FULL verbatim JadeCap prompt (from `market_analyst_jadecap.py` — the "You are a JadeCap ICT Market Analyst..." prompt, ~300 lines with all 10 steps).

Source: Read from agent task output `a596ce0eadaa54f64`, entries #1 and #2.

- [ ] **Step 3: Commit**

```bash
git add agents/trading/market-analyst.md
git commit -m "feat: add market-analyst subagent definition with default + jadecap prompts"
```

---

### Task 3.2: news-analyst.md

- [ ] Create `agents/trading/news-analyst.md`
- [ ] Frontmatter:
```yaml
name: news-analyst
model: null
tools: [get_news, get_global_news, get_insider_transactions]
tools_jadecap: [get_news, get_global_news]
strategy_variants: [default, jadecap]
memory: null
memory_jadecap: portfolio_manager_memory
tier: quick
input: [company_of_interest, trade_date]
output: news_report
```
- [ ] Default prompt source: `news_analyst.py` — "You are a news researcher tasked with analyzing recent news and trends..." (~5 lines). Includes tool usage instructions for `get_news(query, start_date, end_date)` and `get_global_news(curr_date, look_back_days, limit)`.
- [ ] JadeCap prompt source: `news_analyst_jadecap.py` — "You are a JadeCap Macro News Analyst for {active} Futures..." (~200 lines). Includes 4 steps: STEP 1 pull all news (with full NQ-specific event list), STEP 2 kill zone risk assessment (with HIGH/MEDIUM/LOW classification), STEP 3 macro bias (risk-on/risk-off), STEP 4 pre-market context. Includes holiday list, midday chop zone, AMD context, hard rules, and output format with summary table.
- [ ] Commit

### Task 3.3: social-analyst.md

- [ ] Create `agents/trading/social-analyst.md`
- [ ] Frontmatter:
```yaml
name: social-analyst
model: null
tools: [get_news]
strategy_variants: [default]
memory: null
tier: quick
input: [company_of_interest, trade_date]
output: sentiment_report
```
- [ ] Default prompt source: `social_media_analyst.py` — "You are a social media and company specific news researcher/analyst..." (~8 lines). Focuses on social media posts, company news, public sentiment. Uses `get_news(query, start_date, end_date)`.
- [ ] JadeCap section: `N/A` — social analyst not used in jadecap strategy (jadecap only uses market + news analysts)
- [ ] Commit

### Task 3.4: fundamentals-analyst.md

- [ ] Create `agents/trading/fundamentals-analyst.md`
- [ ] Frontmatter:
```yaml
name: fundamentals-analyst
model: null
tools: [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement]
strategy_variants: [default]
memory: null
tier: quick
input: [company_of_interest, trade_date]
output: fundamentals_report
```
- [ ] Default prompt source: `fundamentals_analyst.py` — "You are a researcher tasked with analyzing fundamental information..." (~6 lines). Covers financial documents, company profile, financials history. NOTE: source has a bug where system_message is a tuple `(string,)` — extract the string from the tuple.
- [ ] JadeCap section: `N/A` — fundamentals analyst not used in jadecap strategy
- [ ] Commit

### Task 3.5: bull-researcher.md

- [ ] Create `agents/trading/bull-researcher.md`
- [ ] Frontmatter:
```yaml
name: bull-researcher
model: null
tools: []
strategy_variants: [default, jadecap]
memory: bull_memory
tier: quick
input: [market_report, sentiment_report, news_report, fundamentals_report, debate_history, opponent_last_argument]
output: bull_argument (prefixed "Bull Analyst:")
```
- [ ] Default prompt source: `bull_researcher.py` — "You are a Bull Analyst advocating for investing in the stock..." (~20 lines). Covers growth potential, competitive advantages, positive indicators, bear counterpoints. Uses f-string with `{market_research_report}`, `{sentiment_report}`, `{news_report}`, `{fundamentals_report}`, `{history}`, `{current_response}`, `{past_memory_str}`.
- [ ] JadeCap prompt source: `bull_researcher_jadecap.py` — "You are the JadeCap Long Setup Analyst for {active} Futures..." (~350 lines). Covers 11 sections: HTF bias evidence, premium/discount, liquidity sweep, SFP confirmation, displacement, LTF entry setup (5 models + stacked FVGs + ADX filter + Silver Bullet), kill zone timing, draw on liquidity + IPDA, risk calculation + multi-TF confluence, macro alignment + holiday check, hard rule checklist (14 items) + A+ scoring (weighted 1-10), counter the short analyst, AMD context.
- [ ] **IMPORTANT:** The jadecap prompt contains exact setup requirements (`{bull_req}`), hard rules (`{hard_rules_str}`), kill zones (`{kz_str}`), and AMD context. These are runtime variables that the RunEngine must inject from `trading-config.json` jadecap section when dispatching.
- [ ] Commit

### Task 3.6: bear-researcher.md

- [ ] Create `agents/trading/bear-researcher.md`
- [ ] Frontmatter:
```yaml
name: bear-researcher
model: null
tools: []
strategy_variants: [default, jadecap]
memory: bear_memory
tier: quick
input: [market_report, sentiment_report, news_report, fundamentals_report, debate_history, opponent_last_argument]
output: bear_argument (prefixed "Bear Analyst:")
```
- [ ] Default prompt source: `bear_researcher.py` — "You are a Bear Analyst making the case against investing..." (~20 lines). Mirror of bull — covers risks, competitive weaknesses, negative indicators, bull counterpoints.
- [ ] JadeCap prompt source: `bear_researcher_jadecap.py` — "You are the JadeCap Short Setup Analyst for {active} Futures..." (~350 lines). Mirror of bull jadecap — same 11 sections but for SHORT setups. Uses `{bear_req}` instead of `{bull_req}`. Checks BSL (buy-side liquidity) instead of SSL. Requires premium zone instead of discount.
- [ ] Same runtime variable injection as bull-researcher
- [ ] Commit

### Task 3.7: research-manager.md

- [ ] Create `agents/trading/research-manager.md`
- [ ] Frontmatter:
```yaml
name: research-manager
model: null
tools: []
tools_jadecap: [fetch_live_price]
strategy_variants: [default, jadecap]
memory: invest_judge_memory
tier: deep
input: [debate_history, bull_history, bear_history, market_report, sentiment_report, news_report, fundamentals_report]
output: investment_plan + judge_decision
```
- [ ] Default prompt source: `research_manager.py` — "As the portfolio manager and debate facilitator, your role is to critically evaluate this round of debate..." (~15 lines). Must deliver: recommendation (Buy/Sell/Hold), rationale, strategic actions. Includes `{past_memory_str}`, `{instrument_context}`, `{history}`.
- [ ] JadeCap prompt source: `research_manager_jadecap.py` — "You are the JadeCap ICT Judge and Portfolio Manager for {active} Futures..." (~200 lines). 10-step process: read both analyst arguments, compare on 5 criteria (HTF bias, sweep, displacement, FVG/OB, premium/discount), verify setup requirements, verify kill zone/displacement/sweep/FVG, pre-trade checklist, advanced confluence checks (stacked FVGs, ADX filter, Silver Bullet, multi-TF), calculate entry/stop/target/contracts, hard rules final gate, if neither valid → NO TRADE, output in trade format.
- [ ] **Uses deep_think model** — set `tier: deep` in frontmatter
- [ ] Commit

### Task 3.8: trader.md

- [ ] Create `agents/trading/trader.md`
- [ ] Frontmatter:
```yaml
name: trader
model: null
tools: []
tools_jadecap: [fetch_live_price]
strategy_variants: [default, jadecap]
memory: trader_memory
tier: quick
input: [investment_plan, market_report, sentiment_report, news_report, fundamentals_report]
output: trader_investment_plan (ends with "FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**")
```
- [ ] Default prompt source: `trader.py` — uses TWO messages. System: "You are a trading agent analyzing market data..." (~4 lines). User: "Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}..." (~5 lines).
- [ ] JadeCap prompt source: `trader_jadecap.py` — uses TWO messages. System: "You are the JadeCap Trader Agent for {active} Futures..." (~200 lines, 10 steps: read plan, validate hard rules, if NO TRADE → HOLD, confirm entry/stop/target with IPDA check, ATR stop sizing with contract calculation, target management T1/T2, kill zone window + hard close, final news risk check, consecutive loss check, output in trade format). User: context with live price, point value, max risk, investment plan, all 4 reports.
- [ ] **IMPORTANT:** Trader jadecap prompt references `{half_risk_losses}`, `{max_streak}`, `{atr_mult}`, `{t1_pct}`, `{min_rr}`, `{max_loss}`, `{point_value}`, `{kz_str}`, `{checklist_str}`, `{hard_rules_str}`, `{TRADE_OUTPUT_FORMAT}` — all from jadecap config. RunEngine must inject these.
- [ ] Commit

### Task 3.9: aggressive-risk.md

- [ ] Create `agents/trading/aggressive-risk.md`
- [ ] Frontmatter:
```yaml
name: aggressive-risk
model: null
tools: []
tools_jadecap: [fetch_live_price]
strategy_variants: [default, jadecap]
memory: null
tier: quick
input: [trader_investment_plan, market_report, sentiment_report, news_report, fundamentals_report, risk_debate_history, conservative_last_argument, neutral_last_argument]
output: aggressive_risk_argument
```
- [ ] Default prompt source: `aggressive_debator.py` — "As the Aggressive Risk Analyst, your role is to actively champion high-reward, high-risk opportunities..." (~15 lines). Responds to conservative and neutral arguments with data-driven rebuttals.
- [ ] JadeCap prompt source: `aggressive_debator_jadecap.py` — "You are the JadeCap Aggressive Risk Analyst for NQ/ES Futures..." (~60 lines). 5 ICT-specific sections: setup confluence strength (stacked FVGs, Silver Bullet, A+ score), institutional footprint evidence, risk-reward asymmetry, counter conservative analyst, counter neutral analyst. Argues FOR trade execution.
- [ ] Commit

### Task 3.10: conservative-risk.md

- [ ] Create `agents/trading/conservative-risk.md`
- [ ] Frontmatter:
```yaml
name: conservative-risk
model: null
tools: []
tools_jadecap: [fetch_live_price]
strategy_variants: [default, jadecap]
memory: null
tier: quick
input: [trader_investment_plan, market_report, sentiment_report, news_report, fundamentals_report, risk_debate_history, aggressive_last_argument, neutral_last_argument]
output: conservative_risk_argument
```
- [ ] Default prompt source: `conservative_debator.py` — "As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility..." (~15 lines). Counters aggressive and neutral views with focus on risk mitigation.
- [ ] JadeCap prompt source: `conservative_debator_jadecap.py` — "You are the JadeCap Conservative Risk Analyst for NQ/ES Futures..." (~80 lines). 6 sections: checklist compliance (any fail = NO TRADE), structural risk (unfilled FVGs, unswept liquidity, ADX < 20), timing and session risk (kill zone edge, midday chop, hard close), news and macro risk (FOMC/CPI/NFP = NO TRADE, VIX levels), prop firm account protection (consecutive losses, daily P&L limits, trailing drawdown), counter aggressive analyst.
- [ ] Commit

### Task 3.11: neutral-risk.md

- [ ] Create `agents/trading/neutral-risk.md`
- [ ] Frontmatter:
```yaml
name: neutral-risk
model: null
tools: []
tools_jadecap: [fetch_live_price]
strategy_variants: [default, jadecap]
memory: null
tier: quick
input: [trader_investment_plan, market_report, sentiment_report, news_report, fundamentals_report, risk_debate_history, aggressive_last_argument, conservative_last_argument]
output: neutral_risk_argument
```
- [ ] Default prompt source: `neutral_debator.py` — "As the Neutral Risk Analyst, your role is to provide a balanced perspective..." (~15 lines). Challenges both aggressive and conservative, advocates for moderate approach.
- [ ] JadeCap prompt source: `neutral_debator_jadecap.py` — "You are the JadeCap Neutral Risk Analyst for NQ/ES Futures..." (~70 lines). 6 sections: A+ score verification (walk through each criterion with weighted scoring), sizing recommendation (8-10 full, 6-7 standard, 4-5 reduced, <4 no trade), what each side got right, what each side got wrong, conditional recommendation (multi-TF, ADX, consecutive losses, Silver Bullet), final verdict (EXECUTE at X% / REDUCE to X% / PASS).
- [ ] Commit

### Task 3.12: portfolio-manager.md

- [ ] Create `agents/trading/portfolio-manager.md`
- [ ] Frontmatter:
```yaml
name: portfolio-manager
model: null
tools: []
tools_jadecap: [fetch_live_price]
strategy_variants: [default, jadecap]
memory: portfolio_manager_memory
tier: deep
input: [risk_debate_history, aggressive_history, conservative_history, neutral_history, market_report, sentiment_report, news_report, fundamentals_report, investment_plan, trader_investment_plan]
output: final_trade_decision (BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL)
```
- [ ] Default prompt source: `portfolio_manager.py` — "As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision..." (~20 lines). Rating scale: Buy/Overweight/Hold/Underweight/Sell. Required output: rating, executive summary, investment thesis.
- [ ] JadeCap prompt source: `portfolio_manager_jadecap.py` — "You are the JadeCap Portfolio Manager — the FINAL decision authority for {active} Futures..." (~250 lines). 9 steps: read full risk debate, read trader's plan, apply 5-tier ICT rating scale (BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL with detailed criteria), verify hard rules final time, calculate final contracts from risk consensus (all agree = full, 2/3 = 75%, no consensus = 50% or HOLD) + ADX adjustment + consecutive loss adjustment, include entry/stop/target/contracts/R:R, if NO TRADE from prior agents → enforce HOLD, pre-trade checklist final status, output final trade decision in trade format.
- [ ] **Uses deep_think model** — set `tier: deep`
- [ ] **IMPORTANT:** This is the FINAL agent. Its output IS the pipeline result. The RunEngine extracts the signal from this response.
- [ ] Commit

### Task 3.13: Verify all 12 agent files

- [ ] Run: `ls agents/trading/*.md | wc -l` — must output `12`
- [ ] For each file: verify frontmatter is valid YAML, both strategy sections present, tools listed match source
- [ ] Commit all if not already committed individually

---

### GATE 3: Verify before proceeding to Phase 4

```bash
# 1. Count agent files
ls agents/trading/*.md | wc -l
# Expected: 12

# 2. Verify each file has both strategy sections
for f in agents/trading/*.md; do
  echo "$f:"
  grep -c "## Default Strategy Prompt" "$f"
  grep -c "## JadeCap Strategy Prompt" "$f"
done
# Expected: each file shows 1 and 1 (or 1 and 0 for social/fundamentals which have N/A)

# 3. Verify frontmatter is parseable
python -c "
import yaml, glob
for f in glob.glob('agents/trading/*.md'):
    with open(f) as fh:
        content = fh.read()
    if content.startswith('---'):
        fm = content.split('---')[1]
        data = yaml.safe_load(fm)
        print(f'{f}: {data[\"name\"]} ok')
"
# Expected: 12 lines, all "ok"

# 4. Verify prompts are NOT truncated (spot check — longest files)
wc -l agents/trading/bull-researcher.md agents/trading/market-analyst.md agents/trading/portfolio-manager.md
# Expected: bull ~400+ lines, market ~350+ lines, portfolio ~300+ lines (JadeCap prompts are long)
```

**Manual review:** Open `agents/trading/bull-researcher.md` and verify the JadeCap prompt contains all 11 sections with exact price level placeholders (`{bull_req}`, `{hard_rules_str}`, etc.)

---

## Phase 4: Orchestrator — RunEngine (7 tasks)

**Why:** This is the brain of the merged system. It replaces `TradingAgentsGraph` (the old LangGraph orchestrator) with a simpler dispatch-based approach. Instead of building a compiled state graph, the RunEngine reads agent .md files and calls `dispatch_fn` for each step in sequence.

**Critical design: `dispatch_fn`** — The RunEngine does NOT call any LLM directly. It accepts a callable `dispatch_fn(agent_name: str, prompt: str, model: str) -> str`. This is the **main hook** — the caller provides their own AI dispatch mechanism:
- **Claude Code:** The main OpenClaw agent uses the `Agent` tool to dispatch subagents
- **Custom script:** Could use the Anthropic/OpenAI SDK directly
- **Testing:** A stub that returns canned responses

This design makes the engine AI-agnostic. It orchestrates the PIPELINE, not the AI calls.

**State passing between agents:** Unlike LangGraph (shared memory), subagents receive context via their prompt. The RunEngine accumulates results (reports, debate history, plans) and includes relevant context in each subsequent agent's prompt. This uses more tokens but gives each agent full access to OpenClaw tools (WebSearch, etc.).

**Debate loop logic (preserved from original):**
- Bull/Bear: dispatch bull → dispatch bear → increment count → if `count < 2 * max_debate_rounds` → repeat. With `max_debate_rounds=1` (default), exactly 1 bull + 1 bear argument.
- Risk: aggressive → conservative → neutral → increment count → if `count < 3 * max_risk_rounds` → repeat. With `max_risk_rounds=1` (default), exactly 1 round of all 3.

**Signal extraction:** The portfolio manager's response contains the final signal. The engine parses it looking for: `FINAL TRANSACTION PROPOSAL: **BUY**` pattern, or `Rating: SELL`, or just the last occurrence of BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL in the text. Fallback: HOLD.

**Error handling:** If any subagent dispatch fails, the engine calls `callback.on_error(e)` and re-raises. Partial state is NOT persisted — the run is all-or-nothing. This matches the original LangGraph behavior.

**Verification hook:** `python -m pytest tests/test_engine.py -v` — all pass. Also: manually call `engine.run("NVDA", "2026-03-27")` with the default stub dispatch and verify it completes without errors and returns a RunResult with signal="HOLD" (stub responses don't contain signal words, so fallback kicks in).

### Task 4.1: Create RunEngine skeleton

**Files:**
- Create: `openclaw/engine.py`

- [ ] **Step 1: Write RunEngine**

```python
# openclaw/engine.py
"""Unified RunEngine: dispatches subagents in the 4-tier trading pipeline."""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from openclaw.config import load_config, save_config, get_model_for_agent


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

    def run(self, ticker: str, date: str, dispatch_fn=None, callbacks=None) -> RunResult:
        """Run a full trading analysis pipeline.

        Args:
            ticker: Stock/futures symbol (e.g., "NVDA", "NQ")
            date: Trade date (e.g., "2026-03-27")
            dispatch_fn: Callable(agent_name, prompt, model) -> str response.
                         This is how the caller's AI system dispatches subagents.
                         If None, uses a default print-based stub.
            callbacks: Optional list of RunCallback objects for event streaming.

        Returns:
            RunResult with signal, reports, debates, and metadata.
        """
        if self.config.get("halt"):
            raise RuntimeError("Analysis is halted. Call engine.resume() to re-enable.")

        callbacks = callbacks or []
        dispatch = dispatch_fn or self._default_dispatch
        self._running = True
        start_time = datetime.now()

        for cb in callbacks:
            cb.on_run_start(ticker, date)

        try:
            strategy = self.config["strategy"]
            agents_dir = self.config["paths"]["agents_dir"]

            # ─── TIER 1: ANALYSTS ─────────────────────────────────
            reports = {}
            analyst_map = {
                "market": ("market-analyst", "market_report"),
                "social": ("social-analyst", "sentiment_report"),
                "news": ("news-analyst", "news_report"),
                "fundamentals": ("fundamentals-analyst", "fundamentals_report"),
            }
            selected = self.config["analysis"]["analysts"]

            for analyst_key in selected:
                if analyst_key not in analyst_map:
                    continue
                agent_name, report_field = analyst_map[analyst_key]
                model = get_model_for_agent(self.config, agent_name, "quick")

                prompt = self._build_analyst_prompt(
                    agents_dir, agent_name, strategy, ticker, date
                )
                for cb in callbacks:
                    cb.on_agent_status(agent_name, "running")

                response = dispatch(agent_name, prompt, model)
                reports[report_field] = response

                for cb in callbacks:
                    cb.on_report_section(report_field, response)
                    cb.on_agent_status(agent_name, "completed")

            # ─── TIER 2: BULL/BEAR DEBATE ─────────────────────────
            debate = self._run_debate(
                agents_dir, strategy, ticker, date, reports, dispatch, callbacks
            )

            # ─── TIER 3: JUDGE + TRADER + RISK ────────────────────
            investment_plan, trader_plan, risk_debate = self._run_judge_trader_risk(
                agents_dir, strategy, ticker, date, reports, debate, dispatch, callbacks
            )

            # ─── TIER 4: PORTFOLIO MANAGER ────────────────────────
            final_decision = self._run_portfolio_manager(
                agents_dir, strategy, ticker, date, reports, debate,
                investment_plan, trader_plan, risk_debate, dispatch, callbacks
            )

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

            for cb in callbacks:
                cb.on_run_complete(result)

            return result

        except Exception as e:
            for cb in callbacks:
                cb.on_error(e)
            raise
        finally:
            self._running = False

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
                reports_context, debate, "bull"
            )
            model = get_model_for_agent(self.config, "bull-researcher", "quick")
            for cb in callbacks:
                cb.on_agent_status("bull-researcher", "running")

            bull_response = dispatch("bull-researcher", bull_prompt, model)
            debate["bull_history"] += f"\n{bull_response}"
            debate["history"] += f"\nBull Analyst: {bull_response}"
            debate["count"] += 1

            for cb in callbacks:
                cb.on_debate_turn("Bull Analyst", bull_response)
                cb.on_agent_status("bull-researcher", "completed")

            # Bear counters
            bear_prompt = self._build_researcher_prompt(
                agents_dir, "bear-researcher", strategy, ticker, date,
                reports_context, debate, "bear"
            )
            model = get_model_for_agent(self.config, "bear-researcher", "quick")
            for cb in callbacks:
                cb.on_agent_status("bear-researcher", "running")

            bear_response = dispatch("bear-researcher", bear_prompt, model)
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
        )
        model = get_model_for_agent(self.config, "research-manager", "deep")
        for cb in callbacks:
            cb.on_agent_status("research-manager", "running")

        investment_plan = dispatch("research-manager", manager_prompt, model)

        for cb in callbacks:
            cb.on_agent_status("research-manager", "completed")

        # Trader proposes
        trader_prompt = self._build_prompt_with_context(
            agents_dir, "trader", strategy,
            ticker=ticker, date=date,
            reports=reports_context,
            investment_plan=investment_plan,
        )
        model = get_model_for_agent(self.config, "trader", "quick")
        for cb in callbacks:
            cb.on_agent_status("trader", "running")

        trader_plan = dispatch("trader", trader_prompt, model)

        for cb in callbacks:
            cb.on_agent_status("trader", "completed")

        # Risk debate: aggressive → conservative → neutral (N rounds)
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

                response = dispatch(agent_name, prompt, model)
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
        )
        model = get_model_for_agent(self.config, "portfolio-manager", "deep")
        for cb in callbacks:
            cb.on_agent_status("portfolio-manager", "running")

        response = dispatch("portfolio-manager", prompt, model)

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
        return f"""Analyze {ticker} for trade date {date}.

{prompt_text}

Company/Instrument: {ticker}
Trade Date: {date}
"""

    def _build_researcher_prompt(self, agents_dir, agent_name, strategy,
                                  ticker, date, reports_context, debate, side):
        """Build a prompt for bull/bear researcher."""
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        opponent_history = debate["bear_history"] if side == "bull" else debate["bull_history"]
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
        """Build a prompt for any agent with arbitrary context fields."""
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        context_str = "\n".join(f"{k}: {v}" for k, v in context.items() if v)
        return f"""{prompt_text}

{context_str}
"""

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

    def _default_dispatch(self, agent_name: str, prompt: str, model: str) -> str:
        """Default dispatch stub — prints and returns placeholder."""
        print(f"[DISPATCH] {agent_name} (model: {model})")
        print(f"[PROMPT] {prompt[:200]}...")
        return f"[Stub response from {agent_name}]"

    def reflect(self, ticker: str, date: str, dispatch_fn=None):
        """Post-session: fetch actual price, compare signal, reflect, persist."""
        import yfinance as yf

        # Fetch actual closing price
        stock = yf.Ticker(ticker)
        hist = stock.history(start=date, end=date, interval="1d")
        if hist.empty:
            return {"error": f"No price data for {ticker} on {date}"}

        actual_close = float(hist["Close"].iloc[0])

        # TODO: Load today's signal from database
        # TODO: Compare signal vs actual price movement
        # TODO: Dispatch reflection subagent
        # TODO: Persist outcome to database
        # TODO: Write summary to memory/YYYY-MM-DD.md

        return {
            "ticker": ticker,
            "date": date,
            "actual_close": actual_close,
            "status": "reflection_stub",
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
```

- [ ] **Step 2: Commit**

```bash
git add openclaw/engine.py
git commit -m "feat: add RunEngine with 4-tier subagent dispatch pipeline"
```

---

### Task 4.7: Create callbacks + test engine

**Files:**
- Create: `openclaw/callbacks.py`
- Create: `tests/test_engine.py`

- [ ] **Step 1: Write callbacks**

```python
# openclaw/callbacks.py
"""Callback protocol for RunEngine event streaming."""

from typing import Protocol, Any


class RunCallback(Protocol):
    """Protocol that frontends implement to receive run events."""
    def on_run_start(self, ticker: str, date: str) -> None: ...
    def on_agent_status(self, agent: str, status: str) -> None: ...
    def on_report_section(self, name: str, content: str) -> None: ...
    def on_debate_turn(self, speaker: str, argument: str) -> None: ...
    def on_signal(self, signal: str) -> None: ...
    def on_run_complete(self, result: Any) -> None: ...
    def on_error(self, error: Exception) -> None: ...


class PrintCallback:
    """Simple callback that prints events to stdout."""
    def on_run_start(self, ticker, date):
        print(f"\n{'='*50}")
        print(f"Starting analysis: {ticker} on {date}")
        print(f"{'='*50}")

    def on_agent_status(self, agent, status):
        print(f"  [{agent}] {status}")

    def on_report_section(self, name, content):
        print(f"  Report ready: {name} ({len(content)} chars)")

    def on_debate_turn(self, speaker, argument):
        print(f"  Debate: {speaker} ({len(argument)} chars)")

    def on_signal(self, signal):
        print(f"\n  >>> SIGNAL: {signal} <<<\n")

    def on_run_complete(self, result):
        print(f"Analysis complete: {result.signal} ({result.duration_seconds:.1f}s)")

    def on_error(self, error):
        print(f"  ERROR: {error}")


class CollectorCallback:
    """Callback that collects all events for testing."""
    def __init__(self):
        self.events = []

    def on_run_start(self, ticker, date):
        self.events.append(("run_start", ticker, date))

    def on_agent_status(self, agent, status):
        self.events.append(("agent_status", agent, status))

    def on_report_section(self, name, content):
        self.events.append(("report", name, len(content)))

    def on_debate_turn(self, speaker, argument):
        self.events.append(("debate", speaker, len(argument)))

    def on_signal(self, signal):
        self.events.append(("signal", signal))

    def on_run_complete(self, result):
        self.events.append(("complete", result.signal))

    def on_error(self, error):
        self.events.append(("error", str(error)))
```

- [ ] **Step 2: Write engine tests**

```python
# tests/test_engine.py
import json
import os
import tempfile
import pytest
from openclaw.engine import RunEngine, RunResult
from openclaw.callbacks import CollectorCallback


@pytest.fixture
def config_file(tmp_path):
    """Create a minimal config file for testing."""
    config = {
        "strategy": "default",
        "halt": False,
        "analysis": {
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "analysts": ["market"],
        },
        "paths": {
            "agents_dir": str(tmp_path / "agents" / "trading"),
            "database": str(tmp_path / "test.db"),
            "memory_dir": str(tmp_path / "memory"),
            "results_dir": str(tmp_path / "results"),
        },
    }
    path = str(tmp_path / "test-config.json")
    with open(path, "w") as f:
        json.dump(config, f)

    # Create a minimal agent .md file
    agents_dir = tmp_path / "agents" / "trading"
    agents_dir.mkdir(parents=True)
    for name in ["market-analyst", "bull-researcher", "bear-researcher",
                  "research-manager", "trader", "aggressive-risk",
                  "conservative-risk", "neutral-risk", "portfolio-manager"]:
        (agents_dir / f"{name}.md").write_text(f"""---
name: {name}
---
# {name}
## Default Strategy Prompt
You are {name}. Analyze the data and respond.
## JadeCap Strategy Prompt
N/A
""")
    return path


def test_engine_loads_config(config_file):
    engine = RunEngine(config_path=config_file)
    assert engine.config["strategy"] == "default"
    assert engine.config["halt"] is False


def test_engine_halted_blocks_run(config_file):
    engine = RunEngine(config_path=config_file)
    engine.halt()
    with pytest.raises(RuntimeError, match="halted"):
        engine.run("NVDA", "2026-03-27")


def test_engine_halt_and_resume(config_file):
    engine = RunEngine(config_path=config_file)
    engine.halt()
    assert engine.config["halt"] is True
    assert engine.status["state"] == "halted"

    engine.resume()
    assert engine.config["halt"] is False
    assert engine.status["state"] == "idle"


def test_engine_run_with_stub_dispatch(config_file):
    """Full pipeline with stub dispatch should complete without errors."""
    engine = RunEngine(config_path=config_file)
    collector = CollectorCallback()

    result = engine.run("NVDA", "2026-03-27", callbacks=[collector])

    assert isinstance(result, RunResult)
    assert result.ticker == "NVDA"
    assert result.date == "2026-03-27"
    assert result.signal in ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
    assert result.duration_seconds > 0

    # Verify events were emitted
    event_types = [e[0] for e in collector.events]
    assert "run_start" in event_types
    assert "signal" in event_types
    assert "complete" in event_types


def test_engine_extract_signal():
    engine = RunEngine.__new__(RunEngine)
    assert engine._extract_signal("FINAL TRANSACTION PROPOSAL: **BUY**") == "BUY"
    assert engine._extract_signal("Rating: SELL\nSome explanation") == "SELL"
    assert engine._extract_signal("I recommend we HOLD for now") == "HOLD"
    assert engine._extract_signal("OVERWEIGHT based on analysis") == "OVERWEIGHT"
    assert engine._extract_signal("no clear signal here") == "HOLD"  # fallback


def test_engine_debate_terminates(config_file):
    """Debate should run exactly max_debate_rounds times."""
    engine = RunEngine(config_path=config_file)
    call_count = {"bull": 0, "bear": 0}

    def counting_dispatch(agent_name, prompt, model):
        if "bull" in agent_name:
            call_count["bull"] += 1
        elif "bear" in agent_name:
            call_count["bear"] += 1
        return f"[Response from {agent_name}]"

    engine.run("NVDA", "2026-03-27", dispatch_fn=counting_dispatch)

    assert call_count["bull"] == 1  # max_debate_rounds = 1
    assert call_count["bear"] == 1
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_engine.py -v
```
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add openclaw/callbacks.py tests/test_engine.py
git commit -m "feat: add callbacks protocol and engine tests"
```

---

### GATE 4: Verify before proceeding to Phase 5

```bash
# 1. Engine tests
python -m pytest tests/test_engine.py -v
# Expected: ALL PASSED (config load, halt blocks, halt/resume, stub dispatch completes, signal extraction, debate terminates)

# 2. Engine creates and loads config
python -c "from openclaw.engine import RunEngine; e = RunEngine(); print(e.status)"
# Expected: {'state': 'idle', 'strategy': 'default', ...}

# 3. Engine halt/resume
python -c "
from openclaw.engine import RunEngine
e = RunEngine()
e.halt()
print('halted:', e.status['state'])
e.resume()
print('resumed:', e.status['state'])
"
# Expected: halted: halted, resumed: idle

# 4. Engine runs with stub dispatch (no real AI needed)
python -c "
from openclaw.engine import RunEngine
e = RunEngine()
result = e.run('NVDA', '2026-03-28')
print('signal:', result.signal, 'duration:', round(result.duration_seconds, 2))
"
# Expected: signal: HOLD (stub), duration: ~0.01s

# 5. Callbacks fire
python -c "
from openclaw.engine import RunEngine
from openclaw.callbacks import CollectorCallback
e = RunEngine()
cb = CollectorCallback()
e.run('NVDA', '2026-03-28', callbacks=[cb])
print('events:', len(cb.events))
print('types:', set(ev[0] for ev in cb.events))
"
# Expected: events: 20+ (run_start, agent_status x many, report, debate, signal, complete)
```

**Dispatch code-reviewer agent** on Phase 4 code (engine.py + callbacks.py). Fix any issues.

---

## Phase 5: Memory + Outcomes (4 tasks)

**Why:** TradingAgents' BM25 memories are currently RAM-only — lost when the process exits. The WebUI has a `memory_bridge.py` that syncs to SQLite, but it's WebUI-specific. We need a unified persistence layer that all frontends share.

**Memory flow:**
1. **Before run:** `hydrate_memories()` loads all stored (situation, recommendation) pairs from SQLite into BM25 in-memory stores (one per agent role: bull, bear, trader, judge, portfolio)
2. **During run:** Subagents query BM25 via `memory.get_memories(current_situation, n_matches=2)` — this returns the most relevant past lessons
3. **After reflect:** `persist_memories()` writes new BM25 entries back to SQLite. Deduplication: checks if exact (situation, recommendation) pair already exists before inserting.

**Outcome tracking (NEW — not in original TradingAgents):**
After market close, the engine fetches the actual closing price via yfinance, compares it to the signal (BUY + price went up = correct), and stores the comparison + an LLM reflection in the `outcomes` table. This creates a feedback loop: future agents can learn from past hits and misses.

**Database location:** `trading.db` (configurable via `config["paths"]["database"]`). Same file used by the migrated WebUI for runs/reports/debates tables.

**Markdown summaries:** After each run, a human-readable summary is appended to `memory/YYYY-MM-DD.md`. This is what the OpenClaw agent reads during session startup — it's the bridge between SQLite (machine-readable) and OpenClaw's file-based memory (human-readable).

**Existing code reuse:** `FinancialSituationMemory` from `tradingagents/agents/utils/memory.py` is used as-is. Its API: `add_situations([(situation, recommendation)])`, `get_memories(query, n_matches)`, `clear()`. We only add persistence around it.

**Verification hook:** `python -m pytest tests/test_memory.py -v` — roundtrip test must pass. Also: manually check `trading.db` with `sqlite3 trading.db "SELECT count(*) FROM memories"` after a run.

### Task 5.1: Create database schema

**Files:**
- Create: `openclaw/database.py`

- [ ] **Step 1: Write database.py**

```python
# openclaw/database.py
"""SQLite database for trading runs, memories, and outcomes."""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'default',
    signal TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    error_message TEXT,
    duration_seconds REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    section_name TEXT NOT NULL,
    content TEXT
);

CREATE TABLE IF NOT EXISTS debates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    debate_type TEXT NOT NULL,
    full_history TEXT,
    side_a_history TEXT,
    side_b_history TEXT,
    side_c_history TEXT,
    judge_decision TEXT
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    situation TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    signal TEXT NOT NULL,
    actual_close REAL,
    actual_change_pct REAL,
    correct INTEGER,
    reflection TEXT,
    created_at TEXT NOT NULL
);
"""


def init_db(db_path: str) -> None:
    """Initialize the database, creating tables if they do not exist."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_CREATE_TABLES_SQL)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()


@contextmanager
def get_db(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a sqlite3 connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 2: Commit**

```bash
git add openclaw/database.py
git commit -m "feat: add SQLite database schema for runs, memories, outcomes"
```

---

### Task 5.2: Create memory persistence

**Files:**
- Create: `openclaw/memory_persistence.py`

- [ ] **Step 1: Write memory_persistence.py**

```python
# openclaw/memory_persistence.py
"""Sync BM25 FinancialSituationMemory ↔ SQLite."""

import sqlite3
from datetime import datetime, timezone
from typing import Dict

# Import from the kept TradingAgents code
from tradingagents.agents.utils.memory import FinancialSituationMemory


def persist_memories(
    memories: Dict[str, FinancialSituationMemory],
    db_path: str,
    run_id: str = "",
) -> int:
    """Write all BM25 memory contents to SQLite.

    Returns the number of new entries written.
    """
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    count = 0

    for name, mem in memories.items():
        for situation, recommendation in zip(mem.documents, mem.recommendations):
            # Check if this exact entry already exists (avoid duplicates)
            existing = conn.execute(
                "SELECT id FROM memories WHERE agent_name = ? AND situation = ? AND recommendation = ?",
                (name, situation, recommendation),
            ).fetchone()
            if existing:
                continue

            conn.execute(
                "INSERT INTO memories (agent_name, situation, recommendation, run_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, situation, recommendation, run_id, now),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def hydrate_memories(
    memories: Dict[str, FinancialSituationMemory],
    db_path: str,
) -> int:
    """Load SQLite memories into BM25 stores.

    Clears existing in-memory data before loading.
    Returns total entries loaded.
    """
    conn = sqlite3.connect(db_path)
    total = 0

    for name, mem in memories.items():
        mem.clear()
        rows = conn.execute(
            "SELECT situation, recommendation FROM memories WHERE agent_name = ? ORDER BY created_at",
            (name,),
        ).fetchall()
        if rows:
            mem.add_situations([(r[0], r[1]) for r in rows])
            total += len(rows)

    conn.close()
    return total
```

- [ ] **Step 2: Commit**

```bash
git add openclaw/memory_persistence.py
git commit -m "feat: add BM25 ↔ SQLite memory persistence"
```

---

### Task 5.3: Wire memory into RunEngine

**Files:**
- Modify: `openclaw/engine.py`

- [ ] At the start of `run()`, after config load and halt check:
  - Create 5 BM25 memory instances: `bull_memory`, `bear_memory`, `trader_memory`, `invest_judge_memory`, `portfolio_manager_memory`
  - Call `hydrate_memories({"bull_memory": bull_memory, ...}, db_path)` to load from SQLite
  - Pass relevant memory to each subagent dispatch (bull-researcher gets bull_memory, bear gets bear_memory, etc.)
  - Match memory to agent using the `memory` field from each agent's .md frontmatter

- [ ] At the end of `run()`, after signal extraction:
  - Call `persist_memories(all_memories_dict, db_path, run_id)` to save any new BM25 entries
  - Write run result to `runs` table in SQLite
  - Write each report to `reports` table
  - Write debate histories to `debates` table

- [ ] In `reflect()`, after fetching actual price and running reflection subagent:
  - Call `persist_memories()` for any new reflection memories
  - Write outcome to `outcomes` table (ticker, date, signal, actual_close, correct, reflection text)
  - Append human-readable summary to `memory/YYYY-MM-DD.md`:
    ```
    ## Trading: {ticker} analysis ({date})
    Signal: {signal}
    Actual close: ${actual_close} ({change}%)
    Correct: {yes/no}
    Key insight: {one-line from reflection}
    ```

- [ ] Commit

### Task 5.4: Test memory roundtrip

**Files:**
- Create: `tests/test_memory.py`

- [ ] Write `test_persist_and_hydrate_roundtrip`:
  - Create a `FinancialSituationMemory`, add 2 situations
  - Call `persist_memories()` to SQLite
  - Create a NEW empty memory instance
  - Call `hydrate_memories()` from same SQLite
  - Assert: 2 documents loaded, content matches original
  - Assert: `bm25` index is rebuilt (not None)

- [ ] Write `test_bm25_search_after_hydration`:
  - Persist 3 diverse situations (inflation, tech rally, oil surge)
  - Hydrate into fresh memory
  - Query "inflation and rising interest rates"
  - Assert: top result contains "inflation" in matched_situation

- [ ] Write `test_persist_avoids_duplicates`:
  - Persist same situation twice
  - Hydrate and verify only 1 copy exists (not 2)

- [ ] Write `test_outcome_recording`:
  - Create a test database with init_db()
  - Insert an outcome row (ticker, date, signal, actual_close, correct)
  - Read back and verify all fields match

- [ ] Write `test_markdown_summary_written`:
  - After a mock run + reflect, verify `memory/YYYY-MM-DD.md` exists and contains the ticker + signal

- [ ] Run all: `python -m pytest tests/test_memory.py -v` — expect ALL PASS
- [ ] Commit

```python
# tests/test_memory.py
import os
import tempfile
import pytest
from tradingagents.agents.utils.memory import FinancialSituationMemory
from openclaw.memory_persistence import persist_memories, hydrate_memories
from openclaw.database import init_db


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_persist_and_hydrate_roundtrip(db_path):
    """Memories should survive a persist → hydrate cycle."""
    mem = FinancialSituationMemory("bull_memory")
    mem.add_situations([
        ("High inflation with rising rates", "Buy defensive stocks"),
        ("Tech sector rally with strong earnings", "Increase tech allocation"),
    ])

    count = persist_memories({"bull_memory": mem}, db_path, run_id="run-001")
    assert count == 2

    # Create fresh memory and hydrate
    new_mem = FinancialSituationMemory("bull_memory")
    total = hydrate_memories({"bull_memory": new_mem}, db_path)
    assert total == 2
    assert len(new_mem.documents) == 2
    assert new_mem.documents[0] == "High inflation with rising rates"


def test_bm25_search_after_hydration(db_path):
    """BM25 should return relevant results after hydration."""
    mem = FinancialSituationMemory("trader_memory")
    mem.add_situations([
        ("Inflation rising, fed hawkish", "Sell growth stocks, buy value"),
        ("Tech earnings beat expectations", "Buy NVDA, increase tech exposure"),
        ("Oil prices surging, geopolitical tension", "Hedge with commodities"),
    ])
    persist_memories({"trader_memory": mem}, db_path)

    new_mem = FinancialSituationMemory("trader_memory")
    hydrate_memories({"trader_memory": new_mem}, db_path)

    results = new_mem.get_memories("inflation and interest rates rising", n_matches=1)
    assert len(results) == 1
    assert "inflation" in results[0]["matched_situation"].lower()


def test_persist_avoids_duplicates(db_path):
    """Persisting the same memories twice should not create duplicates."""
    mem = FinancialSituationMemory("bear_memory")
    mem.add_situations([("Recession risk", "Sell equities")])

    persist_memories({"bear_memory": mem}, db_path)
    count = persist_memories({"bear_memory": mem}, db_path)  # second persist
    assert count == 0  # no new entries

    new_mem = FinancialSituationMemory("bear_memory")
    hydrate_memories({"bear_memory": new_mem}, db_path)
    assert len(new_mem.documents) == 1  # not 2
```

- [ ] Run tests, expect PASS
- [ ] Commit

---

### GATE 5: Verify before proceeding to Phase 6

```bash
# 1. Memory tests
python -m pytest tests/test_memory.py -v
# Expected: ALL PASSED (roundtrip, BM25 search after hydration, no duplicates, outcome recording, markdown written)

# 2. Database initializes
python -c "
from openclaw.database import init_db, get_db
init_db('test_gate5.db')
import sqlite3
conn = sqlite3.connect('test_gate5.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('tables:', sorted(tables))
conn.close()
import os; os.unlink('test_gate5.db')
"
# Expected: tables: ['debates', 'memories', 'outcomes', 'reports', 'runs']

# 3. Memory persist + hydrate roundtrip
python -c "
from openclaw.memory import FinancialSituationMemory
from openclaw.memory_persistence import persist_memories, hydrate_memories
from openclaw.database import init_db
init_db('test_gate5.db')
mem = FinancialSituationMemory('test')
mem.add_situations([('inflation rising', 'buy bonds')])
persist_memories({'test': mem}, 'test_gate5.db')
mem2 = FinancialSituationMemory('test')
hydrate_memories({'test': mem2}, 'test_gate5.db')
print('docs:', len(mem2.documents), 'content:', mem2.documents[0][:20])
import os; os.unlink('test_gate5.db')
"
# Expected: docs: 1 content: inflation rising
```

---

## Phase 6: Dashboard (4 tasks)

**Why:** The user wants both a terminal dashboard (quick status during market hours) and the existing React WebUI (detailed analysis review). Both read from the same `trading.db`.

**Terminal monitor purpose:** A Bloomberg-terminal-lite view showing: halt status, strategy, watchlist tickers with their signals, current prices, whether the signal was correct, memory stats, last run timestamp, next heartbeat time. This is what you glance at during market hours.

**Terminal analysis viewer purpose:** Deep-dive into a specific run — shows all 4 analyst reports, the full bull/bear debate transcript, risk debate, trader's plan, and portfolio manager's final decision. This is what you read after a run completes to understand WHY a signal was given.

**WebUI migration:** The existing React frontend at `TradingAgents/webui/` is a fully working app with a backend (FastAPI) and frontend (React 19 + Vite). We move it to `dashboard/web/` and update it to use the unified `trading.db` instead of its own database. The WebUI's `runner.py` (which currently wraps TradingAgentsGraph) is replaced by RunEngine.

**Verification hook:** Run `python dashboard/terminal/monitor.py` — should display the Rich panel without crash. Run with a populated `trading.db` to see actual data.

### Task 6.1: Terminal signal board

```python
# dashboard/terminal/monitor.py
"""Rich-based terminal dashboard for trading signal monitoring."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
import json
import sqlite3
import os


def render_signal_board(config_path: str = "trading-config.json",
                         db_path: str = "trading.db") -> Panel:
    """Render the signal board as a Rich Panel."""
    # Load config
    with open(config_path) as f:
        config = json.load(f)

    table = Table(title="Trading Monitor")
    table.add_column("Ticker", style="cyan")
    table.add_column("Signal", style="bold")
    table.add_column("Date", style="dim")
    table.add_column("Status")

    # Load recent runs from DB
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT ticker, signal, trade_date, status FROM runs ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
        conn.close()

        signal_colors = {
            "BUY": "[green]BUY[/green]",
            "OVERWEIGHT": "[green]OVERWEIGHT[/green]",
            "HOLD": "[yellow]HOLD[/yellow]",
            "UNDERWEIGHT": "[red]UNDERWEIGHT[/red]",
            "SELL": "[red]SELL[/red]",
        }

        for row in rows:
            signal_display = signal_colors.get(row["signal"], row["signal"] or "—")
            table.add_row(
                row["ticker"],
                signal_display,
                row["trade_date"],
                row["status"],
            )
    else:
        table.add_row("—", "—", "—", "No runs yet")

    # Build status line
    halt_status = "[red]HALTED[/red]" if config.get("halt") else "[green]ACTIVE[/green]"
    strategy = config.get("strategy", "default")
    watchlist = ", ".join(config.get("watchlist", [])) or "empty"

    header = f"Status: {halt_status}  |  Strategy: {strategy}  |  Watchlist: {watchlist}"

    return Panel(table, title=header, border_style="blue")


def show_monitor(config_path: str = "trading-config.json", db_path: str = "trading.db"):
    """Display the trading monitor."""
    console = Console()
    panel = render_signal_board(config_path, db_path)
    console.print(panel)


if __name__ == "__main__":
    show_monitor()
```

- [ ] Create `dashboard/__init__.py`, `dashboard/terminal/__init__.py`
- [ ] Create `dashboard/terminal/monitor.py` with above code
- [ ] Commit

### Task 6.2: Terminal analysis viewer

**Files:**
- Create: `dashboard/terminal/analysis_viewer.py`

- [ ] Accept a `run_id` parameter
- [ ] Read from `trading.db`: query `runs` table for the run, `reports` table for all sections, `debates` table for all debates
- [ ] Display with Rich panels:
  - Header: ticker, date, strategy, signal, duration
  - Panel 1: Market Report (full text)
  - Panel 2: Sentiment Report (if present)
  - Panel 3: News Report
  - Panel 4: Fundamentals Report (if present)
  - Panel 5: Bull/Bear Debate (alternating speakers with labeled turns)
  - Panel 6: Research Manager's Decision
  - Panel 7: Trader's Plan
  - Panel 8: Risk Debate (aggressive/conservative/neutral turns)
  - Panel 9: Portfolio Manager's Final Decision (highlighted)
- [ ] Support `--run-id` CLI arg or interactive selection of recent runs
- [ ] Commit

### Task 6.3: Migrate React WebUI

**Files:**
- Move: `TradingAgents/webui/` → `dashboard/web/`

**Step-by-step migration:**
- [ ] Copy directory: `cp -r TradingAgents/webui/ dashboard/web/`
- [ ] Update `dashboard/web/backend/database.py`:
  - Change `DB_PATH` to use `trading-config.json` paths.database value
  - Or accept `db_path` as parameter instead of hardcoding
- [ ] Update `dashboard/web/backend/runner.py`:
  - Remove `TradingAgentsGraph` import and usage
  - Replace with `RunEngine` import from `openclaw.engine`
  - `_execute_run()` calls `engine.run(ticker, date, dispatch_fn=..., callbacks=[WebSocketCallback(...)])`
  - The `dispatch_fn` for WebUI: calls the configured LLM API directly (since WebUI runs headless, not inside Claude Code)
- [ ] Update `dashboard/web/backend/app.py`:
  - Change CORS origins if needed
  - Update static file paths
- [ ] Update `dashboard/web/backend/routes/config.py`:
  - Replace `settings` table reads with `trading-config.json` reads via `openclaw.config.load_config()`
  - `PUT /api/keys` — keep but add allowlist (restrict to known API key names)
  - `PUT /api/settings` — write to `trading-config.json` instead of SQLite settings table
- [ ] Update `dashboard/web/backend/routes/runs.py`:
  - `POST /api/runs` — use `RunEngine.run()` instead of direct `TradingAgentsGraph`
- [ ] Frontend: no changes needed (it talks to the same REST API, just the backend changed)
- [ ] Delete standalone `run_webui.py` from root (entry point moves to `dashboard/web/`)
- [ ] Create `dashboard/web/run.py` as new entry point:
  ```python
  import uvicorn
  from dashboard.web.backend.app import app
  uvicorn.run(app, host="0.0.0.0", port=8000)
  ```
- [ ] Commit

### Task 6.4: Test dashboard

**Files:**
- Create: `tests/test_dashboard.py`

- [ ] Write `test_monitor_renders`:
  - Create a temp `trading-config.json` and empty `trading.db`
  - Call `render_signal_board(config_path, db_path)`
  - Assert: returns a Rich `Panel` object without crash
  - Assert: panel contains "Status:" text

- [ ] Write `test_monitor_with_data`:
  - Create `trading.db` with `init_db()`, insert a test run row
  - Call `render_signal_board()`
  - Assert: panel contains the test ticker name

- [ ] Write `test_viewer_shows_run`:
  - Create `trading.db`, insert a run + reports + debate
  - Call analysis viewer function with the run_id
  - Assert: output contains all 4 report section names

- [ ] Write `test_viewer_missing_run`:
  - Call viewer with nonexistent run_id
  - Assert: graceful error message, no crash

- [ ] Run: `python -m pytest tests/test_dashboard.py -v` — expect ALL PASS
- [ ] Commit

---

### GATE 6: Verify before proceeding to Phase 7

```bash
# 1. Dashboard tests
python -m pytest tests/test_dashboard.py -v
# Expected: ALL PASSED

# 2. Terminal monitor renders
python -c "from dashboard.terminal.monitor import render_signal_board; print(type(render_signal_board()))"
# Expected: <class 'rich.panel.Panel'>

# 3. WebUI backend starts (if migrated)
# Start: python dashboard/web/run.py &
# Test: curl -s http://localhost:8000/api/config | python -m json.tool
# Expected: JSON response with config data
# Kill: kill %1
```

---

## Phase 7: OpenClaw Integration (5 tasks)

**Why:** OpenClaw's 8 framework files define the agent's identity, behavior, and capabilities. After the merge, these files need to know about the trading module — what it does, how to trigger it, what rules to follow.

**What changes in each file:**
- **TOOLS.md** — adds a "Trading Module" section pointing to `trading-config.json`, listing available commands, and describing the pipeline. This is the agent's cheat sheet for trading capabilities.
- **HEARTBEAT.md** — adds the trading day-cycle (pre-session analysis, during-session monitoring, post-session reflection). This turns heartbeats from empty → active trading monitors.
- **AGENTS.md** — adds the trading agent role definition: what it does (analysis), what it doesn't do (execution), its authority scope, and how subagent dispatch works.
- **SOUL.md** — adds trading principles: probabilistic analysis, learning from outcomes, HOLD when uncertain, risk non-negotiable. These are behavioral constraints the agent follows.
- **trading-integrator.md** — complete rewrite. Currently describes a fictional broker-connected system. Must be rewritten to describe the real subagent-based analysis pipeline, RunEngine API, and `trading-config.json`.

**Critical: AGENTS.md must explicitly state "analysis only — no order execution"** — this prevents the agent from hallucinating trading capabilities it doesn't have.

**Critical: trading-integrator.md has hardcoded `/home/hoang/.openclaw/workspace/` paths** — replace ALL of them with relative paths.

**Verification hook:** Read each updated file and verify: (1) trading section exists, (2) no contradictions with other files, (3) no hardcoded absolute paths, (4) accurate description of the actual system.

### Task 7.1: Update TOOLS.md

- [ ] Add this section to `workspace/TOOLS.md`:

```markdown
## Trading Module

Config: `trading-config.json`
Database: `trading.db`
Agent definitions: `agents/trading/*.md`
Daily memory: `memory/YYYY-MM-DD.md`

### How It Works
OpenClaw dispatches 12 trading subagents in a 4-tier pipeline:
1. Analysts (market, social, news, fundamentals) → produce reports
2. Bull/Bear debate → argue for/against the trade
3. Research Manager + Trader + Risk debate → validate and size the trade
4. Portfolio Manager → final BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL

### Strategies
- **default**: Stock analysis with standard indicators (4 analysts)
- **jadecap**: ICT futures analysis with 23 ICT indicators (market + news only)

### Config Quick Reference
- Change strategy: edit `trading-config.json` → `"strategy": "jadecap"`
- Add to watchlist: edit `trading-config.json` → `"watchlist": ["NVDA", "AAPL"]`
- Halt analysis: set `"halt": true` in config
- Per-agent model: set `"llm.per_agent.market-analyst": "gpt-4o"` in config
```

- [ ] Commit

### Task 7.2: Update HEARTBEAT.md

- [ ] Replace empty template with:

```markdown
## Trading Day-Cycle

### Pre-Session (before market open, ~8:00 AM ET)
- [ ] Check halt flag in trading-config.json
- [ ] Run full analysis for each ticker in watchlist
- [ ] Record signals in memory/YYYY-MM-DD.md

### During Session (market hours, every ~30 min)
- [ ] Fetch current prices for analyzed tickers (yfinance, no LLM)
- [ ] Compare to morning predictions
- [ ] Append price updates to memory/YYYY-MM-DD.md
- [ ] Check data provider health

### Post-Session (after market close, ~4:30 PM ET)
- [ ] Fetch actual closing prices for each analyzed ticker
- [ ] Compare predictions vs reality (signal correct?)
- [ ] Run enhanced reflection with outcome data
- [ ] Persist enriched memories to trading.db
- [ ] Curate key lessons into MEMORY.md
```

- [ ] Commit

### Task 7.3: Update AGENTS.md

- [ ] Add section:

```markdown
## Trading Agent

Role: Multi-agent market analysis producing BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL signals through a 4-tier pipeline (analysts → bull/bear debate → risk assessment → final decision).

**This is analysis only — no order execution, no positions, no broker connection.**

Authority: Can run analysis autonomously during market hours (if heartbeat enabled). Cannot spend money. Cannot place orders. Cannot connect to exchanges.

How it works: The main OpenClaw agent dispatches 12 specialized subagents defined in `agents/trading/*.md`. Each subagent receives context from prior agents and produces a specific output. The pipeline preserves the original TradingAgents logic.

Config: `trading-config.json`
Agent definitions: `agents/trading/`
```

- [ ] Commit

### Task 7.4: Update SOUL.md

- [ ] Add section:

```markdown
## Trading Principles

- Analysis is probabilistic — no signal is certain.
- Learn from every outcome, right or wrong.
- When uncertain, HOLD is the correct signal.
- Risk parameters in trading-config.json are non-negotiable.
- Transparency: always explain reasoning, never hide uncertainty.
- Past mistakes are lessons, not failures — they improve future analysis.
```

- [ ] Commit

### Task 7.5: Rewrite trading-integrator.md

**Files:**
- Rewrite: `.claude/agents/trading-integrator.md`

**What to REMOVE (fictional — does not exist in the system):**
- [ ] All references to "order placement", "order cancellation", "position queries" — TradingAgents is analysis-only
- [ ] All references to "exchange APIs", "balance verification", "market hours pre-flight" — no broker connection
- [ ] The entire "Kill Switch Implementation" section (kill_all_orders, flatten_positions, halt_trading, emergency_shutdown) — there are no orders to kill
- [ ] References to "position management", "P&L tracking", "open positions monitoring" — no positions exist
- [ ] The "Graceful Degradation" and "Post-Kill Protocol" sections
- [ ] All hardcoded paths: `/home/hoang/.openclaw/workspace/AGENTS.md` etc. — replace with relative paths

**What to ADD (actual system):**
- [ ] **System description:** "TradingAgents is an analysis-only pipeline that produces BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL signals. It does NOT execute orders, manage positions, or connect to exchanges."
- [ ] **Architecture:** 12 subagent .md files in `agents/trading/`, dispatched by RunEngine in 4-tier pipeline
- [ ] **RunEngine API:** `engine.run(ticker, date, dispatch_fn)`, `engine.reflect(ticker, date)`, `engine.halt()`, `engine.resume()`, `engine.status`
- [ ] **Config:** `trading-config.json` — describe the schema sections (strategy, llm, data_vendors, analysis, risk, jadecap, halt, schedule, paths)
- [ ] **Strategies:** default (stocks, 4 analysts) and jadecap (ICT futures, 2 analysts, 23 indicators)
- [ ] **Memory:** BM25 in `openclaw/memory.py`, persisted to `trading.db`, summaries in `memory/YYYY-MM-DD.md`
- [ ] **Data tools:** `openclaw/dataflows/` (yfinance, databento, alpha vantage) + `openclaw/tools/` (stock, indicators, fundamentals, news, ICT)
- [ ] **Dashboard:** terminal monitor at `dashboard/terminal/monitor.py`, web UI at `dashboard/web/`
- [ ] **Halt switch:** simple boolean `halt: true/false` in trading-config.json — blocks analysis runs, not orders
- [ ] **Heartbeat:** day-cycle defined in HEARTBEAT.md (pre-session analysis, during-session monitoring, post-session reflection)
- [ ] **File paths:** all relative to workspace root, no hardcoded absolute paths

**Update the agent metadata:**
- [ ] Keep: `model: opus`, `color: orange`, `memory: project`
- [ ] Update `description` to match new system (analysis pipeline, not execution)
- [ ] Update all example triggers to match real capabilities

- [ ] Commit

---

### GATE 7: Verify before proceeding to Phase 8

```bash
# 1. TOOLS.md has trading section
grep "trading-config.json" workspace/TOOLS.md
# Expected: found

# 2. HEARTBEAT.md has day-cycle
grep "Pre-Session" workspace/HEARTBEAT.md
# Expected: found

# 3. AGENTS.md has trading role
grep "analysis only" workspace/AGENTS.md
# Expected: found

# 4. SOUL.md has trading principles
grep "probabilistic" workspace/SOUL.md
# Expected: found

# 5. trading-integrator.md rewritten (no fictional concepts)
grep -c "kill_all_orders\|flatten_positions\|exchange API" .claude/agents/trading-integrator.md
# Expected: 0 (none found — fictional concepts removed)

grep "RunEngine" .claude/agents/trading-integrator.md
# Expected: found (real API referenced)

grep "/home/hoang" .claude/agents/trading-integrator.md
# Expected: 0 matches (no hardcoded paths)
```

**Manual review:** Read each updated framework file. Verify no contradictions between them. Verify trading-integrator.md describes the ACTUAL system.

---

## Phase 8: Cleanup (7 tasks)

**Why:** Everything replaced by OpenClaw must be deleted. Leaving dead code creates confusion — someone might try to import `TradingAgentsGraph` and get stale behavior. Clean deletion also removes ~45 files and the ENTIRE LangChain/LangGraph dependency tree (zero langchain in final codebase).

**Order matters:** Delete code FIRST, then clean dependencies. If you clean pyproject.toml first, existing imports will break before their files are deleted, causing confusing errors.

**Safety check before deleting:** Verify no file in `openclaw/` or `agents/trading/` imports from any of the deleted modules:
```bash
grep -r "from tradingagents.graph" openclaw/ agents/
grep -r "from tradingagents.llm_clients" openclaw/ agents/
grep -r "langchain" openclaw/ agents/
```
All should return nothing.

**What to keep in `tradingagents/`:** ONLY these directories/files:
- `dataflows/` (all 15 files — yfinance, databento, alpha vantage, indicators, ICT, interface, config, utils)
- `agents/utils/memory.py` (BM25)
- `agents/utils/core_stock_tools.py` (plain functions after Task 1.4)
- `agents/utils/technical_indicators_tools.py`
- `agents/utils/fundamental_data_tools.py`
- `agents/utils/news_data_tools.py`
- `agents/utils/ict_tools.py`
- `agents/utils/agent_states.py` (TypedDicts — may still be useful for typing)
- `agents/utils/agent_utils.py` (helper functions + tool re-exports)
- `__init__.py` (cleaned up)

**Everything else in tradingagents/ gets deleted.**

**Verification hook:** After cleanup:
```bash
python -c "from tradingagents.dataflows.interface import route_to_vendor; print('OK')"
python -c "from tradingagents.agents.utils.memory import FinancialSituationMemory; print('OK')"
python -c "from openclaw.engine import RunEngine; print('OK')"
grep -r "langchain" TradingAgents/tradingagents/  # should find NOTHING
```

### Task 8.0: Move kept files into openclaw/ (BEFORE deleting anything)

**This must be the FIRST cleanup task.** Move files before deleting the source directory.

- [ ] Move dataflows: `cp -r TradingAgents/tradingagents/dataflows/ openclaw/dataflows/`
- [ ] Move memory: `cp TradingAgents/tradingagents/agents/utils/memory.py openclaw/memory.py`
- [ ] Move agent_states: `cp TradingAgents/tradingagents/agents/utils/agent_states.py openclaw/agent_states.py`
- [ ] Create tools dir: `mkdir -p openclaw/tools/`
- [ ] Move tool files:
  - `cp TradingAgents/tradingagents/agents/utils/core_stock_tools.py openclaw/tools/`
  - `cp TradingAgents/tradingagents/agents/utils/technical_indicators_tools.py openclaw/tools/`
  - `cp TradingAgents/tradingagents/agents/utils/fundamental_data_tools.py openclaw/tools/`
  - `cp TradingAgents/tradingagents/agents/utils/news_data_tools.py openclaw/tools/`
  - `cp TradingAgents/tradingagents/agents/utils/ict_tools.py openclaw/tools/`
- [ ] Create `openclaw/tools/__init__.py` with re-exports from agent_utils.py (adapted)
- [ ] Create `openclaw/dataflows/__init__.py` if not already present
- [ ] **Update ALL internal imports in moved files:**
  - In `openclaw/dataflows/interface.py`: change `from .config import` → stays same (relative)
  - In `openclaw/tools/core_stock_tools.py`: change `from tradingagents.dataflows.interface import route_to_vendor` → `from openclaw.dataflows.interface import route_to_vendor`
  - Same pattern for ALL tool files — find every `from tradingagents.` import and change to `from openclaw.`
  - In `openclaw/memory.py`: no external imports to change (only uses rank_bm25)
  - In `openclaw/engine.py`: update imports to use `from openclaw.memory import`, `from openclaw.tools import`, `from openclaw.dataflows import`
- [ ] **Verify imports work:** `python -c "from openclaw.dataflows.interface import route_to_vendor; print('OK')"`
- [ ] **Verify tools work:** `python -c "from openclaw.tools.core_stock_tools import get_stock_data; print(type(get_stock_data))"`
- [ ] Move webui: `cp -r TradingAgents/webui/ dashboard/web/`
- [ ] Move reference files to workspace root:
  - `cp TradingAgents/.env.example .env.example`
  - `cp TradingAgents/LICENSE LICENSE`
  - `cp TradingAgents/docs/JADECAP_AGENTS.md docs/`
  - `cp -r TradingAgents/assets/ assets/`
  - `cp TradingAgents/tests/test_ticker_symbol_handling.py tests/`
- [ ] Commit: `git commit -m "move: extract kept files from TradingAgents/ into openclaw/"`

### Task 8.1: Delete TradingAgents/ entirely
- [ ] `rm -rf TradingAgents/` — **the entire directory is now gone**
- [ ] Verify: `ls TradingAgents/` should fail with "No such file or directory"
- [ ] Commit: `git commit -m "delete: remove TradingAgents/ — all code now lives in openclaw/"`

### SKIP old Task 8.1-8.6 — replaced by Task 8.0 (move) + Task 8.1 (delete entire dir)

### Task 8.2 (was 8.8): Clean agents/__init__.py — NO LONGER NEEDED (file was deleted with TradingAgents/)

### Task 8.3 (was 8.10): Clean pyproject.toml
Move pyproject.toml to workspace root and update:
- [ ] `cp TradingAgents/pyproject.toml pyproject.toml` (if not already moved)
- [ ] Edit: change package name to `openclaw`
- [ ] Edit: update package paths to point to `openclaw/` not `tradingagents/`
- [ ] Remove langchain/langgraph deps (see full list in original Task 8.10)
- [ ] Keep: pandas, yfinance, stockstats, rank-bm25, requests, parsel, pytz, aiosqlite, rich, python-dotenv
- [ ] Regenerate lock: `uv lock`

### Task 8.4 (was 8.11): Handle README + CLAUDE.md
- [ ] Update `README.md` to describe OpenClaw + trading module (not standalone TradingAgents)
- [ ] Update `workspace/CLAUDE.md` to reflect new architecture
- [ ] Delete `TradingAgents/CLAUDE.md` (already gone with TradingAgents/ deletion)

### Task 8.5: Verify zero LangChain + all imports clean
- [ ] `grep -r "langchain" openclaw/ --include="*.py"` — must return NOTHING
- [ ] `grep -r "langgraph" openclaw/ --include="*.py"` — must return NOTHING
- [ ] `grep -r "from tradingagents" openclaw/ --include="*.py"` — must return NOTHING (old import paths gone)
- [ ] `python -c "from openclaw.engine import RunEngine; print('OK')"` — must succeed
- [ ] `python -c "from openclaw.dataflows.interface import route_to_vendor; print('OK')"` — must succeed
- [ ] `python -c "from openclaw.tools.core_stock_tools import get_stock_data; print('OK')"` — must succeed
- [ ] `python -c "from openclaw.memory import FinancialSituationMemory; print('OK')"` — must succeed
- [ ] `test ! -d TradingAgents/ && echo 'CLEAN — TradingAgents/ fully deleted'`

### Task 8.6: Commit
```bash
git add -A
git commit -m "cleanup: move kept code to openclaw/, delete TradingAgents/ entirely — zero LangChain"
```

---

### GATE 8: Verify before proceeding to Phase 9

**This is the most critical gate.** Phase 8 deleted `TradingAgents/` entirely. Verify everything still works.

```bash
# 1. TradingAgents/ is GONE
test ! -d TradingAgents/ && echo "CLEAN" || echo "FAIL: TradingAgents/ still exists"
# Expected: CLEAN

# 2. Zero LangChain
grep -r "langchain\|langgraph" openclaw/ --include="*.py" | wc -l
# Expected: 0

# 3. Zero old import paths
grep -r "from tradingagents" openclaw/ --include="*.py" | wc -l
# Expected: 0

# 4. All openclaw imports work
python -c "from openclaw.engine import RunEngine; print('engine OK')"
python -c "from openclaw.config import load_config; print('config OK')"
python -c "from openclaw.dataflows.interface import route_to_vendor; print('dataflows OK')"
python -c "from openclaw.tools.core_stock_tools import get_stock_data; print('tools OK')"
python -c "from openclaw.memory import FinancialSituationMemory; print('memory OK')"
python -c "from openclaw.database import init_db; print('database OK')"
python -c "from openclaw.callbacks import PrintCallback; print('callbacks OK')"
# Expected: all print OK

# 5. Engine still runs with stub
python -c "
from openclaw.engine import RunEngine
e = RunEngine()
r = e.run('NVDA', '2026-03-28')
print('signal:', r.signal)
"
# Expected: signal: HOLD (stub)

# 6. ALL tests pass
python -m pytest tests/ -v
# Expected: ALL PASSED

# 7. Agent files intact
ls agents/trading/*.md | wc -l
# Expected: 12

# 8. pyproject.toml has no langchain
grep "langchain" pyproject.toml
# Expected: NO OUTPUT
```

**If ANY check fails: DO NOT proceed to Phase 9. Fix the issue first.**

---

## Phase 9: Full Review + Test — FINAL (10 tasks)

**Why:** This is the final gate. Nothing ships until every test passes and the code-reviewer agent finds no issues. This phase catches: broken imports from deleted code, stale references, logic errors in the RunEngine, memory persistence bugs, and any regressions from the original pipeline.

**Key principle:** Run with a REAL dispatch_fn (not the stub). The functional test should dispatch actual subagents through OpenClaw's Agent tool and verify the full pipeline produces a real signal with real analyst reports.

**Regression check:** Compare old vs new system output. Before starting Phase 8 (cleanup), run the OLD system on a known ticker/date and save the signal + reports. After cleanup, run the NEW system on the same ticker/date and compare. The signals don't need to be identical (different AI calls = different results), but the STRUCTURE should match: 4 reports present, debate history non-empty, signal is a valid value.

**Code-reviewer dispatch (Task 9.8):** Launch a full code-reviewer agent (superpowers:code-reviewer) against the entire merged codebase. The reviewer should check for: stale imports from deleted modules, unused variables, security issues, broken file references, missing error handling. Fix EVERY issue found — do not skip.

### Task 9.1: Functional test (full pipeline end-to-end)

- [ ] Create a real `dispatch_fn` that dispatches subagents through the AI system (Claude Code's Agent tool, or direct API calls)
- [ ] Run: `engine.run("NVDA", "2026-03-28", dispatch_fn=real_dispatch)`
- [ ] Verify:
  - RunResult returned (not None, not error)
  - `result.signal` is one of: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL
  - `result.market_report` is non-empty (analyst ran)
  - `result.news_report` is non-empty
  - `result.investment_debate["history"]` is non-empty (debate happened)
  - `result.risk_debate["history"]` is non-empty
  - `result.final_decision` is non-empty (portfolio manager responded)
  - `result.duration_seconds` > 0
- [ ] Verify in trading.db:
  - `SELECT * FROM runs WHERE ticker='NVDA'` returns 1 row with status='completed'
  - `SELECT count(*) FROM reports WHERE run_id=...` returns 4 (market, sentiment, news, fundamentals for default strategy)
  - `SELECT count(*) FROM debates WHERE run_id=...` returns 2 (investment debate + risk debate)
- [ ] Verify `memory/YYYY-MM-DD.md` exists and contains "NVDA"

### Task 9.2: Memory persistence test

- [ ] Run analysis for NVDA (creates BM25 memories via reflection)
- [ ] Check: `SELECT count(*) FROM memories` > 0
- [ ] Create a NEW RunEngine instance (simulates restart — fresh BM25 stores)
- [ ] Run analysis for NVDA again
- [ ] Verify: the subagent prompts include "past reflections" / "past lessons" content (proving BM25 was hydrated from SQLite)
- [ ] Verify: memory count increased (new memories added, old ones preserved)

### Task 9.3: Outcome tracking test

- [ ] Run analysis for NVDA with a past date (e.g., "2026-03-25" — so actual close price is available)
- [ ] Run: `engine.reflect("NVDA", "2026-03-25")`
- [ ] Verify in trading.db:
  - `SELECT * FROM outcomes WHERE ticker='NVDA'` returns 1 row
  - `actual_close` is a real number (not null)
  - `actual_change_pct` is calculated
  - `correct` is 0 or 1 (based on signal vs price direction)
  - `reflection` is non-empty text
- [ ] Verify `memory/YYYY-MM-DD.md` contains outcome summary line

### Task 9.4: Config / strategy switching test

- [ ] Edit `trading-config.json`: set `"strategy": "jadecap"`, `"analysis.analysts": ["market", "news"]`
- [ ] Run analysis for NQ
- [ ] Verify: only 2 analysts dispatched (market + news), not 4
- [ ] Verify: market-analyst received the JadeCap prompt (contains "JadeCap ICT Market Analyst" string), not the default prompt
- [ ] Verify: bull/bear researchers received JadeCap prompts (contains "Long Setup Analyst" / "Short Setup Analyst")
- [ ] Reset config to default after test

### Task 9.5: Halt switch test

- [ ] `engine.halt()`
- [ ] Verify: `engine.status["state"]` == "halted"
- [ ] Verify: `engine.run("NVDA", "2026-03-28")` raises `RuntimeError` with "halted" message
- [ ] Verify: `trading-config.json` has `"halt": true` (persisted to file)
- [ ] `engine.resume()`
- [ ] Verify: `engine.status["state"]` == "idle"
- [ ] Verify: `engine.run("NVDA", "2026-03-28")` works (no error)
- [ ] Verify: `trading-config.json` has `"halt": false`

### Task 9.6: Multi-LLM test

- [ ] Edit `trading-config.json`:
  ```json
  "llm": {
    "default": "gpt-4o",
    "deep_think": "claude-opus-4-6",
    "quick_think": "gpt-4o-mini",
    "per_agent": {
      "bull-researcher": "claude-sonnet-4-6",
      "portfolio-manager": "claude-opus-4-6"
    }
  }
  ```
- [ ] Verify `get_model_for_agent(config, "bull-researcher", "quick")` returns `"claude-sonnet-4-6"` (per_agent override)
- [ ] Verify `get_model_for_agent(config, "bear-researcher", "quick")` returns `"gpt-4o-mini"` (tier default, no override)
- [ ] Verify `get_model_for_agent(config, "portfolio-manager", "deep")` returns `"claude-opus-4-6"` (per_agent override)
- [ ] Verify `get_model_for_agent(config, "research-manager", "deep")` returns `"claude-opus-4-6"` (deep_think default)
- [ ] If using real dispatch: verify the dispatch_fn receives the correct model string for each agent

### Task 9.7: Dashboard test

- [ ] Run at least 1 analysis first to populate trading.db
- [ ] Terminal monitor:
  - Run `python dashboard/terminal/monitor.py`
  - Verify: Rich panel renders without crash
  - Verify: shows halt status, strategy, at least 1 run with ticker/signal
- [ ] Terminal viewer:
  - Run `python dashboard/terminal/analysis_viewer.py --run-id <id from above>`
  - Verify: displays market report, debate history, final decision
- [ ] Web dashboard (if webui migration complete):
  - Run `python dashboard/web/run.py`
  - Open `http://localhost:8000`
  - Verify: runs list shows the test run
  - Verify: click into run shows reports and debates

### Task 9.8: Dispatch code-reviewer agent

- [ ] Launch superpowers:code-reviewer agent against the ENTIRE `openclaw/` directory + `agents/trading/` + `dashboard/` + `tests/`
- [ ] The reviewer must check for:
  - **Stale imports**: any `from tradingagents.` import paths (should all be `from openclaw.`)
  - **Broken imports**: any import that fails (deleted modules referenced)
  - **LangChain remnants**: any `langchain` or `langgraph` string in Python files
  - **Security issues**: hardcoded paths, SQL injection, unsanitized inputs
  - **Missing error handling**: uncaught exceptions in engine dispatch, database operations
  - **Type mismatches**: function signatures that don't match their callers
  - **Dead code**: unreachable functions, unused imports
- [ ] Fix EVERY issue found — do not skip any
- [ ] Re-run the reviewer after fixes to confirm clean
- [ ] Commit fixes

### Task 9.9: Regression test

**Purpose:** Verify the merged system produces the same QUALITY of output as the original LangGraph system.

- [ ] **Before Phase 8 (cleanup):** Run the OLD system on a known ticker/date:
  ```python
  # Save this output BEFORE deleting TradingAgents/
  from tradingagents.graph.trading_graph import TradingAgentsGraph
  graph = TradingAgentsGraph(debug=True, config={...})
  old_state, old_signal = graph.propagate("NVDA", "2026-03-25")
  # Save old_signal, old_state to a file for comparison
  ```
- [ ] **After Phase 8:** Run the NEW system on the same ticker/date:
  ```python
  from openclaw.engine import RunEngine
  engine = RunEngine()
  new_result = engine.run("NVDA", "2026-03-25", dispatch_fn=real_dispatch)
  ```
- [ ] Compare:
  - Both produce a valid signal? (BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL)
  - Both produce 4 analyst reports (or 2 for jadecap)?
  - Both produce debate history (non-empty)?
  - Both produce a final decision (non-empty)?
  - Signals don't need to match exactly (different AI calls = different results), but STRUCTURE must match
- [ ] If structure differs: investigate which agent is failing and fix

### Task 9.10: Final commit + tag

- [ ] Run full test suite: `python -m pytest tests/ -v` — ALL PASS
- [ ] Verify zero LangChain: `grep -r "langchain" openclaw/ --include="*.py"` — NOTHING
- [ ] Verify TradingAgents/ gone: `test ! -d TradingAgents/`
- [ ] Verify all 12 agent .md files: `ls agents/trading/*.md | wc -l` = 12
- [ ] Verify config loads: `python -c "from openclaw.config import load_config; c = load_config(); print(c['strategy'])"`
- [ ] Verify engine works: `python -c "from openclaw.engine import RunEngine; e = RunEngine(); print(e.status)"`
- [ ] Final commit:
  ```bash
  git add -A
  git commit -m "feat: OpenClaw + TradingAgents merge complete — full subagent architecture"
  git tag v0.1.0-merge
  ```

---

## Summary

| Phase | Tasks | Creates | Modifies | Deletes |
|-------|-------|---------|----------|---------|
| 1. Bug fixes + tool cleanup | 4 | 2 test files | interface.py, ict_indicators.py, .gitignore, 8 tool files | — |
| 2. Config | 3 | config.py, trading-config.json, test | — | — |
| 3. Agent .md files | 12 | 12 agent definitions | — | — |
| 4. Orchestrator | 7 | engine.py, callbacks.py, test | — | — |
| 5. Memory | 4 | database.py, memory_persistence.py, test | engine.py | — |
| 6. Dashboard | 4 | 3 dashboard modules, test | — | — |
| 7. OpenClaw integration | 5 | — | TOOLS.md, HEARTBEAT.md, AGENTS.md, SOUL.md, trading-integrator.md | — |
| 8. Cleanup | 13 | — | pyproject.toml, __init__.py x2, README, CLAUDE.md | ~50 files (see detail below) |
| 9. Review + Test | 10 | — | fixes from review | — |
| **TOTAL** | **62** | **~25 files** | **~15 files** | **~50 files** |

---

## Complete File Disposition

### KEPT (23 files in tradingagents/)
- `dataflows/` — all 15 files (interface, config, y_finance, yfinance_news, alpha_vantage x5, databento_nq, ict_indicators, stockstats_utils, utils, __init__)
- `agents/utils/` — 8 files (memory.py, core_stock_tools.py, technical_indicators_tools.py, fundamental_data_tools.py, news_data_tools.py, ict_tools.py, agent_states.py, agent_utils.py)

### CREATED (~25 new files)
- `agents/trading/` — 12 .md subagent definitions
- `openclaw/` — 6 Python modules (__init__, config, engine, callbacks, database, memory_persistence)
- `dashboard/terminal/` — 2 modules (monitor.py, analysis_viewer.py) + __init__.py files
- `tests/` — 4 test files (test_config, test_engine, test_memory, test_dashboard)
- `trading-config.json` — 1 file

### DELETED (~50 files)
- `graph/` — 7 files
- `llm_clients/` — 8 files
- `cli/` — 8 files + static/
- Agent `_jadecap.py` variants — 10 files
- Agent default `.py` files — 12 files (after prompts extracted to .md)
- Empty agent subdirs — `analysts/`, `researchers/`, `managers/`, `risk_mgmt/`, `trader/`
- Config files — `default_config.py`, `jadecap_config.py`
- Root scripts — `main.py`, `test.py`, `run_webui.py`
- `requirements.txt`

### MIGRATED (40+ files)
- `webui/` → `dashboard/web/` (React frontend + FastAPI backend, all files)

### KEPT AS-IS (reference)
- `.env.example` — API key reference
- `LICENSE` — legal
- `README.md` — updated with new architecture description
- `CLAUDE.md` — updated to reflect merge
- `assets/` — 12 documentation images
- `docs/JADECAP_AGENTS.md` — ICT methodology reference
- `tests/test_ticker_symbol_handling.py` — existing valid test
- `uv.lock` — regenerated after pyproject.toml cleanup
- `tradingagents/dataflows/config.py` — thread-safe singleton still used by route_to_vendor()

### ZERO LANGCHAIN (verified in Phase 8.5)
After merge: `grep -r "langchain" openclaw/` returns NOTHING.
`TradingAgents/` directory does not exist.
All langchain/langgraph packages removed from dependencies.
@tool decorators removed in Phase 1.4.
Core dependencies: pandas, yfinance, stockstats, rank-bm25, requests, parsel, pytz, aiosqlite, rich, python-dotenv.
Optional (webui): fastapi, uvicorn, websockets, smartmoneyconcepts, databento, fpdf2.

---

## Quick Reference: All 9 Phases

| Phase | Tasks | What happens |
|-------|-------|-------------|
| **1. Bug fixes + tool cleanup** | 4 | Fix vendor fallback, ICT KeyError, .gitignore, remove @tool decorators |
| **2. Config** | 3 | Create trading-config.json, config.py loader, tests |
| **3. Agent .md files** | 12 | Create 12 subagent definitions with verbatim prompts |
| **4. Orchestrator** | 7 | Build RunEngine (dispatch_fn hook), callbacks, debate/risk loops |
| **5. Memory + outcomes** | 4 | SQLite schema, BM25↔SQLite persistence, outcome tracking |
| **6. Dashboard** | 4 | Rich terminal monitor, analysis viewer, migrate React WebUI |
| **7. OpenClaw integration** | 5 | Update TOOLS/HEARTBEAT/AGENTS/SOUL.md, rewrite trading-integrator |
| **8. Cleanup** | 7 | Move kept code → openclaw/, delete TradingAgents/ entirely, clean deps |
| **9. Review + test** | 10 | Full pipeline test, memory test, config test, code-reviewer agent, regression |
| **TOTAL** | **56** | |

## End State

```
/home/hoang/.openclaw/
├── workspace/           ← OpenClaw 8 framework files (SOUL, AGENTS, HEARTBEAT, TOOLS, etc.)
├── agents/trading/      ← 12 subagent .md definitions
├── openclaw/            ← THE Python package
│   ├── engine.py        ← RunEngine (dispatch_fn hook)
│   ├── config.py        ← trading-config.json loader
│   ├── callbacks.py     ← RunCallback protocol
│   ├── database.py      ← SQLite schema
│   ├── memory.py        ← BM25 (moved from tradingagents)
│   ├── memory_persistence.py ← BM25 ↔ SQLite
│   ├── agent_states.py  ← TypedDicts (moved)
│   ├── dataflows/       ← 15 files (moved from tradingagents)
│   └── tools/           ← 6 files (moved, @tool removed)
├── dashboard/
│   ├── terminal/        ← Rich monitor + viewer
│   └── web/             ← Migrated React WebUI
├── tests/               ← 4+ test files
├── trading-config.json  ← single config
├── pyproject.toml       ← package: "openclaw"
├── .env.example, LICENSE, README.md
└── docs/, assets/       ← reference material

TradingAgents/ ← DOES NOT EXIST (fully deleted)
```

**OpenClaw is main. Zero LangChain. Zero duplication. Everything accounted for.**

