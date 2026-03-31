# OpenClaw + TradingAgents Merge — Full Implementation Plan

> **Status note (updated 2026-03-29):** Core merge is implemented and partially runtime-validated. This plan now serves as both implementation history and remaining-work tracker.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Dissolve TradingAgents into OpenClaw as a trading module. Full subagent architecture — each trading agent becomes an AI-agnostic .md file dispatched by OpenClaw's main agent. No LangGraph. No duplicate infrastructure. OpenClaw is main.

**Architecture:** 12 trading agent `.md` files in `agents/trading/`, dispatched by an OpenClaw `RunEngine` orchestrator in the original 4-tier pipeline (analysts → debate → judge/trader/risk → portfolio manager). Data tools (yfinance, databento, ICT indicators) stay as Python. Config in `trading-config.json`. Memory in SQLite + markdown. Dashboard in Rich terminal + React/FastAPI web.

## Current Implementation Status (2026-03-29)

### Completed
- `openclaw/engine.py` is the main orchestration engine.
- Trading agent prompts live in `agents/trading/*.md`.
- Core config lives in `trading-config.json` + `openclaw/config.py`.
- Core persistence lives in `openclaw/database.py`.
- BM25 memory lives in `openclaw/memory.py` + `openclaw/memory_persistence.py`.
- Dashboard web runner now uses the OpenClaw-native `RunEngine` instead of old graph/callback leftovers.
- Dashboard DB compatibility layer now points at the unified core DB path/schema.
- Dashboard memory bridge is aligned with `FinancialSituationMemory` and core agent memory namespaces.
- Web runtime compatibility fixes landed for:
  - automatic dashboard DB/settings initialization
  - unified `runs` table insertion from `POST /api/runs`
- Test suite passes (`57 passed` at last verification).

### Still Remaining / Not Fully Validated
- Full end-to-end WebSocket streaming verification during a live run.
- Full cancel-flow verification from web request → background runner → DB/event state.
- Reflection route verification with real market-data conditions.
- Live price streaming verification with real vendor/API conditions.
- Final doc cleanup so README + design docs exactly match implemented runtime behavior.
- **JadeCap runtime strategy path is not end-to-end healthy yet.** A live `NQ` JadeCap run exposed a deeper prompt/runtime integration gap: the JadeCap markdown prompts expect a rich computed context (e.g. `instrument['description']`, `BULL_SETUP[...]`, `RISK[...]`, `AMD[...]`, `kz_str`, `checklist_str`, `hard_rules_str`, `live_price_str`, and expression-like placeholders such as `active_firm.upper()` / `int(t1_pct * 100)`) that the current `RunEngine` does not fully construct.

### New Critical Remediation Track — JadeCap Strategy Fix

This is now a top remaining implementation task, not a hypothetical improvement.

#### Symptoms observed
- Live JadeCap run failed in Tier 1 before analyst completion.
- Crash site: `openclaw/engine.py` → `_build_analyst_prompt()` → `_substitute_placeholders()`.
- Error: `TypeError: string indices must be integers, not 'str'`.
- Additional operational fragility observed around Sunday/overnight `NQ=F` data fetch behavior.

#### Root causes
1. JadeCap prompts were migrated with rich template expressions intact.
2. Current prompt rendering supports mostly flat placeholder substitution.
3. Current engine context building does not provide a dedicated JadeCap runtime context layer.
4. Some JadeCap fields exist in `openclaw/jadecap_config.py` but are not normalized into prompt-ready values.
5. Some risk/config fields referenced by prompts do not cleanly map to the merged JSON config schema.

#### Required fixes
1. Add a dedicated JadeCap context builder in `openclaw/engine.py`.
2. Compute prompt-ready values for:
   - `active`, `active_firm`, `instrument`, `point_value`, `max_loss`, `min_rr`
   - `live_price_str`, `kz_str`, `checklist_str`, `hard_rules_str`
   - `bull_req`, `bear_req`, `holiday_list`, `instrument_context`
   - `TRADE_OUTPUT_FORMAT`, `BULL_SETUP`, `BEAR_SETUP`, `AMD`, `RISK`
   - `atr_mult`, `t1_pct`, `half_risk_losses`, `max_streak`
3. Decide one of two strategies and apply consistently:
   - **Preferred:** simplify JadeCap prompt placeholders so they use plain variable names only
   - or support a safer structured templating layer for expression-style placeholders
4. Normalize missing schema fields between `trading-config.json` and `openclaw/jadecap_config.py`.
5. Re-run live JadeCap validation after the context layer is implemented.

#### Strategy-specific acceptance criteria
A JadeCap run should not be considered fixed until all of the following pass:
- `RunEngine.run('NQ', today)` with `strategy='jadecap'` completes Tier 1 without prompt-render failure.
- Tier 2, 3, and 4 complete with JadeCap prompts rendered successfully.
- Live/fallback price context is included without crashing the run.
- At least one end-to-end `NQ` JadeCap test run completes and writes unified DB artifacts.
- Prompt rendering no longer depends on fragile expression-like placeholders.

### New Important Improvement Track — Unified Provider Configuration + WebUI Editing

The desired end-state is that provider selection is controlled from one canonical OpenClaw config model and exposed consistently in the WebUI and CLI.

#### Goal
Users should be able to configure provider choice per category, for example:
- core price/OHLCV provider
- technical indicator provider
- fundamentals provider
- news provider
- live price provider / live stream preference
- optional macro-news research provider

#### Source of truth rule
- `trading-config.json` should be the canonical source of truth.
- OpenClaw config code should load/save it.
- WebUI should edit the same underlying config.
- CLI should edit the same underlying config.
- The dashboard `settings` table should only remain for temporary UI/session compatibility state, not as a competing long-term config source.

#### Current gap
Right now provider selection is only partially unified:
- `trading-config.json` contains `data_vendors` and `tool_vendors`
- some runtime paths read those values
- some web/runtime paths still use separate fallback logic or compatibility settings reads
- live price source selection is not fully governed by the same config path as the rest of the analysis stack

#### Required fixes
1. Extend config schema so provider categories are explicit and complete.
2. Add/update WebUI controls to edit provider settings directly.
3. Make the WebUI save path write back to core config, not only compatibility settings.
4. Audit all runtime paths to ensure provider selection resolves from one config model.
5. Keep route-level fallback logic only as graceful degradation, not as competing provider policy.

### New Important Improvement Track — Brave-backed Multi-Headline News Research

The news agent should be able to use richer search-backed research instead of relying only on narrow feed sources.

#### Goal
Support Brave Search API as a configurable news research provider so the system can gather multiple current headlines/results and synthesize them into the News Analyst prompt context.

#### Desired behavior
For macro/news analysis, the system should be able to:
- query multiple relevant searches (Fed, CPI, NFP, GDP, major tech earnings, geopolitics, yields, DXY, etc.)
- gather multiple headline/snippet results
- deduplicate overlapping stories
- organize results by macro theme
- feed the consolidated research into the News Analyst report

#### Suggested provider model
Examples of future config options:
- `news_data: yfinance`
- `news_data: brave`
- `news_data: multi`
- possibly later a split such as `macro_news_data: brave` + `ticker_news_data: yfinance`

#### Acceptance criteria
- WebUI exposes a news provider selector.
- `trading-config.json` can persist Brave as the configured news provider.
- News research path can collect multiple Brave results per run.
- News results are deduplicated and summarized before prompt injection.
- JadeCap/news path can use Brave-backed multi-headline context without breaking current yfinance fallback behavior.

### Important Reality Check
This is now a mostly-complete OpenClaw-first merge, but not every dashboard/runtime edge path has been fully validated yet. The system is no longer in the design-only stage.

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

## Appendix: Actual Implementation Details

> Auto-generated 2026-03-28 from reading every file listed below.

---

### engine.py
**Path:** `openclaw/engine.py`
**Purpose:** Orchestrates the 4-tier trading analysis pipeline via subagent dispatch.

#### Dataclass: RunResult
Fields: `run_id: str`, `ticker: str`, `date: str`, `signal: str`, `market_report: str`, `sentiment_report: str`, `news_report: str`, `fundamentals_report: str`, `investment_debate: dict`, `risk_debate: dict`, `trader_plan: str`, `final_decision: str`, `duration_seconds: float`. All default to empty/zero.

#### Class: RunEngine

##### Methods:
- `__init__(self, config_path: str = "trading-config.json") -> None` -- Loads config via `load_config()`, initializes 5 BM25 `FinancialSituationMemory` instances (bull, bear, trader, invest_judge, portfolio_manager), hydrates memories from SQLite if DB exists.
- `run(self, ticker: str, date: str, dispatch_fn: Optional[Callable] = None, dispatch_parallel_fn: Optional[Callable] = None, callbacks: Optional[list] = None) -> RunResult` -- Main entry point. Bridges config to dataflow singleton via `set_dataflow_config()`. Checks halt flag. Creates run UUID, inserts `runs` row. Executes 4 tiers sequentially with try/except per tier (partial state saved on failure). Extracts signal from PM response. Persists memories. Returns `RunResult`.
- `_run_tier1_analysts(self, agents_dir, strategy, ticker, date, dispatch, dispatch_parallel_fn, callbacks) -> dict` -- Runs selected analysts (market/social/news/fundamentals). Uses `dispatch_parallel_fn` if provided and >1 task, otherwise sequential. Parses frontmatter for tier/model. Returns dict of `{report_field: response}`.
- `_run_debate(self, agents_dir, strategy, ticker, date, reports, dispatch, callbacks) -> dict` -- Runs bull/bear debate for `max_debate_rounds`. Each round: bull argues, then bear counters. Returns debate dict with `history`, `bull_history`, `bear_history`, `count`.
- `_run_judge_trader_risk(self, agents_dir, strategy, ticker, date, reports, debate, dispatch, callbacks) -> tuple[str, str, dict]` -- Runs research-manager (investment plan), trader (trade plan), then risk debate (aggressive/conservative/neutral for `max_risk_discuss_rounds`). Returns `(investment_plan, trader_plan, risk_debate)`.
- `_run_portfolio_manager(self, agents_dir, strategy, ticker, date, reports, debate, investment_plan, trader_plan, risk_debate, dispatch, callbacks) -> str` -- Runs portfolio-manager agent with full context. Returns final decision string.
- `_extract_signal(self, final_decision: str) -> str` -- Parses final decision text for BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL. Checks formatted patterns first, then falls back to last occurrence. Returns signal string.
- `_build_analyst_prompt(self, agents_dir, agent_name, strategy, ticker, date) -> str` -- Reads agent .md, extracts strategy prompt, parses frontmatter for tool list, pre-fetches tool data via registry, substitutes placeholders, builds JadeCap context if needed. Returns complete prompt string.
- `_build_researcher_prompt(self, agents_dir, agent_name, strategy, ticker, date, reports_context, debate, side, reports=None) -> str` -- Builds prompt for bull/bear researchers with debate history, opponent history, memory context, and report data. Returns prompt string.
- `_build_prompt_with_context(self, agents_dir, agent_name, strategy, **context) -> str` -- Generic prompt builder for manager/trader/risk/PM agents. Reads strategy prompt, merges JadeCap context if needed, substitutes placeholders. Returns prompt string.
- `_substitute_placeholders(template: str, context: dict) -> str` (static) -- Regex-based placeholder resolver. Handles `.upper()`, `int()`, dict access like `instrument['description']`, and nested dict access like `BULL_SETUP['target']`. Returns resolved string.
- `_build_jadecap_context(self, ticker: str, date: str) -> dict` -- Imports from `jadecap_config.py` (JADECAP_CONFIG, AMD, RISK, HARD_RULES, BULL_SETUP, BEAR_SETUP, CHECKLIST, TRADE_OUTPUT_FORMAT, HOLIDAY_RULES, KILL_ZONES). Builds ~40 context variables including live price, kill zones, checklist, hard rules, requirements, instruments. Returns context dict.
- `_safe_live_price(self, symbol: str) -> str` -- Calls `fetch_live_price()` wrapped in try/except. Returns price string or "unavailable".
- `_format_kill_zones(kill_zones: dict) -> str` (static) -- Formats kill zone dict into bullet list. Returns string.
- `_format_checklist(items: list) -> str` (static) -- Formats checklist items with required/optional tags. Returns string.
- `_format_hard_rules(rules: list) -> str` (static) -- Formats hard rules as bullet list. Returns string.
- `_format_requirements(reqs: list) -> str` (static) -- Formats requirement list as bullets. Returns string.
- `_read_strategy_prompt(self, md_path: str, strategy: str) -> str` -- Reads agent .md file, extracts content under `## JadeCap Strategy Prompt` or `## Default Strategy Prompt` heading. Falls back to content after frontmatter. Returns prompt text.
- `_format_reports(self, reports: dict) -> str` -- Formats report dict into labeled sections. Returns string.
- `_parse_frontmatter(md_path: str) -> dict` (static) -- Parses YAML-like frontmatter between `---` markers. Handles lists `[a, b]`, null, and string values. Returns dict.
- `_prefetch_tool_data(self, tool_names: list, ticker: str, date: str) -> dict` -- Calls `registry.call_many()` for the given tool names. Returns `{tool_name: result_string}`.
- `_get_memory_context(self, memory_name: str, ticker: str, date: str) -> str` -- BM25 retrieves top 3 matching memories for the given ticker/date situation. Returns formatted string or empty.
- `_dispatch_with_timeout(self, dispatch_fn, agent_name: str, prompt: str, model: str) -> str` -- Wraps dispatch in `ThreadPoolExecutor` with configurable timeout (default 300s). Raises `TimeoutError` on expiry. Returns dispatch result string.
- `_persist_reports(self, db_path: str, run_id: str, reports: dict) -> None` -- Inserts report sections into `reports` table.
- `_persist_debate(self, db_path: str, run_id: str, debate_type: str, debate: dict, judge_decision: str = "") -> None` -- Inserts debate record into `debates` table with side histories.
- `_mark_run_failed(self, db_path: str, run_id: str, error_msg: str, start_time) -> None` -- Updates run row to status='failed' with error message and duration.
- `_default_dispatch(self, agent_name: str, prompt: str, model: str) -> str` -- Stub dispatcher that prints and returns a placeholder response.
- `reflect(self, ticker: str, date: str, dispatch_fn=None, callbacks=None) -> dict` -- Post-session reflection. Fetches actual close via yfinance, compares to stored signal, determines correctness (BUY+up=correct, SELL+down=correct), inserts into `outcomes` table. Returns dict with ticker, date, actual_close, signal, correct, actual_change_pct, reflection.
- `halt(self) -> None` -- Sets `config["halt"] = True` and saves config to disk.
- `resume(self) -> None` -- Sets `config["halt"] = False` and saves config to disk.
- `status` (property) -> `dict` -- Returns `{"state": "running"|"idle"|"halted", "strategy": ..., "watchlist": ..., "config_path": ...}`.

---

### config.py
**Path:** `openclaw/config.py`
**Purpose:** Unified config: JSON file + schema defaults. Replaces default_config.py, jadecap_config.py globals, and WebUI settings table.

#### Constants:
- `SCHEMA_DEFAULTS: Dict[str, Any]` -- Full default config tree with keys: strategy, watchlist, llm (default/deep_think/quick_think/per_agent), data_vendors, tool_vendors, analysis, risk, jadecap (instruments/sessions/kill_zones/midday_avoidance), halt, schedule (market_hours), paths.

#### Functions:
- `deep_merge(base: dict, override: dict) -> dict` -- Recursively merges override into base without mutation. Override values win. Returns new dict.
- `load_config(path: str = "trading-config.json") -> Dict[str, Any]` -- Loads JSON config file, deep-merges with `SCHEMA_DEFAULTS`. Returns defaults if file missing.
- `save_config(config: Dict[str, Any], path: str = "trading-config.json") -> None` -- Writes config dict to JSON file with indent=2.
- `get_model_for_agent(config: Dict[str, Any], agent_name: str, tier: str = "quick") -> str` -- Resolves LLM model for agent. Priority: per_agent override > tier default (deep_think/quick_think) > global default. Returns model string.

---

### database.py
**Path:** `openclaw/database.py`
**Purpose:** SQLite database schema for trading run persistence.

#### Schema (5 tables):
- **runs** -- `id TEXT PK`, `ticker TEXT NOT NULL`, `trade_date TEXT NOT NULL`, `strategy TEXT DEFAULT 'default'`, `signal TEXT`, `status TEXT DEFAULT 'running'`, `error_message TEXT`, `duration_seconds REAL`, `created_at TEXT NOT NULL`
- **reports** -- `id INTEGER PK AUTOINCREMENT`, `run_id TEXT FK->runs(id) CASCADE`, `section_name TEXT NOT NULL`, `content TEXT`
- **debates** -- `id INTEGER PK AUTOINCREMENT`, `run_id TEXT FK->runs(id) CASCADE`, `debate_type TEXT NOT NULL`, `full_history TEXT`, `side_a_history TEXT`, `side_b_history TEXT`, `side_c_history TEXT`, `judge_decision TEXT`
- **memories** -- `id INTEGER PK AUTOINCREMENT`, `agent_name TEXT NOT NULL`, `situation TEXT NOT NULL`, `recommendation TEXT NOT NULL`, `run_id TEXT` (no FK), `created_at TEXT NOT NULL`
- **outcomes** -- `id INTEGER PK AUTOINCREMENT`, `run_id TEXT` (no FK), `ticker TEXT NOT NULL`, `trade_date TEXT NOT NULL`, `signal TEXT NOT NULL`, `actual_close REAL`, `actual_change_pct REAL`, `correct INTEGER`, `reflection TEXT`, `created_at TEXT NOT NULL`

#### Functions:
- `init_db(db_path: str) -> None` -- Creates all tables with `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`.
- `safe_get_db(db_path: str) -> ContextManager[sqlite3.Connection]` -- Returns `get_db()` context manager, calling `init_db()` first if DB file does not exist.
- `get_db(db_path: str) -> Generator[sqlite3.Connection, None, None]` -- Context manager yielding a `sqlite3.Connection` with `Row` factory and foreign keys enabled.

---

### memory.py
**Path:** `openclaw/memory.py`
**Purpose:** Financial situation memory using BM25 for lexical similarity matching. No API calls, no token limits, works offline.

#### Class: FinancialSituationMemory

##### Methods:
- `__init__(self, name: str, config: dict = None) -> None` -- Initializes with name identifier. Stores `documents: List[str]`, `recommendations: List[str]`, `bm25: Optional[BM25Okapi]`.
- `_tokenize(self, text: str) -> List[str]` -- Lowercases and splits on non-alphanumeric boundaries. Returns token list.
- `_rebuild_index(self) -> None` -- Rebuilds BM25Okapi index from all stored documents. Sets `bm25 = None` if no documents.
- `add_situations(self, situations_and_advice: List[Tuple[str, str]]) -> None` -- Appends (situation, recommendation) pairs to documents/recommendations lists, then rebuilds BM25 index.
- `get_memories(self, current_situation: str, n_matches: int = 1) -> List[dict]` -- BM25 similarity search. Returns list of dicts with keys `matched_situation`, `recommendation`, `similarity_score` (normalized 0-1). Returns empty list if no documents.
- `clear(self) -> None` -- Clears all documents, recommendations, and BM25 index.

---

### memory_persistence.py
**Path:** `openclaw/memory_persistence.py`
**Purpose:** BM25 <-> SQLite synchronization for FinancialSituationMemory. Persist and reload across sessions.

#### Functions:
- `persist_memories(memories_dict: Dict[str, FinancialSituationMemory], db_path: str, run_id: str) -> int` -- Writes BM25 entries to SQLite `memories` table, deduplicating against existing rows for each agent. Returns count of new rows inserted.
- `hydrate_memories(memories_dict: Dict[str, FinancialSituationMemory], db_path: str) -> int` -- Clears each memory instance, loads from `memories` table ordered by `created_at ASC`, calls `add_situations()`. Returns total memories loaded.

---

### callbacks.py
**Path:** `openclaw/callbacks.py`
**Purpose:** Callback protocol for RunEngine event streaming.

#### Class: RunCallback (Protocol)
- `on_run_start(self, ticker: str, date: str) -> None`
- `on_agent_status(self, agent: str, status: str) -> None`
- `on_report_section(self, name: str, content: str) -> None`
- `on_debate_turn(self, speaker: str, argument: str) -> None`
- `on_signal(self, signal: str) -> None`
- `on_run_complete(self, result: Any) -> None`
- `on_error(self, error: Exception) -> None`

#### Class: PrintCallback
Implements `RunCallback`. Prints all events to stdout with formatting. `on_run_complete` shows signal and duration.

#### Class: CollectorCallback
Implements `RunCallback`. Stores all events in `self.events: list` as tuples for testing. Each event type is a tuple like `("run_start", ticker, date)`.

#### Class: FileMemoryCallback
- `__init__(self, memory_dir: str = "memory") -> None` -- Accumulates lines in memory.
- `on_run_start/on_agent_status/on_report_section/on_debate_turn/on_signal/on_run_complete/on_error` -- Append formatted lines. Complete/error calls `_flush()`.
- `_flush(self) -> None` -- Writes accumulated lines to `memory/<date>.md`. Appends if file exists.

---

### heartbeat.py
**Path:** `openclaw/heartbeat.py`
**Purpose:** Market phase detection and heartbeat state management.

#### Functions:
- `get_market_phase(config: dict) -> str` -- Returns current market phase: `'pre'|'open'|'midday'|'close'|'post'|'closed'`. Uses config timezone (default US/Eastern). Auto-selects stock/futures hours based on strategy. Handles futures overnight session (18:00-17:00).
- `should_run_phase(config: dict, heartbeat_state: dict, phase: str) -> tuple[bool, str]` -- Checks if a heartbeat phase should run. Phases: `pre_session` (once/day), `during_session` (interval-based), `post_session` (once/day). Returns `(should_run, reason)`. Checks halt flag, market phase, and last-run timestamps.
- `load_heartbeat_state(path: str = "heartbeat-state.json") -> dict` -- Loads JSON state file. Returns empty dict if missing.
- `update_heartbeat_state(path: str, phase: str, result: dict = None) -> dict` -- Updates heartbeat state with current ISO timestamp for the phase key (`lastPreSession`/`lastMonitor`/`lastPostSession`). Merges result into `todaySignals`. Writes to disk. Returns updated state.

---

### indicators.py
**Path:** `openclaw/indicators.py`
**Purpose:** Unified indicator interface routing to stockstats or smartmoneyconcepts backends.

#### Constants:
- `STOCKSTATS_INDICATORS: set` -- 13 indicators: close_50_sma, close_200_sma, close_10_ema, macd, macds, macdh, rsi, mfi, boll, boll_ub, boll_lb, atr, vwma.
- `SMC_INDICATORS: set` -- 17 ICT indicators: fvg, order_blocks, session_levels, equal_highs_lows, market_structure, prev_day_levels, midnight_open, killzone_status, fib_ote, math_indicators, ndog, nwog, sfp_detection, displacement_candle, liquidity_sweep, breaker_block, amd_phase.
- `ALL_INDICATORS: set` -- Union of both sets (30 total).

#### Functions:
- `get_indicator(symbol: str, indicator: str, date: str, timeframe: str = "1D", look_back_days: int = 30) -> str` -- Routes to stockstats or SMC backend. Falls back to stockstats for unknown indicators. Returns formatted string.
- `get_indicators_batch(symbol: str, indicators: list, date: str, timeframe: str = "1D", look_back_days: int = 30) -> str` -- Calls `get_indicator()` for each, combines with headers. Returns combined string.
- `list_indicators() -> dict` -- Returns `{"stockstats": [...], "smartmoneyconcepts": [...]}`.
- `_get_stockstats(symbol: str, indicator: str, date: str, look_back_days: int) -> str` -- Delegates to `route_to_vendor("get_indicators", ...)`.
- `_get_smc(symbol: str, indicator: str, date: str, timeframe: str) -> str` -- Fetches OHLCV via `_fetch_ohlcv_df()`, dispatches to appropriate `ict_indicators` function. Returns string result or error.
- `_get_configured_vendor() -> str` -- Reads vendor from dataflow config singleton. Defaults to "yfinance".
- `_fetch_ohlcv_df(symbol: str, timeframe: str, trade_date: str) -> pd.DataFrame | str | None` -- Fetches OHLCV data via databento or yfinance depending on config. Parses CSV, normalizes columns, sets Date index. Returns DataFrame, error string, or None.
- `fetch_live_price(symbol: str) -> str` -- Tries 3 methods in order: WebUI endpoint (localhost:8000), Databento Historical API (15min delayed), yfinance fallback. Returns `"CURRENT PRICE: {symbol} = {price}"` or `"unavailable"`.

---

### tool_registry.py
**Path:** `openclaw/tool_registry.py`
**Purpose:** Dynamic tool registry for the trading pipeline. Tools register with name, callable, and param_builder.

#### Module-level:
- `_build_context(ticker: str, date: str, config: Optional[dict] = None) -> dict` -- Builds standard context with `ticker`, `date`, `start_7d`, `start_30d`, `start_90d`, `config`.
- `registry = ToolRegistry()` -- Module-level singleton.

#### Class: ToolRegistry

##### Methods:
- `__init__(self) -> None` -- Initializes `_tools: Dict[str, dict]`.
- `register(self, name: str, fn: Callable, param_builder: Callable[[dict], dict], description: str = "", category: str = "general") -> None` -- Registers a tool with name, callable, param_builder, description, category.
- `call(self, name: str, ticker: str, date: str, config: Optional[dict] = None) -> str` -- Calls a registered tool. Builds context, runs param_builder, invokes fn with kwargs. Raises `KeyError` if not registered.
- `call_many(self, names: List[str], ticker: str, date: str, config: Optional[dict] = None) -> Dict[str, str]` -- Calls multiple tools, returns results by name. Failed tools logged and returned as error strings.
- `list_tools(self) -> List[str]` -- Returns all registered tool names.
- `list_by_category(self, category: str) -> List[str]` -- Returns tool names filtered by category.
- `get_info(self, name: str) -> Optional[dict]` -- Returns `{"name", "description", "category"}` or None.
- `describe_all(self) -> str` -- Returns formatted string describing all tools with category.
- `__contains__(self, name: str) -> bool` -- Checks if tool is registered.
- `__len__(self) -> int` -- Returns count of registered tools.

---

### tools/__init__.py
**Path:** `openclaw/tools/__init__.py`
**Purpose:** Auto-registers all trading data tools with the global ToolRegistry on import. Plain Python functions, no LangChain.

#### Imports:
- `build_instrument_context`, `create_msg_delete` from `agent_utils`
- `get_stock_data` from `core_stock_tools`
- `get_indicators` from `technical_indicators_tools`
- `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement` from `fundamental_data_tools`
- `get_news`, `get_global_news`, `get_insider_transactions` from `news_data_tools`

#### Registered Tools (14 total):

| Name | fn | param_builder | Category |
|---|---|---|---|
| `get_stock_data` | `get_stock_data` | `{symbol, start_date=start_30d, end_date=date}` | stock |
| `get_indicators` | `get_indicators_batch` | `_pick_indicators(ctx)` -- selects ICT+rsi+atr for jadecap, 8 stock indicators for default | technical |
| `get_ict_levels` | `get_indicators_batch` | 6 ICT indicators: fvg, order_blocks, market_structure, session_levels, prev_day_levels, equal_highs_lows | technical |
| `get_fundamentals` | `get_fundamentals` | `{ticker, curr_date=date}` | fundamental |
| `get_balance_sheet` | `get_balance_sheet` | `{ticker, freq="quarterly", curr_date=date}` | fundamental |
| `get_cashflow` | `get_cashflow` | `{ticker, freq="quarterly", curr_date=date}` | fundamental |
| `get_income_statement` | `get_income_statement` | `{ticker, freq="quarterly", curr_date=date}` | fundamental |
| `get_news` | `get_news` | `{ticker, start_date=start_30d, end_date=date}` | news |
| `get_global_news` | `get_global_news` | `{curr_date=date}` | news |
| `get_insider_transactions` | `get_insider_transactions` | `{ticker}` | news |
| `fetch_live_price` | `fetch_live_price` | `{symbol=ticker}` | realtime |
| `get_live_price` | `fetch_live_price` | `{symbol=ticker}` (alias) | realtime |
| `get_killzone_status_tool` | `_killzone_wrapper` | `{date}` | realtime |
| `get_contract_size` | `_contract_wrapper` | `{stop_points=10}` | realtime |
| `get_midnight_open_tool` | `_midnight_wrapper` | `{symbol=ticker, date}` | realtime |

#### Helper Functions:
- `_pick_indicators(ctx) -> dict` -- Selects ICT or stock indicators based on strategy.
- `_killzone_wrapper(**kwargs) -> str` -- Calls `get_indicator("", "killzone_status", date)`.
- `_contract_wrapper(**kwargs) -> str` -- Calls `get_contract_calc(stop_points)`.
- `_midnight_wrapper(**kwargs) -> str` -- Calls `get_indicator(symbol, "midnight_open", date, timeframe="1m")`.

---

### dataflows/config.py
**Path:** `openclaw/dataflows/config.py`
**Purpose:** Thread-safe config singleton for dataflows. RunEngine calls `set_config()` to bridge trading-config.json values.

#### Constants:
- `_DATAFLOW_DEFAULTS: Dict` -- Minimal defaults: data_vendors (all yfinance), tool_vendors (empty), data_cache_dir.

#### Functions:
- `initialize_config() -> None` -- Initializes global `_config` with defaults if None. Thread-safe.
- `set_config(config: Dict) -> None` -- Deep-merges config into singleton (thread-safe, mutating).
- `_deep_update(base: Dict, override: Dict) -> None` -- Recursive in-place merge of override into base.
- `get_config() -> Dict` -- Returns a copy of current config (thread-safe). Auto-initializes if None.

---

### dataflows/interface.py
**Path:** `openclaw/dataflows/interface.py`
**Purpose:** Routes data method calls to vendor-specific implementations with fallback support.

#### Constants:
- `TOOLS_CATEGORIES: dict` -- Maps category name to description and tool list. Categories: core_stock_apis, technical_indicators, fundamental_data, news_data.
- `VENDOR_LIST: list` -- `["yfinance", "alpha_vantage", "databento"]`.
- `VENDOR_METHODS: dict` -- Maps 9 method names to vendor-specific function dicts: get_stock_data, get_indicators, get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_news, get_global_news, get_insider_transactions. Each has databento/alpha_vantage/yfinance implementations.

#### Functions:
- `get_category_for_method(method: str) -> str` -- Looks up which category contains the method. Raises `ValueError` if not found.
- `get_vendor(category: str, method: str = None) -> str` -- Gets configured vendor. Priority: tool_vendors[method] > data_vendors[category]. Returns vendor string.
- `route_to_vendor(method: str, *args, **kwargs) -> Any` -- Routes to vendor implementation. Builds fallback chain: configured vendors first, then remaining available vendors. Catches all exceptions per vendor, tries next. Raises `RuntimeError` if all vendors fail.

---

### dashboard/terminal/monitor.py
**Path:** `dashboard/terminal/monitor.py`
**Purpose:** Rich-based signal board showing halt status, watchlist signals, memory stats, and last run info.

#### Functions:
- `_signal_style(signal: str) -> str` -- Maps signal (buy/sell/hold/etc.) to Rich style string.
- `_build_halt_status(config: Dict[str, Any]) -> Text` -- Returns "HALTED" (red) or "ACTIVE" (green) Rich Text.
- `_build_strategy_text(config: Dict[str, Any]) -> Text` -- Returns strategy name as cyan Rich Text.
- `_build_watchlist_table(config: Dict[str, Any], db_path: str) -> Table` -- Queries latest run and outcome per watchlist ticker. Returns Rich Table with Ticker/Signal/Date/Status/Correct columns.
- `_build_memory_table(db_path: str) -> Table` -- Queries memory counts per agent. Returns Rich Table.
- `_build_last_run_info(db_path: str) -> Table` -- Queries most recent run. Returns Rich Table with run details.
- `render_signal_board(config_path: str = "trading-config.json", db_path: str = "trading.db") -> Panel` -- Loads config, builds all sub-sections, combines into Rich Panel.
- `show_monitor(config_path: str = "trading-config.json", db_path: str = "trading.db") -> None` -- Prints the signal board to terminal via Rich Console.

---

### dashboard/terminal/analysis_viewer.py
**Path:** `dashboard/terminal/analysis_viewer.py`
**Purpose:** Rich-based detailed analysis viewer for individual trading runs.

#### Functions:
- `_signal_style(signal: str) -> str` -- Maps signal to Rich style string.
- `_build_header_panel(run_row) -> Panel` -- Builds header panel showing ticker, date, strategy, signal, status, duration, error.
- `_build_report_panels(reports) -> list[Panel]` -- Creates one Rich Panel per report section.
- `_build_debate_panels(debates) -> list[Panel]` -- Creates panels showing bull/bear/neutral histories and judge decision with color-coded labels.
- `show_analysis(run_id: str, db_path: str = "trading.db") -> Optional[Panel]` -- Fetches run, reports, and debates from DB. Builds header + report + debate panels. Prints to console. Returns master Panel or None if run not found.

---

### dashboard/web/run.py
**Path:** `dashboard/web/run.py`
**Purpose:** Entry point for the OpenClaw Web Dashboard.

Runs `uvicorn.run(app, host="0.0.0.0", port=8000)` when executed directly.

---

### dashboard/web/backend/app.py
**Path:** `dashboard/web/backend/app.py`
**Purpose:** FastAPI application with lifespan, CORS, routers, and SPA catch-all.

#### Lifespan (`async def lifespan(app)`):
1. Calls `await init_db()` (dashboard DB layer).
2. Marks stuck "running" rows as "failed" with restart message.
3. Hydrates 5 BM25 memory instances from SQLite.
4. Captures event loop for async bridge (`init_event_loop()`).
5. Starts Databento live price stream if API key present.

#### Routes:
- `GET /api/health -> {"status": "ok", "version": "0.2.2"}`
- Includes routers: ws, prices_ws, runs, config, memories, cache, prices.
- SPA catch-all: serves `frontend/dist/index.html` for non-API routes. Assets cached immutably, index.html never cached.

#### CORS:
Allows origins: localhost:5173, localhost:8000, 127.0.0.1:8000, 127.0.0.1:5173.

---

### dashboard/web/backend/database.py
**Path:** `dashboard/web/backend/database.py`
**Purpose:** Async aiosqlite compatibility layer over the unified OpenClaw SQLite schema.

#### Constants:
- `DB_PATH: str` -- Resolved from `trading-config.json` -> `paths.database`. Defaults to `trading.db`.
- `DB_DIR: str` -- Directory of DB_PATH.

#### Additional Table:
- **settings** -- `key TEXT PK`, `value TEXT` (dashboard-specific key-value store).

#### Functions:
- `_resolve_db_path() -> str` -- Reads config and returns absolute DB path.
- `async init_db() -> None` -- Initializes unified DB via `core_init_db()`, then creates `settings` table. Sets WAL mode.
- `async get_db() -> AsyncGenerator[aiosqlite.Connection, None]` -- Async context manager. Self-initializes schema on each access. Returns connection with Row factory and foreign keys.

---

### dashboard/web/backend/routes/config.py
**Path:** `dashboard/web/backend/routes/config.py`
**Purpose:** Config-related API endpoints for the web dashboard.

#### Constants:
- `PROVIDERS: Dict[str, str]` -- 7 providers with API base URLs (openai, anthropic, google, deepseek, xai, openrouter, ollama).
- `DEEP_MODELS: Dict[str, list]` -- Deep-think models per provider (GPT-5.4, Claude Opus 4.6, Gemini 3.1 Pro, Grok 4, DeepSeek R1, etc.).
- `QUICK_MODELS: Dict[str, list]` -- Quick-think models per provider (GPT-5 Mini, Claude Sonnet 4.6, Gemini 3 Flash, etc.).
- `ANALYST_TYPES: list` -- 4 analyst types: market, social, news, fundamentals.
- `DATA_PROVIDER_OPTIONS: dict` -- Vendor options per data category.
- `TOOL_PROVIDER_OPTIONS: dict` -- Tool vendor options (web_search).
- `_TRACKED_API_KEYS: list` -- 8 API key env var names.

#### Functions:
- `async _get_ollama_models() -> List[Dict[str, str]]` -- Fetches models from local Ollama API (port 11434). Returns label/value list.

#### Endpoints:
- `GET /api/config -> dict` -- Returns providers, deep_models, quick_models, analyst_types, data/tool provider options. Dynamically fetches Ollama models.
- `GET /api/trading-config -> dict` -- Returns unified trading config from `load_config()`.
- `PUT /api/trading-config -> dict` -- Deep-merges payload with existing config, saves to disk.
- `GET /api/settings -> Dict[str, Any]` -- Reads all settings from `settings` table, JSON-decodes values.
- `PUT /api/settings -> dict` -- Upserts key/value pairs into `settings` table (JSON-encodes values).
- `PUT /api/keys -> dict` -- Writes API keys to `.env` file (creates/updates). Sets in `os.environ` immediately. Never stored in SQLite.
- `GET /api/keys/status -> Dict[str, bool]` -- Returns which tracked API keys are set in environment.

---

### dashboard/web/backend/routes/runs.py
**Path:** `dashboard/web/backend/routes/runs.py`
**Purpose:** Run management API endpoints.

#### Pydantic Models:
- `RunCreate` -- ticker, trade_date, provider, deep_model, quick_model, effort?, backend_url?, max_debate_rounds=1, max_risk_discuss_rounds=1, data_vendors?, tool_vendors?, selected_analysts=[]
- `ReflectRequest` -- returns_losses: float
- `RunImport` -- run: dict, reports: list, debates: list

#### Helper Functions:
- `async _fetch_run(run_id: str) -> Optional[Dict]` -- Fetches single run row as dict.
- `async _fetch_full_run(run_id: str) -> Optional[Dict]` -- Fetches run + reports + debates. JSON-decodes stored columns.

#### Endpoints:
- `POST /api/runs -> JSONResponse(201)` -- Creates new run. Checks `runner_manager.is_running`. Inserts run row. Reads strategy config from settings. Starts background run via `runner_manager.start_run()`.
- `GET /api/runs -> dict` -- Lists runs with filtering (ticker, signal, status, from_date, to_date), sorting (whitelisted columns), and pagination. Returns `{runs, total, page, per_page}`.
- `GET /api/runs/{run_id} -> dict` -- Returns full run with reports and debates.
- `DELETE /api/runs/{run_id} -> dict` -- Deletes run and all child rows (reports, debates, memories).
- `POST /api/runs/{run_id}/cancel -> dict` -- Sets cancel event on runner, marks run as cancelled.
- `POST /api/runs/reset -> dict` -- Force-resets stuck runner. Marks all running rows as failed.
- `POST /api/runs/{run_id}/reflect -> dict` -- Loads reports/debates, builds situation/recommendation for 5 agent memories, inserts into `memories` table, rehydrates BM25 instances. Returns count of memories created.
- `POST /api/runs/{run_id}/rerun -> JSONResponse` -- Re-runs with same config by constructing `RunCreate` from existing run data.
- `GET /api/runs/{run_id}/tokens -> dict` -- Stub: returns tokens_in, tokens_out, empty breakdown.
- `GET /api/runs/{run_id}/timing -> dict` -- Stub: returns duration_seconds, empty breakdown.
- `GET /api/runs/{run_id}/tools -> dict` -- Stub: returns empty tool_calls list.
- `GET /api/runs/{run_id}/export -> JSONResponse` -- Exports full run as JSON download.
- `POST /api/runs/import -> JSONResponse(201)` -- Imports run from JSON. Checks for duplicate ID. Inserts run, reports, debates.
- `GET /api/runs/{run_id}/compare/{other_id} -> dict` -- Returns both full runs for side-by-side comparison.

---

### dashboard/web/backend/runner.py
**Path:** `dashboard/web/backend/runner.py`
**Purpose:** Background runner for the web dashboard. Runs RunEngine in a background thread, streams events to WebSocket clients.

#### Constants:
- `_FUTURES_MAP: Dict[str, str]` -- Maps short futures names to yfinance tickers (NQ->NQ=F, etc.).
- `DISPLAY_AGENT_NAMES: Dict[str, str]` -- Maps agent IDs to display names (13 agents + reflection).

#### Class: WebUICallbackHandler(RunCallback)
- `__init__(self, runner: RunnerManager) -> None` -- Stores reference to runner.
- `_name(self, agent: str) -> str` -- Resolves display name from `DISPLAY_AGENT_NAMES`.
- `_check_cancel(self) -> None` -- Raises `RuntimeError("Run cancelled")` if cancel event is set.
- `on_run_start/on_agent_status/on_report_section/on_debate_turn/on_signal/on_run_complete/on_error` -- Each adds structured event dict to runner's event buffer with type, data, agent names.

#### Class: RunnerManager
- `__init__(self) -> None` -- Initializes `active_run_id`, `events: list`, `cancel_event: threading.Event`, `ws_connections: set`, `_thread`, `_lock`, `_loop`, `_config_dict`.
- `is_running` (property) -> `bool` -- Returns True if thread is alive. Auto-clears dead thread reference.
- `force_reset(self) -> None` -- Clears thread, run_id, events, cancel_event.
- `add_event(self, event_dict: Dict) -> None` -- Thread-safe append with auto-incrementing id, timestamp, run_id. Triggers WebSocket broadcast.
- `get_events(self, since_id: int = 0) -> List[Dict]` -- Returns events with id > since_id.
- `start_run(self, run_id: str, config_dict: Dict) -> None` -- Validates no active run. Clears state. Emits run_started event. Spawns daemon thread running `_execute_run`.
- `cancel_run(self) -> bool` -- Sets cancel event, emits cancelling event.
- `_build_engine_config(self) -> Dict` -- Creates RunEngine, merges web config (strategy, models, debate rounds, analysts, vendors) into engine config.
- `_execute_run(self) -> None` -- Thread target. Creates RunEngine, builds config, maps futures tickers, calls `engine.run()`. Catches cancellation and general exceptions, emits appropriate events.
- `_schedule_broadcast(self, event_dict: Dict) -> None` -- Broadcasts event to all WebSocket connections via `asyncio.run_coroutine_threadsafe`.

#### Module-level:
- `runner_manager = RunnerManager()` -- Singleton instance.

---

### Agent .md Files (agents/trading/)

#### market-analyst.md
**Frontmatter:** name: market-analyst, model: null, tools: [get_stock_data, get_indicators], tools_jadecap: [get_ict_levels, get_live_price, get_midnight_open_tool, get_killzone_status_tool, get_contract_size], memory: null, memory_jadecap: invest_judge_memory, tier: quick, input: [trade_date, company_of_interest, messages], output: market_report
**Default prompt (first 2 lines):** You are a trading assistant tasked with analyzing financial markets. Your role is to select the most relevant indicators for a given market condition or trading strategy.
**JadeCap prompt (first 2 lines):** You are a JadeCap ICT Market Analyst for {active} Futures. {instrument['description']} | Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1
**Line count:** 261

#### social-analyst.md
**Frontmatter:** name: social-analyst, model: null, tools: [get_news], strategy_variants: [default], memory: null, tier: quick, input: [trade_date, company_of_interest, messages], output: sentiment_report
**Default prompt (first 2 lines):** You are a social media and company specific news researcher/analyst tasked with analyzing social media posts, recent company news, and public sentiment for a specific company over the past week. You will be given a company's name...
**JadeCap prompt:** N/A
**Line count:** 32

#### news-analyst.md
**Frontmatter:** name: news-analyst, model: null, tools: [get_news, get_global_news, get_insider_transactions], tools_jadecap: [get_news, get_global_news], memory: null, memory_jadecap: portfolio_manager_memory, tier: quick, input: [trade_date, company_of_interest, messages], output: news_report
**Default prompt (first 2 lines):** You are a news researcher tasked with analyzing recent news and trends over the past week. Please write a comprehensive report of the current state of the world that is relevant for trading and macroeconomics.
**JadeCap prompt (first 2 lines):** You are a JadeCap Macro News Analyst for {active} Futures ({instrument['description']}). Trade Date: {current_date} | Active Firm: {active_firm.upper()}
**Line count:** 178

#### fundamentals-analyst.md
**Frontmatter:** name: fundamentals-analyst, model: null, tools: [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement], strategy_variants: [default], memory: null, tier: quick, input: [trade_date, company_of_interest, messages], output: fundamentals_report
**Default prompt (first 2 lines):** You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials...
**JadeCap prompt:** N/A
**Line count:** 35

#### bull-researcher.md
**Frontmatter:** name: bull-researcher, model: null, tools: [], tools_jadecap: [fetch_live_price], memory: bull_memory, tier: quick, input: [investment_debate_state, market_report, sentiment_report, news_report, fundamentals_report, company_of_interest], output: investment_debate_state
**Default prompt (first 2 lines):** You are a Bull Analyst advocating for investing in the stock. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators.
**JadeCap prompt (first 2 lines):** You are the JadeCap Long Setup Analyst for {active} Futures. Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1
**Line count:** 278

#### bear-researcher.md
**Frontmatter:** name: bear-researcher, model: null, tools: [], tools_jadecap: [fetch_live_price], memory: bear_memory, tier: quick, input: [investment_debate_state, market_report, sentiment_report, news_report, fundamentals_report, company_of_interest], output: investment_debate_state
**Default prompt (first 2 lines):** You are a Bear Analyst making the case against investing in the stock. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators.
**JadeCap prompt (first 2 lines):** You are the JadeCap Short Setup Analyst for {active} Futures. Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1
**Line count:** 280

#### research-manager.md
**Frontmatter:** name: research-manager, model: null, tools: [], tools_jadecap: [fetch_live_price], memory: invest_judge_memory, tier: deep, input: [investment_debate_state, market_report, sentiment_report, news_report, fundamentals_report, company_of_interest], output: [investment_debate_state, investment_plan]
**Default prompt (first 2 lines):** As the portfolio manager and debate facilitator, your role is to critically evaluate this round of debate and make a definitive decision: align with the bear analyst, the bull analyst, or choose Hold only if it is strongly justified.
**JadeCap prompt (first 2 lines):** You are the JadeCap ICT Judge and Portfolio Manager for {active} Futures. Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1
**Line count:** 248

#### trader.md
**Frontmatter:** name: trader, model: null, tools: [], tools_jadecap: [fetch_live_price], memory: trader_memory, tier: quick, input: [company_of_interest, investment_plan, market_report, sentiment_report, news_report, fundamentals_report], output: [trader_investment_plan, sender]
**Default prompt (first 2 lines):** You are a trading agent analyzing market data to make investment decisions. Based on your analysis, provide a specific recommendation to buy, sell, or hold.
**JadeCap prompt (first 2 lines):** You are the JadeCap Trader Agent for {active} Futures using the ICT methodology. Your job is to take the Research Manager's investment plan, validate it one final time, size the position, and output a concrete TRADE PLAN or HOLD.
**Line count:** 220

#### aggressive-risk.md
**Frontmatter:** name: aggressive-risk, model: null, tools: [], tools_jadecap: [fetch_live_price], memory: null, tier: quick, input: [risk_debate_state, market_report, sentiment_report, news_report, fundamentals_report, trader_investment_plan, company_of_interest], output: risk_debate_state
**Default prompt (first 2 lines):** As the Aggressive Risk Analyst, your role is to actively champion high-reward, high-risk opportunities, emphasizing bold strategies and competitive advantages. When evaluating the trader's decision or plan, focus intently on the potential upside...
**JadeCap prompt (first 2 lines):** You are the JadeCap Aggressive Risk Analyst for NQ/ES Futures using ICT methodology. Your role: CHAMPION the trade when ICT confluence is strong.
**Line count:** 108

#### conservative-risk.md
**Frontmatter:** name: conservative-risk, model: null, tools: [], tools_jadecap: [fetch_live_price], memory: null, tier: quick, input: [risk_debate_state, market_report, sentiment_report, news_report, fundamentals_report, trader_investment_plan, company_of_interest], output: risk_debate_state
**Default prompt (first 2 lines):** As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation...
**JadeCap prompt (first 2 lines):** You are the JadeCap Conservative Risk Analyst for NQ/ES Futures using ICT methodology. Your role: PROTECT the prop firm account. Challenge marginal setups ruthlessly.
**Line count:** 118

#### neutral-risk.md
**Frontmatter:** name: neutral-risk, model: null, tools: [], tools_jadecap: [fetch_live_price], memory: null, tier: quick, input: [risk_debate_state, market_report, sentiment_report, news_report, fundamentals_report, trader_investment_plan, company_of_interest], output: risk_debate_state
**Default prompt (first 2 lines):** As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach...
**JadeCap prompt (first 2 lines):** You are the JadeCap Neutral Risk Analyst for NQ/ES Futures using ICT methodology. Your role: BALANCE both sides objectively. You don't default to "trade" or "no trade."
**Line count:** 121

#### portfolio-manager.md
**Frontmatter:** name: portfolio-manager, model: null, tools: [], tools_jadecap: [fetch_live_price], memory: portfolio_manager_memory, tier: deep, input: [risk_debate_state, market_report, sentiment_report, news_report, fundamentals_report, investment_plan, trader_investment_plan, company_of_interest], output: [risk_debate_state, final_trade_decision]
**Default prompt (first 2 lines):** As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision. {instrument_context}
**JadeCap prompt (first 2 lines):** You are the JadeCap Portfolio Manager -- the FINAL decision authority for {active} Futures. Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1
**Line count:** 242


---

## Phase 10: WebUI Trading Monitor + OpenClaw Agent Registration (added 2026-03-29)

> Full detailed plan with all code: `docs/superpowers/plans/2026-03-29-openclaw-trading-integration.md`

### What This Phase Adds

**OpenClaw Agent Registration:**
- `openclaw.json` → `agents.list` includes `trading-monitor` with label, description, tools profile, boot files
- `agents/trading-monitor/agent/models.json` — model config (GPT-5.4 primary, Claude Opus 4.6 deep think)

**Backend (5 new endpoints in `dashboard/web/backend/routes/trading.py`):**
- `GET /api/trading/status` → full state: config + DB runs + market phase + bias + watchlist signals + memory stats + risk + LLM + analysis + schedule + jadecap
- `PUT /api/trading/bias` → update direction (bullish/bearish/neutral) + reason + confidence (low/medium/high)
- `PUT /api/trading/halt` → toggle halt boolean, persists to trading-config.json
- `PUT /api/trading/watchlist` → add/remove/set tickers, persists to trading-config.json
- `PUT /api/trading/risk` → deep-merge risk parameters, persists to trading-config.json

**Frontend (7 new files):**
- `TradingMonitor.jsx` — main page (7 cards: halt switch, bias control, last run, watchlist, pipeline, risk, memory stats, LLM config). Auto-refreshes every 30 seconds.
- `HaltSwitch.jsx` — green ACTIVE / red HALTED toggle button. Calls `PUT /api/trading/halt`.
- `BiasControl.jsx` — 3 direction buttons (bullish/neutral/bearish) + 3 confidence buttons (low/medium/high) + reason text input. Calls `PUT /api/trading/bias`.
- `WatchlistPanel.jsx` — ticker input + add button + table (ticker, signal badge, date, status, correct, remove). Calls `PUT /api/trading/watchlist`.
- `PipelineStatus.jsx` — 4-tier pipeline visualization showing analysts, debate rounds, risk rotation, final signal. Reads from `/api/trading/status`.
- `RiskPanel.jsx` — 2-column grid of risk params. Adapts for JadeCap (adds ATR stop, T1 close, hard close, instrument).

**Modified Files:**
- `App.jsx` — add `/trading` route for TradingMonitor
- `Layout.jsx` — add "Trading" nav link, rename header from "TradingAgents" to "OpenClaw"
- `app.py` — register trading router

**Tests (5 new in `tests/test_trading_api.py`):**
- `test_bias_roundtrip` — set bias, reload, verify persisted
- `test_halt_roundtrip` — set halt, reload, verify
- `test_watchlist_add_remove` — add/remove tickers
- `test_risk_update` — update risk params, verify deep merge
- `test_schema_defaults_has_bias` — SCHEMA_DEFAULTS includes bias section

### Function Details

#### `GET /api/trading/status` Response Shape:
```json
{
  "state": "active" | "halted",
  "strategy": "default" | "jadecap",
  "market_phase": "pre" | "open" | "midday" | "close" | "post" | "closed",
  "bias": {"direction": "bullish", "reason": "...", "confidence": "high"},
  "watchlist": [{"ticker": "NVDA", "signal": "BUY", "date": "2026-03-28", "status": "completed", "correct": true}],
  "last_run": {"id": "...", "ticker": "NVDA", "trade_date": "...", "strategy": "...", "signal": "BUY", "status": "completed", "duration_seconds": 45.2, "created_at": "..."},
  "memory_stats": [{"agent": "bull_memory", "count": 5}],
  "risk": {"max_loss_per_trade": 500, ...},
  "llm": {"default": "gpt-4o", "deep_think": "claude-opus-4-6", "quick_think": "gpt-4o-mini", "per_agent": {}},
  "analysis": {"analysts": ["market", "news"], "max_debate_rounds": 1, ...},
  "schedule": {...},
  "jadecap": {...} | null
}
```

#### Component Props:
- `HaltSwitch({ halted: bool, onToggle: (newState) => void })`
- `BiasControl({ bias: {direction, reason, confidence}, onUpdate: (newBias) => void })`
- `WatchlistPanel({ watchlist: [{ticker, signal, date, status, correct}], onUpdate: (newWatchlist) => void })`
- `PipelineStatus({ analysis: {analysts, max_debate_rounds, ...}, strategy: string })`
- `RiskPanel({ risk: {max_loss_per_trade, ...}, jadecap: {...} | null })`

### Summary
| Phase | Tasks | Creates | Modifies |
|-------|-------|---------|----------|
| A. Agent Registration | 2 | `openclaw.json` entry, `agents/trading-monitor/` | `openclaw.json` |
| B. Backend API | 1 | `routes/trading.py`, `test_trading_api.py` | `app.py` |
| C. Frontend Components | 5 | 6 React components | — |
| D. Wire + Build | 1 | — | `App.jsx`, `Layout.jsx`, `dist/` |
| E. Plan + Push | 1 | — | plan .md |
| **Total** | **10** | **9 new files** | **4 modified** |

---

## Phase 11: Trading Tab in OpenClaw Control UI (added 2026-03-29)

> **SUPERSEDED** — This version replaced by the gateway-native Phase 11 below.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Trading" tab to the OpenClaw Control UI at `http://127.0.0.1:18789/trading` — the same dashboard that has Chat, Overview, Channels, Sessions, etc. One URL, one UI, trading is a first-class tab.

**How OpenClaw Control UI works:**
- Source: `/home/hoang/openclaw/ui/` — Vite + Lit web components
- Navigation: `ui/src/ui/navigation.ts` defines all tabs, paths, icons
- Views: `ui/src/ui/views/*.ts` — each tab is a function returning `html` (Lit template)
- Rendering: `ui/src/ui/app-render.ts` — maps `state.tab === "tabname"` to view render call
- State: `ui/src/ui/app-view-state.ts` — reactive state for each tab
- i18n: `ui/src/i18n/locales/en.ts` — tab labels + subtitles
- Lazy loading: views are lazy-imported to keep initial bundle small
- Build: `cd /home/hoang/openclaw && pnpm ui:build` → output to `dist/control-ui/`
- Gateway: serves built UI at `http://127.0.0.1:18789/`

**Data source for Trading tab:**
The Control UI communicates via WebSocket to the gateway. For trading data, we use the gateway's `agent` method to invoke the trading-monitor agent, OR we add a custom REST endpoint. Simplest: the Trading view reads `trading-config.json` and `trading.db` via a new gateway server method `trading.status`.

**But simpler first approach:** The trading view can call our existing FastAPI backend at `http://127.0.0.1:8200/api/trading/status` directly (CORS enabled). This avoids modifying gateway source. Phase 12 can migrate to native gateway methods later.

---

### File Structure

```
/home/hoang/openclaw/ui/src/
├── i18n/locales/en.ts                    ← MODIFY: add tabs.trading + subtitles.trading
├── ui/
│   ├── navigation.ts                     ← MODIFY: add "trading" tab + path + icon
│   ├── app-render.ts                     ← MODIFY: add state.tab === "trading" case
│   ├── app-view-state.ts                 ← MODIFY: add trading state fields
│   ├── controllers/
│   │   └── trading.ts                    ← CREATE: trading data controller
│   └── views/
│       └── trading.ts                    ← CREATE: trading tab Lit view

/home/hoang/.openclaw/workspace/
├── dashboard/web/backend/
│   ├── app.py                            ← MODIFY: add CORS for Control UI origin
│   └── routes/trading.py                 ← EXISTS (from Phase 10)
└── dashboard/web/run.py                  ← MODIFY: change port to 8200 (companion)
```

---

### Task 11.1: Add "trading" to navigation.ts

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/navigation.ts`

- [ ] **Step 1: Add "trading" to TAB_GROUPS**

In the `control` group, add `"trading"` after `"cron"`:

```typescript
{ label: "control", tabs: ["overview", "channels", "instances", "sessions", "usage", "cron", "trading"] },
```

- [ ] **Step 2: Add "trading" to Tab type**

```typescript
export type Tab =
  | "agents"
  | "overview"
  | "channels"
  | "instances"
  | "sessions"
  | "usage"
  | "cron"
  | "skills"
  | "nodes"
  | "chat"
  | "config"
  | "communications"
  | "appearance"
  | "automation"
  | "infrastructure"
  | "aiAgents"
  | "debug"
  | "logs"
  | "trading";
```

- [ ] **Step 3: Add path mapping**

```typescript
const TAB_PATHS: Record<Tab, string> = {
  // ... existing entries ...
  trading: "/trading",
};
```

- [ ] **Step 4: Add icon mapping**

In `iconForTab()`:

```typescript
case "trading":
  return "barChart";  // reuse the barChart icon (same as overview/usage)
```

- [ ] **Step 5: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/navigation.ts
git commit -m "feat: add trading tab to navigation"
```

---

### Task 11.2: Add i18n labels

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/i18n/locales/en.ts`

- [ ] **Step 1: Add tab label**

In the `tabs` section:

```typescript
tabs: {
  // ... existing entries ...
  trading: "Trading",
},
```

- [ ] **Step 2: Add subtitle**

In the `subtitles` section:

```typescript
subtitles: {
  // ... existing entries ...
  trading: "Market bias, watchlist, pipeline, risk.",
},
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/i18n/locales/en.ts
git commit -m "feat: add trading tab i18n labels"
```

---

### Task 11.3: Create trading controller

**Files:**
- Create: `/home/hoang/openclaw/ui/src/ui/controllers/trading.ts`

This controller fetches data from our FastAPI trading backend.

- [ ] **Step 1: Create the controller**

```typescript
// ui/src/ui/controllers/trading.ts
// Fetches trading status from the companion FastAPI backend.

export interface TradingBias {
  direction: "bullish" | "neutral" | "bearish";
  reason: string;
  confidence: "low" | "medium" | "high";
}

export interface WatchlistItem {
  ticker: string;
  signal: string | null;
  date: string | null;
  status: string | null;
  correct: boolean | null;
}

export interface LastRun {
  id: string;
  ticker: string;
  trade_date: string;
  strategy: string;
  signal: string;
  status: string;
  duration_seconds: number;
  created_at: string;
}

export interface MemoryStat {
  agent: string;
  count: number;
}

export interface TradingStatus {
  state: "active" | "halted";
  strategy: string;
  market_phase: string;
  bias: TradingBias;
  watchlist: WatchlistItem[];
  last_run: LastRun | null;
  memory_stats: MemoryStat[];
  risk: Record<string, number>;
  llm: Record<string, string>;
  analysis: Record<string, unknown>;
  schedule: Record<string, unknown>;
  jadecap: Record<string, unknown> | null;
}

const TRADING_API = "http://127.0.0.1:8200/api/trading";

export async function fetchTradingStatus(): Promise<TradingStatus | null> {
  try {
    const res = await fetch(`${TRADING_API}/status`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function setBias(bias: Partial<TradingBias>): Promise<TradingBias | null> {
  try {
    const res = await fetch(`${TRADING_API}/bias`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bias),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.bias;
  } catch {
    return null;
  }
}

export async function setHalt(halt: boolean): Promise<boolean> {
  try {
    const res = await fetch(`${TRADING_API}/halt`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ halt }),
    });
    if (!res.ok) return !halt;
    const data = await res.json();
    return data.halt;
  } catch {
    return !halt;
  }
}

export async function updateWatchlist(action: string, ticker: string): Promise<string[]> {
  try {
    const res = await fetch(`${TRADING_API}/watchlist`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ticker }),
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.watchlist;
  } catch {
    return [];
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/controllers/trading.ts
git commit -m "feat: add trading controller for API calls"
```

---

### Task 11.4: Create trading view

**Files:**
- Create: `/home/hoang/openclaw/ui/src/ui/views/trading.ts`

- [ ] **Step 1: Create the view**

```typescript
// ui/src/ui/views/trading.ts
// Trading Monitor tab — market bias, watchlist, pipeline, risk, memory stats.

import { html, nothing } from "lit";
import type { TradingStatus, WatchlistItem } from "../controllers/trading.ts";

export type TradingProps = {
  loading: boolean;
  status: TradingStatus | null;
  error: string | null;
  newTicker: string;
  onRefresh: () => void;
  onToggleHalt: () => void;
  onSetBias: (direction: string) => void;
  onSetConfidence: (confidence: string) => void;
  onBiasReasonChange: (reason: string) => void;
  onBiasReasonSave: () => void;
  onAddTicker: () => void;
  onRemoveTicker: (ticker: string) => void;
  onNewTickerChange: (value: string) => void;
};

const PHASE_LABELS: Record<string, string> = {
  pre: "Pre-Session", open: "Market Open", midday: "Midday",
  close: "Near Close", post: "Post-Session", closed: "Market Closed",
};

const SIGNAL_COLORS: Record<string, string> = {
  BUY: "#22c55e", OVERWEIGHT: "#86efac", HOLD: "#9ca3af",
  UNDERWEIGHT: "#fb923c", SELL: "#ef4444",
};

function signalBadge(signal: string | null) {
  if (!signal) return html`<span style="opacity:0.5">—</span>`;
  const color = SIGNAL_COLORS[signal.toUpperCase()] ?? "#9ca3af";
  return html`<span style="background:color-mix(in srgb,${color} 15%,transparent);color:${color};border:1px solid color-mix(in srgb,${color} 30%,transparent);padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600">${signal}</span>`;
}

function card(title: string, content: unknown) {
  return html`
    <div style="background:var(--claw-surface-1);border:1px solid var(--claw-border);border-radius:12px;padding:16px;margin-bottom:12px">
      <div style="font-weight:600;font-size:14px;margin-bottom:10px;color:var(--claw-text)">${title}</div>
      ${content}
    </div>`;
}

export function renderTrading(props: TradingProps) {
  const { loading, status: s, error } = props;

  if (loading) return html`<div style="padding:40px;text-align:center;opacity:0.5">Loading trading status…</div>`;
  if (!s) return html`<div style="padding:40px;text-align:center">
    <div style="opacity:0.5;margin-bottom:8px">Trading backend not available</div>
    <div style="font-size:12px;opacity:0.4">Start: <code>cd ~/.openclaw/workspace && python dashboard/web/run.py</code></div>
    <button @click=${props.onRefresh} style="margin-top:12px;padding:6px 16px;border-radius:8px;border:1px solid var(--claw-border);background:var(--claw-surface-1);color:var(--claw-text);cursor:pointer">Retry</button>
  </div>`;

  const phase = PHASE_LABELS[s.market_phase] ?? s.market_phase ?? "Unknown";
  const halted = s.state === "halted";
  const dir = s.bias?.direction ?? "neutral";

  return html`
    <div style="max-width:960px;margin:0 auto">
      <!-- Header -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <div>
          <div style="font-size:20px;font-weight:700;color:var(--claw-text)">Trading Monitor</div>
          <div style="font-size:12px;opacity:0.6">${s.strategy?.toUpperCase()} · ${phase}</div>
        </div>
        <button @click=${props.onToggleHalt}
          style="padding:8px 16px;border-radius:8px;font-weight:600;font-size:13px;cursor:pointer;border:1px solid ${halted ? "var(--claw-red)" : "var(--claw-green)"};background:color-mix(in srgb,${halted ? "var(--claw-red)" : "var(--claw-green)"} 12%,transparent);color:${halted ? "var(--claw-red)" : "var(--claw-green)"}">
          ${halted ? "⏸ HALTED — Resume" : "● ACTIVE — Halt"}
        </button>
      </div>

      ${error ? html`<div style="padding:10px 14px;background:color-mix(in srgb,var(--claw-red) 10%,transparent);border:1px solid var(--claw-red);border-radius:8px;margin-bottom:12px;font-size:13px;color:var(--claw-red)">${error}</div>` : nothing}

      <!-- Bias + Last Run row -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        ${card("Market Bias", html`
          <div style="display:flex;gap:6px;margin-bottom:8px">
            ${["bullish", "neutral", "bearish"].map((d) => {
              const active = dir === d;
              const color = d === "bullish" ? "var(--claw-green)" : d === "bearish" ? "var(--claw-red)" : "var(--claw-text-secondary)";
              return html`<button @click=${() => props.onSetBias(d)}
                style="flex:1;padding:6px;border-radius:8px;font-size:12px;font-weight:600;text-transform:capitalize;cursor:pointer;border:1.5px solid ${active ? color : "var(--claw-border)"};background:${active ? `color-mix(in srgb,${color} 12%,transparent)` : "transparent"};color:${active ? color : "var(--claw-text-secondary)"}">${d}</button>`;
            })}
          </div>
          <div style="display:flex;gap:4px;align-items:center;margin-bottom:8px">
            <span style="font-size:11px;opacity:0.6">Confidence:</span>
            ${["low", "medium", "high"].map((c) => html`
              <button @click=${() => props.onSetConfidence(c)}
                style="padding:2px 8px;border-radius:4px;font-size:11px;cursor:pointer;text-transform:capitalize;border:1px solid ${s.bias?.confidence === c ? "var(--claw-accent)" : "var(--claw-border)"};background:${s.bias?.confidence === c ? "color-mix(in srgb,var(--claw-accent) 10%,transparent)" : "transparent"};color:${s.bias?.confidence === c ? "var(--claw-accent)" : "var(--claw-text-secondary)"}">${c}</button>
            `)}
          </div>
          <input .value=${s.bias?.reason ?? ""} @input=${(e: Event) => props.onBiasReasonChange((e.target as HTMLInputElement).value)} @blur=${props.onBiasReasonSave} @keydown=${(e: KeyboardEvent) => e.key === "Enter" && props.onBiasReasonSave()}
            placeholder="Bias reason…" style="width:100%;padding:6px 10px;border-radius:8px;border:1px solid var(--claw-border);background:var(--claw-surface-2);color:var(--claw-text);font-size:12px;outline:none">
        `)}

        ${card("Last Run", s.last_run ? html`
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
            <span style="font-weight:600;color:var(--claw-text)">${s.last_run.ticker}</span>
            ${signalBadge(s.last_run.signal)}
          </div>
          <div style="font-size:11px;opacity:0.6">
            ${s.last_run.trade_date} · ${s.last_run.strategy} · ${s.last_run.duration_seconds?.toFixed(1)}s · ${s.last_run.status}
          </div>
        ` : html`<div style="opacity:0.5;font-size:13px">No runs yet</div>`)}
      </div>

      <!-- Watchlist -->
      ${card("Watchlist", html`
        <div style="display:flex;gap:6px;margin-bottom:10px">
          <input .value=${props.newTicker} @input=${(e: Event) => props.onNewTickerChange((e.target as HTMLInputElement).value.toUpperCase())} @keydown=${(e: KeyboardEvent) => e.key === "Enter" && props.onAddTicker()}
            placeholder="Add ticker" style="flex:1;padding:6px 10px;border-radius:8px;border:1px solid var(--claw-border);background:var(--claw-surface-2);color:var(--claw-text);font-size:12px;outline:none">
          <button @click=${props.onAddTicker} style="padding:6px 14px;border-radius:8px;background:var(--claw-accent);color:white;font-size:12px;font-weight:600;border:none;cursor:pointer">Add</button>
        </div>
        ${s.watchlist.length === 0 ? html`<div style="opacity:0.5;font-size:12px">No tickers — add one above</div>` : html`
          <table style="width:100%;font-size:12px;border-collapse:collapse">
            <thead><tr style="opacity:0.6">
              <th style="text-align:left;padding:4px 0">Ticker</th><th style="text-align:left">Signal</th>
              <th style="text-align:left">Date</th><th style="text-align:left">Status</th>
              <th style="text-align:center">OK?</th><th></th>
            </tr></thead>
            <tbody>${s.watchlist.map((w: WatchlistItem) => html`
              <tr style="border-top:1px solid var(--claw-border)">
                <td style="padding:6px 0;font-weight:600;color:var(--claw-text)">${w.ticker}</td>
                <td>${signalBadge(w.signal)}</td>
                <td style="opacity:0.6">${w.date ?? "—"}</td>
                <td style="opacity:0.6">${w.status ?? "—"}</td>
                <td style="text-align:center">${w.correct === true ? "✓" : w.correct === false ? "✗" : "—"}</td>
                <td style="text-align:right"><button @click=${() => props.onRemoveTicker(w.ticker)} style="color:var(--claw-red);background:none;border:none;cursor:pointer;font-size:11px">Remove</button></td>
              </tr>
            `)}</tbody>
          </table>
        `}
      `)}

      <!-- Pipeline + Risk row -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        ${card("Pipeline", html`
          ${[
            { label: "Tier 1: Analysts", detail: (s.analysis as Record<string,unknown>)?.analysts ? ((s.analysis as Record<string,string[]>).analysts).join(", ") : "market, social, news, fundamentals", color: "var(--claw-accent)" },
            { label: "Tier 2: Bull/Bear Debate", detail: `${(s.analysis as Record<string,number>)?.max_debate_rounds ?? 1} round`, color: "var(--claw-green)" },
            { label: "Tier 3: Judge + Trader + Risk", detail: `${(s.analysis as Record<string,number>)?.max_risk_discuss_rounds ?? 1} round`, color: "var(--claw-yellow,#f59e0b)" },
            { label: "Tier 4: Portfolio Manager", detail: "BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL", color: "var(--claw-red)" },
          ].map((tier) => html`
            <div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:var(--claw-surface-2);border-radius:8px;margin-bottom:4px">
              <span style="width:8px;height:8px;border-radius:50%;background:${tier.color};flex-shrink:0"></span>
              <div>
                <div style="font-size:12px;font-weight:500;color:var(--claw-text)">${tier.label}</div>
                <div style="font-size:11px;opacity:0.5">${tier.detail}</div>
              </div>
            </div>
          `)}
          <div style="font-size:11px;opacity:0.5;margin-top:4px">Strategy: <strong>${s.strategy}</strong> · Timeout: ${(s.analysis as Record<string,number>)?.agent_timeout_seconds ?? 300}s/agent</div>
        `)}

        ${card("Risk", html`
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
            ${[
              ["Max Loss/Trade", `$${s.risk?.max_loss_per_trade ?? 500}`],
              ["Daily Limit", `$${s.risk?.daily_loss_limit ?? 1000}`],
              ["Max Drawdown", `${s.risk?.max_drawdown_pct ?? 5}%`],
              ["Max Losses", `${s.risk?.max_consecutive_losses ?? 3}`],
              ["Min R:R", `${s.risk?.min_risk_reward ?? 3}:1`],
              ...(s.jadecap ? [
                ["ATR Stop", `${s.jadecap.atr_stop_multiplier ?? 1.5}x`],
                ["Hard Close", `${s.jadecap.hard_close_time ?? "15:45"} ET`],
                ["Instrument", `${s.jadecap.active_instrument ?? "NQ"}`],
              ] : []),
            ].map(([label, value]) => html`
              <div style="padding:6px 10px;background:var(--claw-surface-2);border-radius:6px">
                <div style="font-size:10px;opacity:0.5">${label}</div>
                <div style="font-size:13px;font-weight:600;color:var(--claw-text)">${value}</div>
              </div>
            `)}
          </div>
        `)}
      </div>

      <!-- Memory + LLM row -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        ${s.memory_stats?.length ? card("Memory", html`
          <div style="display:flex;flex-wrap:wrap;gap:6px">
            ${s.memory_stats.map((m: {agent:string;count:number}) => html`
              <span style="padding:4px 10px;background:var(--claw-surface-2);border-radius:6px;font-size:11px;color:var(--claw-text)">
                <strong>${m.agent}</strong> <span style="opacity:0.5">(${m.count})</span>
              </span>
            `)}
          </div>
        `) : nothing}

        ${card("LLM Config", html`
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px">
            ${[
              ["Default", s.llm?.default ?? "gpt-4o"],
              ["Deep", s.llm?.deep_think ?? "claude-opus-4-6"],
              ["Quick", s.llm?.quick_think ?? "gpt-4o-mini"],
            ].map(([label, value]) => html`
              <div style="padding:6px 10px;background:var(--claw-surface-2);border-radius:6px">
                <div style="font-size:10px;opacity:0.5">${label}</div>
                <div style="font-size:11px;font-weight:500;color:var(--claw-text)">${value}</div>
              </div>
            `)}
          </div>
        `)}
      </div>

      <div style="text-align:center;margin-top:8px">
        <button @click=${props.onRefresh} style="padding:4px 12px;border-radius:6px;font-size:11px;border:1px solid var(--claw-border);background:transparent;color:var(--claw-text-secondary);cursor:pointer">Refresh</button>
      </div>
    </div>
  `;
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/views/trading.ts
git commit -m "feat: add trading view with bias, watchlist, pipeline, risk panels"
```

---

### Task 11.5: Add trading state to app-view-state.ts

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/app-view-state.ts`

- [ ] **Step 1: Add trading state fields**

Add these fields to the `AppViewState` type (near other tab states):

```typescript
// Trading tab state
tradingLoading: boolean;
tradingStatus: import("./controllers/trading.ts").TradingStatus | null;
tradingError: string | null;
tradingNewTicker: string;
```

And initialize them in the constructor/defaults:

```typescript
tradingLoading: false,
tradingStatus: null,
tradingError: null,
tradingNewTicker: "",
```

Add a method:

```typescript
async loadTrading() {
  this.tradingLoading = true;
  this.tradingError = null;
  try {
    const { fetchTradingStatus } = await import("./controllers/trading.ts");
    this.tradingStatus = await fetchTradingStatus();
    if (!this.tradingStatus) this.tradingError = "Backend not available";
  } catch (e) {
    this.tradingError = String(e);
  } finally {
    this.tradingLoading = false;
  }
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/app-view-state.ts
git commit -m "feat: add trading state fields to AppViewState"
```

---

### Task 11.6: Wire trading view in app-render.ts

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/app-render.ts`

- [ ] **Step 1: Add lazy import**

Near the other lazy imports (around line 124-132):

```typescript
const lazyTrading = createLazy(() => import("./views/trading.ts"));
```

- [ ] **Step 2: Add render case**

Find the chain of `state.tab === "..."` conditionals (around line 1954). After the last one (e.g., `state.tab === "logs"`), add:

```typescript
          : state.tab === "trading"
            ? (() => {
                const mod = lazyTrading.get();
                if (!mod) { lazyTrading.load().then(() => state.requestUpdate()); return html`<div style="padding:40px;text-align:center;opacity:0.5">Loading…</div>`; }
                if (!state.tradingStatus && !state.tradingLoading) state.loadTrading();
                return mod.renderTrading({
                  loading: state.tradingLoading,
                  status: state.tradingStatus,
                  error: state.tradingError,
                  newTicker: state.tradingNewTicker,
                  onRefresh: () => state.loadTrading(),
                  onToggleHalt: async () => {
                    const { setHalt } = await import("./controllers/trading.ts");
                    const halted = state.tradingStatus?.state === "halted";
                    await setHalt(!halted);
                    state.loadTrading();
                  },
                  onSetBias: async (direction: string) => {
                    const { setBias } = await import("./controllers/trading.ts");
                    await setBias({ direction } as any);
                    state.loadTrading();
                  },
                  onSetConfidence: async (confidence: string) => {
                    const { setBias } = await import("./controllers/trading.ts");
                    await setBias({ confidence } as any);
                    state.loadTrading();
                  },
                  onBiasReasonChange: (reason: string) => { state.tradingNewTicker; /* trigger re-render */ },
                  onBiasReasonSave: async () => {
                    const { setBias } = await import("./controllers/trading.ts");
                    const input = (document.querySelector('input[placeholder="Bias reason…"]') as HTMLInputElement)?.value ?? "";
                    await setBias({ reason: input } as any);
                    state.loadTrading();
                  },
                  onAddTicker: async () => {
                    if (!state.tradingNewTicker.trim()) return;
                    const { updateWatchlist } = await import("./controllers/trading.ts");
                    await updateWatchlist("add", state.tradingNewTicker.trim());
                    state.tradingNewTicker = "";
                    state.loadTrading();
                  },
                  onRemoveTicker: async (ticker: string) => {
                    const { updateWatchlist } = await import("./controllers/trading.ts");
                    await updateWatchlist("remove", ticker);
                    state.loadTrading();
                  },
                  onNewTickerChange: (value: string) => { state.tradingNewTicker = value; },
                });
              })()
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/app-render.ts
git commit -m "feat: wire trading view into app-render with lazy loading"
```

---

### Task 11.7: Update FastAPI CORS + port

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/dashboard/web/backend/app.py`
- Modify: `/home/hoang/.openclaw/workspace/dashboard/web/run.py`

- [ ] **Step 1: Add Control UI origin to CORS**

In `app.py`, find the `CORSMiddleware` and add `"http://127.0.0.1:18789"` to `allow_origins`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "http://localhost:8200", "http://127.0.0.1:18789"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Change run.py port to 8200**

```python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8200)
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/.openclaw/workspace
git add dashboard/web/backend/app.py dashboard/web/run.py
git commit -m "feat: add Control UI CORS origin, change companion port to 8200"
```

---

### Task 11.8: Build and verify

- [ ] **Step 1: Build the Control UI**

```bash
cd /home/hoang/openclaw
pnpm ui:build
```
Expected: Build succeeds, output in `dist/control-ui/`

- [ ] **Step 2: Start the trading backend**

```bash
cd /home/hoang/.openclaw/workspace
python dashboard/web/run.py &
```
Expected: FastAPI running on port 8200

- [ ] **Step 3: Start the gateway**

```bash
openclaw gateway
```
Expected: Gateway running on port 18789

- [ ] **Step 4: Open the dashboard**

Open `http://127.0.0.1:18789/trading` in a browser.

Expected: Trading tab visible in the sidebar under "Control". Shows:
- Halt switch (green ACTIVE or red HALTED)
- Market bias (bullish/neutral/bearish buttons + confidence + reason)
- Last run info
- Watchlist table with add/remove
- Pipeline visualization (4 tiers)
- Risk parameters grid
- Memory stats
- LLM config

- [ ] **Step 5: Verify all other tabs still work**

Click through: Chat, Overview, Channels, Instances, Sessions, Cron, Agents, Skills, Config, Logs — all should work as before.

- [ ] **Step 6: Commit the build**

```bash
cd /home/hoang/openclaw
git add dist/control-ui/
git commit -m "build: rebuild Control UI with trading tab"
```

---

### Task 11.9: Run all workspace tests

- [ ] **Step 1: Run Python tests**

```bash
cd /home/hoang/.openclaw/workspace
.venv/bin/python -m pytest tests/ -v
```
Expected: 63+ tests pass

- [ ] **Step 2: Commit and push workspace**

```bash
cd /home/hoang/.openclaw/workspace
git add -A
git commit -m "feat: Phase 11 — Trading tab in OpenClaw Control UI"
git push origin main
```

---

### Summary

| Task | File | Action |
|------|------|--------|
| 11.1 | `navigation.ts` | Add trading tab + path + icon |
| 11.2 | `en.ts` | Add i18n labels |
| 11.3 | `controllers/trading.ts` | Create API controller (fetchTradingStatus, setBias, setHalt, updateWatchlist) |
| 11.4 | `views/trading.ts` | Create Lit view (renderTrading with 7 card panels) |
| 11.5 | `app-view-state.ts` | Add trading state fields + loadTrading() |
| 11.6 | `app-render.ts` | Wire lazy-loaded trading view into tab switch |
| 11.7 | `app.py` + `run.py` | CORS for 18789, change companion port to 8200 |
| 11.8 | Build + verify | `pnpm ui:build`, test in browser |
| 11.9 | Tests + push | Run Python tests, commit, push |

**Architecture:**
- OpenClaw gateway serves Control UI at `http://127.0.0.1:18789/trading`
- Trading view calls FastAPI companion backend at `http://127.0.0.1:8200/api/trading/*`
- All data comes from `trading-config.json` + `trading.db` via the existing backend endpoints
- No gateway source code modified — only the UI layer (Lit components)

---

## Phase 11: Trading Tab in OpenClaw Control UI — Gateway-Native (added 2026-03-29, rewritten 2026-03-28)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a first-class "Trading" tab to OpenClaw Control UI at `http://127.0.0.1:18789/trading`. All data flows through the existing gateway WebSocket on port 18789. Zero companion services. No FastAPI. No separate port.

**Architecture decision:** Gateway server methods (NOT FastAPI). The trading data methods run as TypeScript gateway server methods. They read `trading-config.json` and `trading.db` directly using Node.js `fs` + `better-sqlite3`. This keeps everything on port 18789 with zero companion services.

**What the Trading tab must show (9 panels):**
1. Halt switch — ACTIVE/HALTED toggle (reads/writes `config.halt`)
2. Market bias — direction (bullish/neutral/bearish) + confidence (low/medium/high) + reason text
3. Watchlist — table of tickers with latest signal, date, status, correct; add/remove
4. Last run — ticker, signal badge, date, strategy, duration, status
5. Pipeline — 4-tier visualization (analysts, debate, risk, PM) with config values
6. Risk parameters — max loss, daily limit, drawdown, consecutive losses, R:R + JadeCap extras
7. Memory stats — per-agent memory counts
8. LLM config — default/deep/quick models
9. Strategy — current strategy name + market phase

**Data sources (Python, in workspace):**
- Config: `/home/hoang/.openclaw/workspace/trading-config.json` (JSON, loaded by `openclaw/config.py`)
- Database: `/home/hoang/.openclaw/workspace/trading.db` (SQLite — runs, reports, debates, memories, outcomes)
- Market phase: `openclaw/heartbeat.py` `get_market_phase()`
- Schema defaults: `openclaw/config.py` `SCHEMA_DEFAULTS`

**Source locations:**
- UI: `/home/hoang/openclaw/ui/src/` (Vite + Lit web components)
- Gateway server methods: `/home/hoang/openclaw/src/gateway/server-methods/`
- Method registration: `/home/hoang/openclaw/src/gateway/server-methods.ts`
- Method scopes: `/home/hoang/openclaw/src/gateway/method-scopes.ts` (or equivalent)
- Navigation: `/home/hoang/openclaw/ui/src/ui/navigation.ts`
- i18n: `/home/hoang/openclaw/ui/src/i18n/locales/en.ts`
- Views: `/home/hoang/openclaw/ui/src/ui/views/`
- Controllers: `/home/hoang/openclaw/ui/src/ui/controllers/`
- State: `/home/hoang/openclaw/ui/src/ui/app-view-state.ts`
- Rendering: `/home/hoang/openclaw/ui/src/ui/app-render.ts`

**Prerequisite: Install better-sqlite3**

```bash
cd /home/hoang/openclaw
pnpm add better-sqlite3
pnpm add -D @types/better-sqlite3
```

**Gateway methods to add:**
- `trading.status` — read config + query DB -> full status object
- `trading.setBias` — update `config.bias` -> save
- `trading.setHalt` — update `config.halt` -> save
- `trading.updateWatchlist` — add/remove/set tickers -> save
- `trading.setRisk` — deep merge risk params -> save

---

### File Structure

```
/home/hoang/openclaw/src/gateway/
  server-methods/
    trading.ts                           <- CREATE: 5 handler functions
  server-methods.ts                        <- MODIFY: register tradingHandlers
  method-scopes.ts                         <- MODIFY: add trading.* scopes

/home/hoang/openclaw/ui/src/
  i18n/locales/en.ts                       <- MODIFY: add tabs.trading + subtitles.trading
  ui/
    navigation.ts                        <- MODIFY: add "trading" tab + path + icon
    app-render.ts                        <- MODIFY: add state.tab === "trading" case
    app-view-state.ts                    <- MODIFY: add trading state fields
    controllers/
      trading.ts                       <- CREATE: WS method calls via gateway
    views/
      trading.ts                       <- CREATE: renderTrading with all 9 panels
```

**Total: 18 tasks** (4 backend, 6 frontend, 2 config, 3 build/test, 3 cleanup)

---

### Task 11.1: Create server-methods/trading.ts with 5 handler functions

**Files:**
- Create: `/home/hoang/openclaw/src/gateway/server-methods/trading.ts`

**Dependencies:** None (first task).

- [ ] **Step 1: Create the trading server methods file**

This file exports `tradingHandlers` — an object whose keys are method names (`trading.status`, `trading.setBias`, etc.) and whose values are handler functions. Each handler reads/writes `trading-config.json` and queries `trading.db` using `better-sqlite3`.

```typescript
// /home/hoang/openclaw/src/gateway/server-methods/trading.ts
//
// Gateway server methods for the Trading tab.
// Reads trading-config.json + trading.db directly — no companion service.

import fs from "node:fs";
import path from "node:path";
import { homedir } from "node:os";
import Database from "better-sqlite3";

// --- Paths ----------------------------------------------------------------
const WORKSPACE = path.join(homedir(), ".openclaw", "workspace");
const CONFIG_PATH = path.join(WORKSPACE, "trading-config.json");
const DB_PATH = path.join(WORKSPACE, "trading.db");

// --- Schema defaults (mirrors openclaw/config.py SCHEMA_DEFAULTS) ---------
const SCHEMA_DEFAULTS: Record<string, unknown> = {
  halt: false,
  strategy: "default",
  bias: { direction: "neutral", confidence: "medium", reason: "" },
  watchlist: ["NVDA", "AAPL", "MSFT"],
  analysis: {
    analysts: ["market", "social", "news", "fundamentals"],
    max_debate_rounds: 1,
    max_risk_discuss_rounds: 1,
    agent_timeout_seconds: 300,
  },
  risk: {
    max_loss_per_trade: 500,
    daily_loss_limit: 1000,
    max_drawdown_pct: 5,
    max_consecutive_losses: 3,
    min_risk_reward: 3,
  },
  llm: {
    default: "gpt-4o",
    deep_think: "claude-opus-4-6",
    quick_think: "gpt-4o-mini",
    per_agent: {},
  },
  market_hours: { use: "auto" },
  jadecap: null,
};

// --- Helpers --------------------------------------------------------------

function readConfig(): Record<string, unknown> {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, "utf-8");
    const user = JSON.parse(raw);
    return deepMerge(structuredClone(SCHEMA_DEFAULTS), user);
  } catch {
    return structuredClone(SCHEMA_DEFAULTS) as Record<string, unknown>;
  }
}

function writeConfig(config: Record<string, unknown>): void {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2) + "\n", "utf-8");
}

function deepMerge(
  target: Record<string, unknown>,
  source: Record<string, unknown>,
): Record<string, unknown> {
  for (const key of Object.keys(source)) {
    if (
      source[key] &&
      typeof source[key] === "object" &&
      !Array.isArray(source[key]) &&
      target[key] &&
      typeof target[key] === "object" &&
      !Array.isArray(target[key])
    ) {
      target[key] = deepMerge(
        target[key] as Record<string, unknown>,
        source[key] as Record<string, unknown>,
      );
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

function getDb(): Database.Database {
  if (!fs.existsSync(DB_PATH)) {
    const db = new Database(DB_PATH);
    db.pragma("journal_mode = WAL");
    db.exec(`
      CREATE TABLE IF NOT EXISTS runs (
        id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        trade_date TEXT,
        strategy TEXT DEFAULT 'default',
        signal TEXT,
        status TEXT DEFAULT 'running',
        duration_seconds REAL,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
      );
      CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        situation TEXT,
        recommendation TEXT,
        ticker TEXT,
        created_at TEXT DEFAULT (datetime('now'))
      );
    `);
    return db;
  }
  const db = new Database(DB_PATH, { readonly: false });
  db.pragma("journal_mode = WAL");
  return db;
}

function getMarketPhase(): string {
  const now = new Date();
  const et = new Date(
    now.toLocaleString("en-US", { timeZone: "America/New_York" }),
  );
  const h = et.getHours();
  const m = et.getMinutes();
  const day = et.getDay();
  const minutes = h * 60 + m;

  if (day === 0 || day === 6) return "closed";
  if (minutes < 9 * 60 + 30) return "pre";
  if (minutes < 10 * 60) return "open";
  if (minutes < 14 * 60) return "midday";
  if (minutes < 16 * 60) return "close";
  if (minutes < 18 * 60) return "post";
  return "closed";
}

// --- Handlers -------------------------------------------------------------

import type { GatewayRequestHandlers } from "./types.js";

function errorShape(code: number, message: string) {
  return { code, message };
}

const ErrorCodes = { UNAVAILABLE: -1, INVALID_PARAMS: -2 } as const;

export const tradingHandlers: GatewayRequestHandlers = {
  "trading.status": async ({ params, respond, context }) => {
    try {
      const config = readConfig();

      let lastRun: Record<string, unknown> | null = null;
      let memoryStats: Array<{ agent: string; count: number }> = [];

      let db: Database.Database | null = null;
      try {
        db = getDb();

        const runRow = db
          .prepare(
            `SELECT id, ticker, trade_date, strategy, signal, status,
                    duration_seconds, created_at
             FROM runs ORDER BY created_at DESC LIMIT 1`,
          )
          .get() as Record<string, unknown> | undefined;

        if (runRow) {
          lastRun = {
            id: runRow.id,
            ticker: runRow.ticker,
            trade_date: runRow.trade_date,
            strategy: runRow.strategy,
            signal: runRow.signal,
            status: runRow.status,
            duration_seconds: runRow.duration_seconds,
            created_at: runRow.created_at,
          };
        }

        try {
          const memRows = db
            .prepare(
              `SELECT agent_name as agent, COUNT(*) as count
               FROM memories GROUP BY agent_name ORDER BY count DESC`,
            )
            .all() as Array<{ agent: string; count: number }>;
          memoryStats = memRows;
        } catch {
          memoryStats = [];
        }
      } catch {
        // DB may not exist
      } finally {
        if (db) db.close();
      }

      const watchlistTickers = (config.watchlist as string[]) ?? [];
      let watchlist: Array<Record<string, unknown>> = watchlistTickers.map(
        (t) => ({
          ticker: t,
          signal: null,
          date: null,
          status: null,
          correct: null,
        }),
      );

      try {
        db = getDb();
        for (let i = 0; i < watchlist.length; i++) {
          const row = db
            .prepare(
              `SELECT signal, trade_date, status FROM runs
               WHERE ticker = ? ORDER BY created_at DESC LIMIT 1`,
            )
            .get(watchlist[i].ticker as string) as
            | Record<string, unknown>
            | undefined;

          if (row) {
            watchlist[i].signal = row.signal ?? null;
            watchlist[i].date = row.trade_date ?? null;
            watchlist[i].status = row.status ?? null;
          }

          try {
            const outcome = db
              .prepare(
                `SELECT correct FROM outcomes
                 WHERE ticker = ? ORDER BY created_at DESC LIMIT 1`,
              )
              .get(watchlist[i].ticker as string) as
              | { correct: number | null }
              | undefined;
            if (outcome && outcome.correct !== null) {
              watchlist[i].correct = outcome.correct === 1;
            }
          } catch {
            // outcomes table may not exist
          }
        }
        db.close();
      } catch {
        // DB unavailable
      }

      respond(true, {
        state: config.halt ? "halted" : "active",
        strategy: config.strategy,
        market_phase: getMarketPhase(),
        bias: config.bias,
        watchlist,
        last_run: lastRun,
        memory_stats: memoryStats,
        risk: config.risk,
        llm: config.llm,
        analysis: config.analysis,
        schedule: config.schedule ?? {},
        jadecap: config.jadecap ?? null,
      });
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    }
  },

  "trading.setBias": async ({ params, respond, context }) => {
    try {
      const config = readConfig();
      const bias = (config.bias ?? {}) as Record<string, unknown>;

      if (params.direction !== undefined) {
        const valid = ["bullish", "neutral", "bearish"];
        if (valid.includes(params.direction as string)) {
          bias.direction = params.direction;
        }
      }
      if (params.confidence !== undefined) {
        const valid = ["low", "medium", "high"];
        if (valid.includes(params.confidence as string)) {
          bias.confidence = params.confidence;
        }
      }
      if (params.reason !== undefined) {
        bias.reason = String(params.reason);
      }

      config.bias = bias;
      writeConfig(config);
      respond(true, { bias: config.bias });
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    }
  },

  "trading.setHalt": async ({ params, respond, context }) => {
    try {
      const config = readConfig();
      const halt = Boolean(params.halt);
      config.halt = halt;
      writeConfig(config);
      respond(true, { halt });
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    }
  },

  "trading.updateWatchlist": async ({ params, respond, context }) => {
    try {
      const config = readConfig();
      let list = ((config.watchlist ?? []) as string[]).slice();
      const action = params.action as string;

      if (action === "add" && params.ticker) {
        const t = (params.ticker as string).toUpperCase().trim();
        if (t && !list.includes(t)) {
          list.push(t);
        }
      } else if (action === "remove" && params.ticker) {
        const t = (params.ticker as string).toUpperCase().trim();
        list = list.filter((x) => x !== t);
      } else if (action === "set" && Array.isArray(params.tickers)) {
        list = (params.tickers as string[])
          .map((t) => t.toUpperCase().trim())
          .filter(Boolean);
      }

      config.watchlist = list;
      writeConfig(config);
      respond(true, { watchlist: list });
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    }
  },

  "trading.setRisk": async ({ params, respond, context }) => {
    try {
      const config = readConfig();
      const risk = (config.risk ?? {}) as Record<string, unknown>;

      const numericFields = [
        "max_loss_per_trade",
        "daily_loss_limit",
        "max_drawdown_pct",
        "max_consecutive_losses",
        "min_risk_reward",
      ];
      for (const field of numericFields) {
        if (params[field] !== undefined) {
          const val = Number(params[field]);
          if (!isNaN(val)) {
            risk[field] = val;
          }
        }
      }

      if (params.jadecap && typeof params.jadecap === "object") {
        const jc = (config.jadecap ?? {}) as Record<string, unknown>;
        const jcParams = params.jadecap as Record<string, unknown>;
        if (jcParams.atr_stop_multiplier !== undefined)
          jc.atr_stop_multiplier = Number(jcParams.atr_stop_multiplier);
        if (jcParams.hard_close_time !== undefined)
          jc.hard_close_time = String(jcParams.hard_close_time);
        if (jcParams.active_instrument !== undefined)
          jc.active_instrument = String(jcParams.active_instrument);
        config.jadecap = jc;
      }

      config.risk = risk;
      writeConfig(config);
      respond(true, { risk: config.risk, jadecap: config.jadecap ?? null });
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    }
  },
};
```

- [ ] **Step 2: Verify the file compiles**

```bash
cd /home/hoang/openclaw
npx tsc --noEmit src/gateway/server-methods/trading.ts 2>&1 | head -20
```

Expected: No errors, or only errors related to imports that will resolve after `pnpm build`.

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add src/gateway/server-methods/trading.ts
git commit -m "feat(trading): add gateway server methods for trading tab"
```

---

### Task 11.2: Register tradingHandlers in server-methods.ts

**Files:**
- Modify: `/home/hoang/openclaw/src/gateway/server-methods.ts`

**Dependencies:** Task 11.1 (trading.ts must exist).

- [ ] **Step 1: Add import**

At the top of `server-methods.ts`, add the import alongside the other server-method imports:

```typescript
import { tradingHandlers } from "./server-methods/trading.js";
```

- [ ] **Step 2: Spread into coreGatewayHandlers**

Find the `coreGatewayHandlers` object (the spread of all handler objects) and add `...tradingHandlers`:

```typescript
export const coreGatewayHandlers = {
  // ... existing handler spreads ...
  ...tradingHandlers,
};
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add src/gateway/server-methods.ts
git commit -m "feat(trading): register tradingHandlers in gateway server-methods"
```

---

### Task 11.3: Add method scopes in method-scopes.ts

**Files:**
- Modify: `/home/hoang/openclaw/src/gateway/method-scopes.ts` (or the equivalent file that defines which methods require which auth scopes)

**Dependencies:** Task 11.1.

- [ ] **Step 1: Add trading method scopes**

Find the method-to-scope mapping. The file uses `READ_SCOPE` and `WRITE_SCOPE` arrays. Add trading methods to the appropriate scope — `trading.status` is read-only, mutations go in `WRITE_SCOPE`:

```typescript
[READ_SCOPE]: [
  // ... existing entries ...
  "trading.status",
],
[WRITE_SCOPE]: [
  // ... existing entries ...
  "trading.setBias",
  "trading.setHalt",
  "trading.updateWatchlist",
  "trading.setRisk",
],
```

**Note to implementer:** Read the existing `method-scopes.ts` file to confirm the exact `READ_SCOPE` / `WRITE_SCOPE` constant names and pattern. Match whatever convention is already in use.

- [ ] **Step 2: Commit**

```bash
cd /home/hoang/openclaw
git add src/gateway/method-scopes.ts
git commit -m "feat(trading): add trading.* method scopes"
```

---

### Task 11.4: Add protocol schema types (optional, good practice)

**Files:**
- Create or modify: `/home/hoang/openclaw/src/gateway/protocol/schema/trading.ts` (if a schema directory exists)

**Dependencies:** None (purely type definitions).

This task is optional. If the gateway has a `protocol/schema/` directory with Zod or TypeScript types for method params/results, add trading types there. If no such directory exists, skip this task — the types in the controller (Task 11.7) are sufficient.

- [ ] **Step 1: Check if protocol/schema directory exists**

```bash
ls -la /home/hoang/openclaw/src/gateway/protocol/schema/ 2>/dev/null || echo "No schema directory -- skip this task"
```

- [ ] **Step 2: If it exists, create trading schema types**

```typescript
// /home/hoang/openclaw/src/gateway/protocol/schema/trading.ts

export interface TradingBias {
  direction: "bullish" | "neutral" | "bearish";
  confidence: "low" | "medium" | "high";
  reason: string;
}

export interface WatchlistItem {
  ticker: string;
  signal: string | null;
  date: string | null;
  status: string | null;
  correct: boolean | null;
}

export interface LastRun {
  id: string;
  ticker: string;
  trade_date: string;
  strategy: string;
  signal: string;
  status: string;
  duration_seconds: number;
  created_at: string;
}

export interface MemoryStat {
  agent: string;
  count: number;
}

export interface TradingStatusResult {
  state: "active" | "halted";
  strategy: string;
  market_phase: string;
  bias: TradingBias;
  watchlist: WatchlistItem[];
  last_run: LastRun | null;
  memory_stats: MemoryStat[];
  risk: Record<string, number>;
  llm: Record<string, string>;
  analysis: Record<string, unknown>;
  schedule: Record<string, unknown>;
  jadecap: Record<string, unknown> | null;
}

export interface SetBiasParams {
  direction?: "bullish" | "neutral" | "bearish";
  confidence?: "low" | "medium" | "high";
  reason?: string;
}

export interface SetHaltParams {
  halt: boolean;
}

export interface UpdateWatchlistParams {
  action: "add" | "remove" | "set";
  ticker?: string;
  tickers?: string[];
}

export interface SetRiskParams {
  max_loss_per_trade?: number;
  daily_loss_limit?: number;
  max_drawdown_pct?: number;
  max_consecutive_losses?: number;
  min_risk_reward?: number;
  jadecap?: {
    atr_stop_multiplier?: number;
    hard_close_time?: string;
    active_instrument?: string;
  };
}
```

- [ ] **Step 3: Commit (if created)**

```bash
cd /home/hoang/openclaw
git add src/gateway/protocol/schema/trading.ts 2>/dev/null && \
  git commit -m "feat(trading): add protocol schema types for trading methods" || \
  echo "Skipped -- no schema directory"
```

---

### Task 11.5: Add "trading" to navigation.ts

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/navigation.ts`

**Dependencies:** None (frontend-only).

- [ ] **Step 1: Add "trading" to the Tab type union**

Find the `Tab` type and add `"trading"` as the last union member:

```typescript
export type Tab =
  | "agents"
  | "overview"
  | "channels"
  | "instances"
  | "sessions"
  | "usage"
  | "cron"
  | "skills"
  | "nodes"
  | "chat"
  | "config"
  | "communications"
  | "appearance"
  | "automation"
  | "infrastructure"
  | "aiAgents"
  | "debug"
  | "logs"
  | "trading";
```

- [ ] **Step 2: Add "trading" to the TAB_GROUPS array**

In the `control` group, add `"trading"` after `"cron"`:

```typescript
{ label: "control", tabs: ["overview", "channels", "instances", "sessions", "usage", "cron", "trading"] },
```

- [ ] **Step 3: Add path mapping in TAB_PATHS**

```typescript
const TAB_PATHS: Record<Tab, string> = {
  // ... existing entries ...
  trading: "/trading",
};
```

- [ ] **Step 4: Add icon mapping in iconForTab()**

```typescript
case "trading":
  return "barChart";
```

- [ ] **Step 5: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/navigation.ts
git commit -m "feat(trading): add trading tab to navigation"
```

---

### Task 11.6: Add i18n labels in en.ts

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/i18n/locales/en.ts`

**Dependencies:** None.

- [ ] **Step 1: Add tab label**

In the `tabs` object:

```typescript
tabs: {
  // ... existing entries ...
  trading: "Trading",
},
```

- [ ] **Step 2: Add subtitle**

In the `subtitles` object:

```typescript
subtitles: {
  // ... existing entries ...
  trading: "Market bias, watchlist, pipeline, risk.",
},
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/i18n/locales/en.ts
git commit -m "feat(trading): add i18n labels for trading tab"
```

---

### Task 11.7: Create controllers/trading.ts (gateway WS method calls)

**Files:**
- Create: `/home/hoang/openclaw/ui/src/ui/controllers/trading.ts`

**Dependencies:** Tasks 11.1-11.3 (gateway methods must be registered). But the controller can be written first — it just calls WS methods by name.

**Key difference from old Phase 11:** This controller calls gateway WebSocket methods (e.g., `client.request("trading.status", {})`) instead of `fetch("http://...")`. It uses the same `client.request()` pattern as all other controllers in the UI (see `controllers/cron.ts` for reference).

- [ ] **Step 1: Read an existing controller to confirm the WS call pattern**

```bash
head -60 /home/hoang/openclaw/ui/src/ui/controllers/cron.ts
```

The ACTUAL pattern: functions receive `client: GatewayBrowserClient` and call `client.request("method.name", params)`.

- [ ] **Step 2: Create the controller**

```typescript
// /home/hoang/openclaw/ui/src/ui/controllers/trading.ts
//
// Trading tab controller -- calls gateway WebSocket methods.
// All data flows through port 18789 WS, no companion service.

import type { GatewayBrowserClient } from "../gateway.ts";

// --- Types ----------------------------------------------------------------

export interface TradingBias {
  direction: "bullish" | "neutral" | "bearish";
  reason: string;
  confidence: "low" | "medium" | "high";
}

export interface WatchlistItem {
  ticker: string;
  signal: string | null;
  date: string | null;
  status: string | null;
  correct: boolean | null;
}

export interface LastRun {
  id: string;
  ticker: string;
  trade_date: string;
  strategy: string;
  signal: string;
  status: string;
  duration_seconds: number;
  created_at: string;
}

export interface MemoryStat {
  agent: string;
  count: number;
}

export interface TradingStatus {
  state: "active" | "halted";
  strategy: string;
  market_phase: string;
  bias: TradingBias;
  watchlist: WatchlistItem[];
  last_run: LastRun | null;
  memory_stats: MemoryStat[];
  risk: Record<string, number>;
  llm: Record<string, string>;
  analysis: Record<string, unknown>;
  schedule: Record<string, unknown>;
  jadecap: Record<string, unknown> | null;
}

// --- API Functions --------------------------------------------------------

export async function loadTradingStatus(client: GatewayBrowserClient): Promise<TradingStatus | null> {
  try {
    const res = await client.request<TradingStatus>("trading.status", {});
    return res ?? null;
  } catch {
    return null;
  }
}

export async function setBias(
  client: GatewayBrowserClient,
  bias: Partial<TradingBias>,
): Promise<TradingBias | null> {
  try {
    const result = await client.request<{ bias: TradingBias }>(
      "trading.setBias",
      bias as Record<string, unknown>,
    );
    return result?.bias ?? null;
  } catch {
    return null;
  }
}

export async function setHalt(client: GatewayBrowserClient, halt: boolean): Promise<boolean> {
  try {
    const result = await client.request<{ halt: boolean }>("trading.setHalt", { halt });
    return result?.halt ?? !halt;
  } catch {
    return !halt;
  }
}

export async function updateWatchlist(
  client: GatewayBrowserClient,
  action: "add" | "remove" | "set",
  ticker?: string,
  tickers?: string[],
): Promise<string[]> {
  try {
    const params: Record<string, unknown> = { action };
    if (ticker) params.ticker = ticker;
    if (tickers) params.tickers = tickers;
    const result = await client.request<{ watchlist: string[] }>("trading.updateWatchlist", params);
    return result?.watchlist ?? [];
  } catch {
    return [];
  }
}

export async function setRisk(
  client: GatewayBrowserClient,
  params: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  try {
    const result = await client.request<Record<string, unknown>>("trading.setRisk", params);
    return result ?? {};
  } catch {
    return {};
  }
}
```

**Important note for implementer:** This uses the `GatewayBrowserClient` + `client.request()` pattern from `controllers/cron.ts`. The `client` is obtained from `state.client` in the view/render layer and passed to each controller function.

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/controllers/trading.ts
git commit -m "feat(trading): add trading controller with gateway WS method calls"
```

---

### Task 11.8: Create views/trading.ts (renderTrading with all 9 panels)

**Files:**
- Create: `/home/hoang/openclaw/ui/src/ui/views/trading.ts`

**Dependencies:** Task 11.7 (controller types imported by view).

- [ ] **Step 1: Create the view**

```typescript
// /home/hoang/openclaw/ui/src/ui/views/trading.ts
//
// Trading Monitor tab -- 9 panels:
// 1. Halt switch, 2. Market bias, 3. Watchlist, 4. Last run,
// 5. Pipeline, 6. Risk parameters, 7. Memory stats, 8. LLM config, 9. Strategy

import { html, nothing } from "lit";
import type { TradingStatus, WatchlistItem } from "../controllers/trading.ts";

// --- Props ----------------------------------------------------------------

export type TradingProps = {
  loading: boolean;
  status: TradingStatus | null;
  error: string | null;
  newTicker: string;
  onRefresh: () => void;
  onToggleHalt: () => void;
  onSetBias: (direction: string) => void;
  onSetConfidence: (confidence: string) => void;
  onBiasReasonChange: (reason: string) => void;
  onBiasReasonSave: () => void;
  onAddTicker: () => void;
  onRemoveTicker: (ticker: string) => void;
  onNewTickerChange: (value: string) => void;
};

// --- Constants ------------------------------------------------------------

const PHASE_LABELS: Record<string, string> = {
  pre: "Pre-Session",
  open: "Market Open",
  midday: "Midday",
  close: "Near Close",
  post: "Post-Session",
  closed: "Market Closed",
};

const SIGNAL_COLORS: Record<string, string> = {
  BUY: "#22c55e",
  OVERWEIGHT: "#86efac",
  HOLD: "#9ca3af",
  UNDERWEIGHT: "#fb923c",
  SELL: "#ef4444",
};

// --- Helpers --------------------------------------------------------------

function signalBadge(signal: string | null) {
  if (!signal) return html`<span style="opacity:0.5">--</span>`;
  const color = SIGNAL_COLORS[signal.toUpperCase()] ?? "#9ca3af";
  return html`<span style="
    background: color-mix(in srgb, ${color} 15%, transparent);
    color: ${color};
    border: 1px solid color-mix(in srgb, ${color} 30%, transparent);
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 600;
  ">${signal}</span>`;
}

function card(title: string, content: unknown) {
  return html`
    <div style="
      background: var(--claw-surface-1);
      border: 1px solid var(--claw-border);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
    ">
      <div style="
        font-weight: 600;
        font-size: 14px;
        margin-bottom: 10px;
        color: var(--claw-text);
      ">${title}</div>
      ${content}
    </div>
  `;
}

function statBox(label: string, value: string) {
  return html`
    <div style="
      padding: 6px 10px;
      background: var(--claw-surface-2);
      border-radius: 6px;
    ">
      <div style="font-size: 10px; opacity: 0.5">${label}</div>
      <div style="font-size: 13px; font-weight: 600; color: var(--claw-text)">${value}</div>
    </div>
  `;
}

// --- Panel Renderers ------------------------------------------------------

function renderHaltAndStrategy(s: TradingStatus, props: TradingProps) {
  const phase = PHASE_LABELS[s.market_phase] ?? s.market_phase ?? "Unknown";
  const halted = s.state === "halted";

  return html`
    <div style="
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    ">
      <div>
        <div style="font-size: 20px; font-weight: 700; color: var(--claw-text)">
          Trading Monitor
        </div>
        <div style="font-size: 12px; opacity: 0.6">
          ${s.strategy?.toUpperCase() ?? "DEFAULT"} // ${phase}
        </div>
      </div>
      <button @click=${props.onToggleHalt} style="
        padding: 8px 16px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 13px;
        cursor: pointer;
        border: 1px solid ${halted ? "var(--claw-red)" : "var(--claw-green)"};
        background: color-mix(in srgb, ${halted ? "var(--claw-red)" : "var(--claw-green)"} 12%, transparent);
        color: ${halted ? "var(--claw-red)" : "var(--claw-green)"};
      ">
        ${halted ? "HALTED -- Resume" : "ACTIVE -- Halt"}
      </button>
    </div>
  `;
}

function renderBias(s: TradingStatus, props: TradingProps) {
  const dir = s.bias?.direction ?? "neutral";
  return card("Market Bias", html`
    <div style="display: flex; gap: 6px; margin-bottom: 8px">
      ${["bullish", "neutral", "bearish"].map((d) => {
        const active = dir === d;
        const color =
          d === "bullish"
            ? "var(--claw-green)"
            : d === "bearish"
              ? "var(--claw-red)"
              : "var(--claw-text-secondary)";
        return html`
          <button @click=${() => props.onSetBias(d)} style="
            flex: 1;
            padding: 6px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            text-transform: capitalize;
            cursor: pointer;
            border: 1.5px solid ${active ? color : "var(--claw-border)"};
            background: ${active
              ? `color-mix(in srgb, ${color} 12%, transparent)`
              : "transparent"};
            color: ${active ? color : "var(--claw-text-secondary)"};
          ">${d}</button>
        `;
      })}
    </div>
    <div style="display: flex; gap: 4px; align-items: center; margin-bottom: 8px">
      <span style="font-size: 11px; opacity: 0.6">Confidence:</span>
      ${["low", "medium", "high"].map((c) => html`
        <button @click=${() => props.onSetConfidence(c)} style="
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 11px;
          cursor: pointer;
          text-transform: capitalize;
          border: 1px solid ${s.bias?.confidence === c
            ? "var(--claw-accent)"
            : "var(--claw-border)"};
          background: ${s.bias?.confidence === c
            ? "color-mix(in srgb, var(--claw-accent) 10%, transparent)"
            : "transparent"};
          color: ${s.bias?.confidence === c
            ? "var(--claw-accent)"
            : "var(--claw-text-secondary)"};
        ">${c}</button>
      `)}
    </div>
    <input
      .value=${s.bias?.reason ?? ""}
      @input=${(e: Event) =>
        props.onBiasReasonChange((e.target as HTMLInputElement).value)}
      @blur=${props.onBiasReasonSave}
      @keydown=${(e: KeyboardEvent) =>
        e.key === "Enter" && props.onBiasReasonSave()}
      placeholder="Bias reason..."
      style="
        width: 100%;
        padding: 6px 10px;
        border-radius: 8px;
        border: 1px solid var(--claw-border);
        background: var(--claw-surface-2);
        color: var(--claw-text);
        font-size: 12px;
        outline: none;
        box-sizing: border-box;
      "
    >
  `);
}

function renderLastRun(s: TradingStatus) {
  return card(
    "Last Run",
    s.last_run
      ? html`
          <div style="
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
          ">
            <span style="font-weight: 600; color: var(--claw-text)">
              ${s.last_run.ticker}
            </span>
            ${signalBadge(s.last_run.signal)}
          </div>
          <div style="font-size: 11px; opacity: 0.6">
            ${s.last_run.trade_date} // ${s.last_run.strategy} //
            ${s.last_run.duration_seconds?.toFixed(1)}s // ${s.last_run.status}
          </div>
        `
      : html`<div style="opacity: 0.5; font-size: 13px">No runs yet</div>`,
  );
}

function renderWatchlist(s: TradingStatus, props: TradingProps) {
  return card("Watchlist", html`
    <div style="display: flex; gap: 6px; margin-bottom: 10px">
      <input
        .value=${props.newTicker}
        @input=${(e: Event) =>
          props.onNewTickerChange(
            (e.target as HTMLInputElement).value.toUpperCase(),
          )}
        @keydown=${(e: KeyboardEvent) =>
          e.key === "Enter" && props.onAddTicker()}
        placeholder="Add ticker"
        style="
          flex: 1;
          padding: 6px 10px;
          border-radius: 8px;
          border: 1px solid var(--claw-border);
          background: var(--claw-surface-2);
          color: var(--claw-text);
          font-size: 12px;
          outline: none;
        "
      >
      <button @click=${props.onAddTicker} style="
        padding: 6px 14px;
        border-radius: 8px;
        background: var(--claw-accent);
        color: white;
        font-size: 12px;
        font-weight: 600;
        border: none;
        cursor: pointer;
      ">Add</button>
    </div>
    ${s.watchlist.length === 0
      ? html`<div style="opacity: 0.5; font-size: 12px">
          No tickers -- add one above
        </div>`
      : html`
          <table style="width: 100%; font-size: 12px; border-collapse: collapse">
            <thead>
              <tr style="opacity: 0.6">
                <th style="text-align: left; padding: 4px 0">Ticker</th>
                <th style="text-align: left">Signal</th>
                <th style="text-align: left">Date</th>
                <th style="text-align: left">Status</th>
                <th style="text-align: center">OK?</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${s.watchlist.map(
                (w: WatchlistItem) => html`
                  <tr style="border-top: 1px solid var(--claw-border)">
                    <td style="
                      padding: 6px 0;
                      font-weight: 600;
                      color: var(--claw-text);
                    ">${w.ticker}</td>
                    <td>${signalBadge(w.signal)}</td>
                    <td style="opacity: 0.6">${w.date ?? "--"}</td>
                    <td style="opacity: 0.6">${w.status ?? "--"}</td>
                    <td style="text-align: center">
                      ${w.correct === true
                        ? "Y"
                        : w.correct === false
                          ? "N"
                          : "--"}
                    </td>
                    <td style="text-align: right">
                      <button
                        @click=${() => props.onRemoveTicker(w.ticker)}
                        style="
                          color: var(--claw-red);
                          background: none;
                          border: none;
                          cursor: pointer;
                          font-size: 11px;
                        "
                      >Remove</button>
                    </td>
                  </tr>
                `,
              )}
            </tbody>
          </table>
        `}
  `);
}

function renderPipeline(s: TradingStatus) {
  const analysis = (s.analysis ?? {}) as Record<string, unknown>;
  const tiers = [
    {
      label: "Tier 1: Analysts",
      detail: Array.isArray(analysis.analysts)
        ? (analysis.analysts as string[]).join(", ")
        : "market, social, news, fundamentals",
      color: "var(--claw-accent)",
    },
    {
      label: "Tier 2: Bull/Bear Debate",
      detail: `${(analysis.max_debate_rounds as number) ?? 1} round${
        ((analysis.max_debate_rounds as number) ?? 1) > 1 ? "s" : ""
      }`,
      color: "var(--claw-green)",
    },
    {
      label: "Tier 3: Judge + Trader + Risk",
      detail: `${(analysis.max_risk_discuss_rounds as number) ?? 1} round${
        ((analysis.max_risk_discuss_rounds as number) ?? 1) > 1 ? "s" : ""
      }`,
      color: "var(--claw-yellow, #f59e0b)",
    },
    {
      label: "Tier 4: Portfolio Manager",
      detail: "BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL",
      color: "var(--claw-red)",
    },
  ];

  return card("Pipeline", html`
    ${tiers.map(
      (tier) => html`
        <div style="
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 6px 10px;
          background: var(--claw-surface-2);
          border-radius: 8px;
          margin-bottom: 4px;
        ">
          <span style="
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: ${tier.color};
            flex-shrink: 0;
          "></span>
          <div>
            <div style="font-size: 12px; font-weight: 500; color: var(--claw-text)">
              ${tier.label}
            </div>
            <div style="font-size: 11px; opacity: 0.5">${tier.detail}</div>
          </div>
        </div>
      `,
    )}
    <div style="font-size: 11px; opacity: 0.5; margin-top: 4px">
      Strategy: <strong>${s.strategy}</strong> //
      Timeout: ${(analysis.agent_timeout_seconds as number) ?? 300}s/agent
    </div>
  `);
}

function renderRisk(s: TradingStatus) {
  const risk = (s.risk ?? {}) as Record<string, number>;
  const jc = s.jadecap as Record<string, unknown> | null;

  const items: Array<[string, string]> = [
    ["Max Loss/Trade", `$${risk.max_loss_per_trade ?? 500}`],
    ["Daily Limit", `$${risk.daily_loss_limit ?? 1000}`],
    ["Max Drawdown", `${risk.max_drawdown_pct ?? 5}%`],
    ["Max Losses", `${risk.max_consecutive_losses ?? 3}`],
    ["Min R:R", `${risk.min_risk_reward ?? 3}:1`],
  ];

  if (jc) {
    items.push(
      ["ATR Stop", `${jc.atr_stop_multiplier ?? 1.5}x`],
      ["Hard Close", `${jc.hard_close_time ?? "15:45"} ET`],
      ["Instrument", `${jc.active_instrument ?? "NQ"}`],
    );
  }

  return card("Risk Parameters", html`
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px">
      ${items.map(([label, value]) => statBox(label, value))}
    </div>
  `);
}

function renderMemoryStats(s: TradingStatus) {
  if (!s.memory_stats?.length) return nothing;
  return card("Memory", html`
    <div style="display: flex; flex-wrap: wrap; gap: 6px">
      ${s.memory_stats.map(
        (m: { agent: string; count: number }) => html`
          <span style="
            padding: 4px 10px;
            background: var(--claw-surface-2);
            border-radius: 6px;
            font-size: 11px;
            color: var(--claw-text);
          ">
            <strong>${m.agent}</strong>
            <span style="opacity: 0.5">(${m.count})</span>
          </span>
        `,
      )}
    </div>
  `);
}

function renderLlmConfig(s: TradingStatus) {
  const llm = (s.llm ?? {}) as Record<string, string>;
  return card("LLM Config", html`
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px">
      ${[
        ["Default", llm.default ?? "gpt-4o"],
        ["Deep", llm.deep_think ?? "claude-opus-4-6"],
        ["Quick", llm.quick_think ?? "gpt-4o-mini"],
      ].map(
        ([label, value]) => html`
          <div style="
            padding: 6px 10px;
            background: var(--claw-surface-2);
            border-radius: 6px;
          ">
            <div style="font-size: 10px; opacity: 0.5">${label}</div>
            <div style="
              font-size: 11px;
              font-weight: 500;
              color: var(--claw-text);
            ">${value}</div>
          </div>
        `,
      )}
    </div>
  `);
}

// --- Main Render Function -------------------------------------------------

export function renderTrading(props: TradingProps) {
  const { loading, status: s, error } = props;

  if (loading) {
    return html`<div style="padding: 40px; text-align: center; opacity: 0.5">
      Loading trading status...
    </div>`;
  }

  if (!s) {
    return html`
      <div style="padding: 40px; text-align: center">
        <div style="opacity: 0.5; margin-bottom: 8px">
          Trading data not available
        </div>
        <div style="font-size: 12px; opacity: 0.4">
          Ensure <code>trading-config.json</code> exists in
          <code>~/.openclaw/workspace/</code>
        </div>
        <button @click=${props.onRefresh} style="
          margin-top: 12px;
          padding: 6px 16px;
          border-radius: 8px;
          border: 1px solid var(--claw-border);
          background: var(--claw-surface-1);
          color: var(--claw-text);
          cursor: pointer;
        ">Retry</button>
      </div>
    `;
  }

  return html`
    <div style="max-width: 960px; margin: 0 auto">
      ${renderHaltAndStrategy(s, props)}

      ${error
        ? html`
            <div style="
              padding: 10px 14px;
              background: color-mix(in srgb, var(--claw-red) 10%, transparent);
              border: 1px solid var(--claw-red);
              border-radius: 8px;
              margin-bottom: 12px;
              font-size: 13px;
              color: var(--claw-red);
            ">${error}</div>
          `
        : nothing}

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
        ${renderBias(s, props)}
        ${renderLastRun(s)}
      </div>

      ${renderWatchlist(s, props)}

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
        ${renderPipeline(s)}
        ${renderRisk(s)}
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px">
        ${renderMemoryStats(s)}
        ${renderLlmConfig(s)}
      </div>

      <div style="text-align: center; margin-top: 8px">
        <button @click=${props.onRefresh} style="
          padding: 4px 12px;
          border-radius: 6px;
          font-size: 11px;
          border: 1px solid var(--claw-border);
          background: transparent;
          color: var(--claw-text-secondary);
          cursor: pointer;
        ">Refresh</button>
      </div>
    </div>
  `;
}
```

- [ ] **Step 2: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/views/trading.ts
git commit -m "feat(trading): add trading view with all 9 panels"
```

---

### Task 11.9: Add trading state to app-view-state.ts

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/app-view-state.ts`

**Dependencies:** Task 11.7 (controller types).

- [ ] **Step 1: Add state fields to AppViewState type**

Find the `AppViewState` type/interface and add these fields alongside other tab-specific state:

```typescript
// Trading tab state
tradingLoading: boolean;
tradingStatus: import("./controllers/trading.ts").TradingStatus | null;
tradingError: string | null;
tradingNewTicker: string;
```

- [ ] **Step 2: Add initial values**

In the constructor or default values object:

```typescript
tradingLoading: false,
tradingStatus: null,
tradingError: null,
tradingNewTicker: "",
```

- [ ] **Step 3: Add loadTrading() method**

Add this method to the class (or state object, depending on pattern):

```typescript
async loadTrading() {
  this.tradingLoading = true;
  this.tradingError = null;
  this.requestUpdate();
  try {
    const { fetchTradingStatus } = await import("./controllers/trading.ts");
    this.tradingStatus = await fetchTradingStatus();
    if (!this.tradingStatus) {
      this.tradingError = "Gateway returned no trading data";
    }
  } catch (e) {
    this.tradingError = String(e);
  } finally {
    this.tradingLoading = false;
    this.requestUpdate();
  }
}
```

**Note:** If the state uses a reactive framework (e.g., Lit reactive properties, or a custom reactive store), ensure `tradingLoading`, `tradingStatus`, `tradingError`, and `tradingNewTicker` are declared as reactive. Match how other tab states (e.g., `cronLoading`, `sessionsLoading`) are declared.

- [ ] **Step 4: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/app-view-state.ts
git commit -m "feat(trading): add trading state fields and loadTrading() to AppViewState"
```

---

### Task 11.10: Wire view in app-render.ts (lazy import + tab case)

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/app-render.ts`

**Dependencies:** Tasks 11.7, 11.8, 11.9 (controller, view, and state must exist).

- [ ] **Step 1: Add lazy import**

Near the other `createLazy(() => import("./views/..."))` calls:

```typescript
const lazyTrading = createLazy(() => import("./views/trading.ts"));
```

- [ ] **Step 2: Add render case**

Find the chain of `state.tab === "..."` ternary conditionals. After the last existing case (e.g., `state.tab === "logs"`), add:

```typescript
          : state.tab === "trading"
            ? (() => {
                if (!state.tradingStatus && !state.tradingLoading) {
                  state.loadTrading();
                }
                return lazyRender(lazyTrading, (m) =>
                  m.renderTrading({
                    loading: state.tradingLoading,
                    status: state.tradingStatus,
                    error: state.tradingError,
                    newTicker: state.tradingNewTicker,
                    onRefresh: () => state.loadTrading(),
                    onToggleHalt: async () => {
                      const { setHalt } = await import("./controllers/trading.ts");
                      const halted = state.tradingStatus?.state === "halted";
                      await setHalt(state.client, !halted);
                      state.loadTrading();
                    },
                    onSetBias: async (direction: string) => {
                      const { setBias } = await import("./controllers/trading.ts");
                      await setBias(state.client, { direction } as any);
                      state.loadTrading();
                    },
                    onSetConfidence: async (confidence: string) => {
                      const { setBias } = await import("./controllers/trading.ts");
                      await setBias(state.client, { confidence } as any);
                      state.loadTrading();
                    },
                    onBiasReasonChange: (reason: string) => {
                      void reason;
                    },
                    onBiasReasonSave: async () => {
                      const { setBias } = await import("./controllers/trading.ts");
                      const input =
                        (document.querySelector(
                          'input[placeholder="Bias reason..."]',
                        ) as HTMLInputElement)?.value ?? "";
                      await setBias(state.client, { reason: input });
                      state.loadTrading();
                    },
                    onAddTicker: async () => {
                      if (!state.tradingNewTicker.trim()) return;
                      const { updateWatchlist } = await import(
                        "./controllers/trading.ts"
                      );
                      await updateWatchlist(state.client, "add", state.tradingNewTicker.trim());
                      state.tradingNewTicker = "";
                      state.loadTrading();
                    },
                    onRemoveTicker: async (ticker: string) => {
                      const { updateWatchlist } = await import(
                        "./controllers/trading.ts"
                      );
                      await updateWatchlist(state.client, "remove", ticker);
                      state.loadTrading();
                    },
                    onNewTickerChange: (value: string) => {
                      state.tradingNewTicker = value;
                      state.requestUpdate();
                    },
                  })
                );
              })()
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/app-render.ts
git commit -m "feat(trading): wire trading view into app-render with lazy loading"
```

---

### Task 11.11: Add trading config section to views/config.ts (optional)

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/views/config.ts` (if it exists and has editable config sections)

**Dependencies:** Task 11.7 (controller for `setRisk`).

This task is optional. If the config view already has sections for other features, add a "Trading" section. Otherwise, risk editing can be done directly from the Trading tab's Risk card in a future iteration.

- [ ] **Step 1: Check if config.ts has editable sections**

```bash
head -50 /home/hoang/openclaw/ui/src/ui/views/config.ts
```

- [ ] **Step 2: If applicable, add a "Trading Risk" section**

```typescript
// Add to the config view's render function, in a new section:
${card("Trading Risk Parameters", html`
  <div style="font-size: 12px; opacity: 0.6; margin-bottom: 8px">
    Edit risk parameters in <code>~/.openclaw/workspace/trading-config.json</code>
    or use the Trading tab.
  </div>
`)}
```

- [ ] **Step 3: Commit (if changes made)**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/views/config.ts 2>/dev/null && \
  git commit -m "feat(trading): add trading config reference to config view" || \
  echo "Skipped"
```

---

### Task 11.12: Ensure trading-config.json bias field in SCHEMA_DEFAULTS

**Files:**
- Verify: `/home/hoang/.openclaw/workspace/openclaw/config.py`
- Verify: `/home/hoang/.openclaw/workspace/trading-config.json`

**Dependencies:** None.

- [ ] **Step 1: Verify SCHEMA_DEFAULTS includes bias**

```bash
grep -A 5 '"bias"' /home/hoang/.openclaw/workspace/openclaw/config.py
```

Expected output should include:
```python
"bias": {"direction": "neutral", "confidence": "medium", "reason": ""},
```

If missing, add it to SCHEMA_DEFAULTS.

- [ ] **Step 2: Verify trading-config.json is valid JSON**

```bash
python3 -c "import json; json.load(open('/home/hoang/.openclaw/workspace/trading-config.json'))" && echo "Valid JSON"
```

Expected: `Valid JSON`

- [ ] **Step 3: Verify bias field exists in config**

```bash
python3 -c "
import json
c = json.load(open('/home/hoang/.openclaw/workspace/trading-config.json'))
print('bias:', c.get('bias', 'MISSING'))
print('halt:', c.get('halt', 'MISSING'))
print('watchlist:', c.get('watchlist', 'MISSING'))
print('risk:', c.get('risk', 'MISSING'))
"
```

If any field shows `MISSING`, add it to the config file or confirm that `SCHEMA_DEFAULTS` in `config.py` provides the default (the gateway handler in Task 11.1 also has fallback defaults).

---

### Task 11.13: Build gateway

**Dependencies:** Tasks 11.1-11.3 (all backend changes).

- [ ] **Step 1: Install better-sqlite3 if not already present**

```bash
cd /home/hoang/openclaw && pnpm ls better-sqlite3 2>/dev/null || pnpm add better-sqlite3 && pnpm add -D @types/better-sqlite3
```

- [ ] **Step 2: Build gateway**

```bash
cd /home/hoang/openclaw && pnpm build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Verify trading handlers are in the build output**

```bash
grep -r "trading.status" /home/hoang/openclaw/dist/ | head -5
```

Expected: At least one match showing the handler was compiled.

---

### Task 11.14: Build UI

**Dependencies:** Tasks 11.5-11.10 (all frontend changes).

- [ ] **Step 1: Build the Control UI**

```bash
cd /home/hoang/openclaw && pnpm ui:build
```

Expected: Build succeeds, output in `dist/control-ui/`

- [ ] **Step 2: Verify trading assets exist**

```bash
grep -r "trading" /home/hoang/openclaw/dist/control-ui/assets/ | head -5
```

Expected: Trading module code appears in the bundled JS.

---

### Task 11.15: Verify end-to-end

**Dependencies:** Tasks 11.13, 11.14 (both builds must pass).

- [ ] **Step 1: Start the gateway**

```bash
cd /home/hoang/openclaw && openclaw gateway &
```

Expected: Gateway running on port 18789.

- [ ] **Step 2: Open the dashboard**

Open `http://127.0.0.1:18789/` in a browser. Navigate to the Trading tab (should appear in the "Control" section of the sidebar).

- [ ] **Step 3: Verify all 9 panels render**

Expected:
1. Halt switch -- green "ACTIVE - Halt" button (or red "HALTED - Resume")
2. Market bias -- bullish/neutral/bearish buttons, confidence low/medium/high, reason input
3. Watchlist -- table with ticker, signal badge, date, status, correct column, add/remove
4. Last run -- ticker + signal badge + date + strategy + duration + status (or "No runs yet")
5. Pipeline -- 4 tiers with colored dots, analyst names, debate rounds, timeout
6. Risk parameters -- grid of max loss, daily limit, drawdown, consecutive losses, R:R (+ JadeCap if configured)
7. Memory stats -- per-agent badges with counts (or hidden if no memories)
8. LLM config -- default/deep/quick model names
9. Strategy -- shown in header next to market phase

- [ ] **Step 4: Test interactions**

1. Click "Halt" button -> should toggle to "HALTED"
2. Click a bias direction -> should update immediately
3. Change confidence -> should update
4. Type a bias reason and press Enter -> should save
5. Add a ticker (type "TSLA" + Enter) -> should appear in watchlist
6. Remove a ticker -> should disappear
7. Click "Refresh" -> should reload all data

- [ ] **Step 5: Verify other tabs still work**

Click through: Chat, Overview, Channels, Instances, Sessions, Cron, Agents, Skills, Config, Logs -- all should work as before.

- [ ] **Step 6: Kill the gateway**

```bash
kill %1
```

---

### Task 11.16: Remove dashboard/web/ FastAPI backend (no longer needed)

**Files:**
- Delete: `/home/hoang/.openclaw/workspace/dashboard/web/backend/`
- Delete: `/home/hoang/.openclaw/workspace/dashboard/web/run.py`

**Dependencies:** Task 11.15 (verify gateway-native approach works first).

- [ ] **Step 1: Confirm no other code depends on the FastAPI backend**

```bash
grep -r "8200\|dashboard/web/backend\|dashboard/web/run" /home/hoang/.openclaw/workspace/ --include="*.py" --include="*.ts" --include="*.md" | grep -v "plans/" | grep -v ".git/"
```

Expected: No critical imports or references outside the plan docs.

- [ ] **Step 2: Move to trash (not delete)**

```bash
cd /home/hoang/.openclaw/workspace
mkdir -p .trash/dashboard-web-backend-$(date +%Y%m%d)
mv dashboard/web/backend/ .trash/dashboard-web-backend-$(date +%Y%m%d)/backend/
mv dashboard/web/run.py .trash/dashboard-web-backend-$(date +%Y%m%d)/run.py 2>/dev/null || true
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/.openclaw/workspace
git add -A dashboard/web/
git commit -m "chore: remove FastAPI backend (replaced by gateway-native trading methods)"
```

---

### Task 11.17: Remove dashboard/web/frontend/ React app (replaced by Lit)

**Files:**
- Delete: `/home/hoang/.openclaw/workspace/dashboard/web/frontend/`

**Dependencies:** Task 11.15.

- [ ] **Step 1: Move to trash**

```bash
cd /home/hoang/.openclaw/workspace
mkdir -p .trash/dashboard-web-frontend-$(date +%Y%m%d)
mv dashboard/web/frontend/ .trash/dashboard-web-frontend-$(date +%Y%m%d)/frontend/ 2>/dev/null || true
```

- [ ] **Step 2: Remove empty dashboard/web/ directory if empty**

```bash
rmdir /home/hoang/.openclaw/workspace/dashboard/web/ 2>/dev/null || echo "Directory not empty, leaving"
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/.openclaw/workspace
git add -A dashboard/
git commit -m "chore: remove React frontend (replaced by Lit trading tab in OpenClaw Control UI)"
```

---

### Task 11.18: Update CLAUDE.md and plan doc

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/CLAUDE.md`
- Modify: `/home/hoang/.openclaw/workspace/docs/superpowers/plans/2026-03-27-openclaw-tradingagents-merge.md`

**Dependencies:** Tasks 11.15-11.17.

- [ ] **Step 1: Update CLAUDE.md architecture section**

Replace the old `dashboard/web/` references:

Old:
```
dashboard/web/         <- React + FastAPI web dashboard
```

New:
```
# dashboard/web/ is REMOVED -- trading UI is now a native tab in OpenClaw Control UI
# Access at http://127.0.0.1:18789/trading (served by gateway on port 18789)
```

Update the Key Dependencies section -- remove:
```
Optional (webui): `fastapi`, `uvicorn`, `websockets`, `smartmoneyconcepts`, `databento`
```

Replace with:
```
Optional: `smartmoneyconcepts`, `databento`
# FastAPI/uvicorn no longer needed -- trading UI is gateway-native
```

- [ ] **Step 2: Update plan doc -- mark old Phase 11 as superseded**

At the top of the old Phase 11 section (around line 4344), add a deprecation notice:

```markdown
> **SUPERSEDED:** This version of Phase 11 used a FastAPI companion backend on port 8200.
> It has been replaced by the gateway-native version below (Phase 11, rewritten 2026-03-28).
> The gateway-native approach requires no companion service -- all data flows through the
> existing WebSocket on port 18789.
```

- [ ] **Step 3: Run workspace tests**

```bash
cd /home/hoang/.openclaw/workspace
.venv/bin/python -m pytest tests/ -v
```

Expected: All tests pass (63+).

- [ ] **Step 4: Commit everything**

```bash
cd /home/hoang/.openclaw/workspace
git add CLAUDE.md docs/
git commit -m "docs: update CLAUDE.md and plan for gateway-native trading tab (Phase 11 rewrite)"
```

```bash
cd /home/hoang/openclaw
git add -A
git commit -m "feat: Phase 11 complete -- Trading tab in OpenClaw Control UI (gateway-native)"
```

---

### Summary

| Task | File(s) | Action |
|------|---------|--------|
| 11.1 | `src/gateway/server-methods/trading.ts` | Create 5 handler functions (status, setBias, setHalt, updateWatchlist, setRisk) |
| 11.2 | `src/gateway/server-methods.ts` | Register `...tradingHandlers` in `coreGatewayHandlers` |
| 11.3 | `src/gateway/method-scopes.ts` | Add `trading.*` method scopes |
| 11.4 | `src/gateway/protocol/schema/trading.ts` | Optional: protocol types |
| 11.5 | `ui/src/ui/navigation.ts` | Add `"trading"` to Tab type, TAB_GROUPS, TAB_PATHS, iconForTab |
| 11.6 | `ui/src/i18n/locales/en.ts` | Add `tabs.trading` + `subtitles.trading` |
| 11.7 | `ui/src/ui/controllers/trading.ts` | Create controller with WS method calls |
| 11.8 | `ui/src/ui/views/trading.ts` | Create view with all 9 panels |
| 11.9 | `ui/src/ui/app-view-state.ts` | Add trading state fields + `loadTrading()` |
| 11.10 | `ui/src/ui/app-render.ts` | Wire lazy-loaded trading view into tab switch |
| 11.11 | `ui/src/ui/views/config.ts` | Optional: trading config reference |
| 11.12 | `openclaw/config.py` + `trading-config.json` | Verify bias/halt/watchlist/risk in SCHEMA_DEFAULTS |
| 11.13 | Build gateway | `pnpm build` -- verify trading handlers compiled |
| 11.14 | Build UI | `pnpm ui:build` -- verify trading assets bundled |
| 11.15 | Verify | Start gateway, open `/trading`, test all 9 panels + interactions |
| 11.16 | `dashboard/web/backend/` | Remove FastAPI backend (move to `.trash/`) |
| 11.17 | `dashboard/web/frontend/` | Remove React app (move to `.trash/`) |
| 11.18 | `CLAUDE.md` + plan doc | Update architecture docs, mark old Phase 11 superseded |

**Architecture (final):**
- OpenClaw gateway serves Control UI at `http://127.0.0.1:18789/`
- Trading tab at `http://127.0.0.1:18789/trading`
- All data flows via WebSocket methods (`trading.status`, `trading.setBias`, `trading.setHalt`, `trading.updateWatchlist`, `trading.setRisk`)
- Gateway reads `~/.openclaw/workspace/trading-config.json` + `~/.openclaw/workspace/trading.db` directly
- Zero companion services. One port. One UI. Trading is a first-class tab.
- `better-sqlite3` added as gateway dependency for direct SQLite access
- FastAPI backend and React frontend are removed after verification
