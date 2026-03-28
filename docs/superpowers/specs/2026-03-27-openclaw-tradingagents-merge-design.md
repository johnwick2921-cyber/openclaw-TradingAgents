# Design: Merge TradingAgents into OpenClaw

**Date:** 2026-03-27
**Status:** Approved
**Goal:** Unify TradingAgents (4-tier LLM trading analysis pipeline) with OpenClaw (agent identity/memory framework) into a single system with one engine, one config, one memory store, and no duplication.

---

## 1. RunEngine (`tradingagents/engine.py`)

Single orchestration class replacing the three separate entry points (`main.py`, `cli/main.py`, `webui/backend/runner.py`).

### API

```python
class RunEngine:
    def __init__(self, config_path: str = "trading-config.json"):
        """Load config, merge with schema defaults, validate."""

    def run(self, ticker: str, date: str, callbacks: list[RunCallback] = None) -> RunResult:
        """
        Full analysis pipeline:
        1. Check halt flag → abort if halted
        2. Hydrate BM25 from SQLite (5 memory stores)
        3. Build TradingAgentsGraph with config + callbacks
        4. propagate(ticker, date)
        5. process_signal() → BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
        6. Persist BM25 mutations to SQLite
        7. Append human-readable summary to memory/YYYY-MM-DD.md
        8. Return RunResult(signal, reports, debate_history, stats)
        """

    def reflect(self, ticker: str, date: str) -> ReflectionResult:
        """
        Post-session enhanced reflection:
        1. Fetch actual closing price (yfinance)
        2. Compare signal vs reality
        3. Feed comparison to LLM Reflector with outcome data
        4. Persist enriched memories to BM25 + SQLite
        5. Return ReflectionResult(outcome, lessons)
        """

    def halt(self):
        """Set halt flag in trading-config.json. Blocks all future runs."""

    def resume(self):
        """Clear halt flag. Requires explicit call (no auto-resume)."""

    @property
    def status(self) -> EngineStatus:
        """Return {state: running|idle|halted, last_run, watchlist, next_scheduled}."""
```

### RunResult

```python
@dataclass
class RunResult:
    ticker: str
    date: str
    signal: str                    # BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
    market_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str
    investment_debate: dict        # bull_history, bear_history, judge_decision
    risk_debate: dict              # aggressive/conservative/neutral history, judge_decision
    trader_plan: str
    final_decision: str
    duration_seconds: float
    token_stats: dict
```

### Callback Protocol

```python
class RunCallback(Protocol):
    def on_run_start(self, ticker: str, date: str): ...
    def on_agent_status(self, agent: str, status: str): ...
    def on_report_section(self, name: str, content: str): ...
    def on_debate_turn(self, speaker: str, argument: str): ...
    def on_signal(self, signal: str): ...
    def on_run_complete(self, result: RunResult): ...
    def on_error(self, error: Exception): ...
```

Frontend implementations:
- `RichCallback` — updates Rich TUI panels (CLI)
- `WebSocketCallback` — pushes events to WebSocket clients (WebUI)
- `FileMemoryCallback` — writes summaries to markdown files (OpenClaw)
- `StatsCallback` — tracks token/tool usage (all frontends)
- `CancelCallback` — checks cancel event, raises on cancellation (WebUI)

### What It Replaces

| Before | After |
|--------|-------|
| `cli/main.py` lines 400-900 (config building, graph streaming, Rich display) | `RunEngine.run()` + `RichCallback` |
| `webui/backend/runner.py` `_execute_run()` (config building, threading, WS events) | `RunEngine.run()` + `WebSocketCallback` |
| `main.py` (config override, propagate, reflect) | `RunEngine.run()` + `RunEngine.reflect()` |

---

## 2. Config (`trading-config.json`)

Single JSON file replacing `default_config.py` dict, `jadecap_config.py` module globals + `apply_settings()`, and WebUI SQLite `settings` table.

### Schema

```json
{
  "strategy": "default",
  "watchlist": ["NVDA", "AAPL"],

  "llm": {
    "provider": "openai",
    "deep_think_model": "gpt-4o",
    "quick_think_model": "gpt-4o-mini",
    "thinking_level": "low",
    "temperature": 0
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
    "max_consecutive_losses": 3
  },

  "jadecap": {
    "active_instrument": "NQ",
    "prop_firm": "apex",
    "hard_close_time": "15:45",
    "sessions": {},
    "kill_zones": {},
    "entry_models": {}
  },

  "halt": false,

  "schedule": {
    "pre_session_analysis": true,
    "monitor_interval_min": 30,
    "post_session_reflect": true,
    "market_open": "09:30",
    "market_close": "16:00",
    "timezone": "US/Eastern"
  },

  "paths": {
    "database": "trading.db",
    "memory_dir": "memory",
    "results_dir": "results"
  }
}
```

### Config Loading

```python
def load_config(path: str = "trading-config.json") -> dict:
    """Load JSON config, merge with SCHEMA_DEFAULTS, validate required fields."""
    with open(path) as f:
        user_config = json.load(f)
    config = deep_merge(SCHEMA_DEFAULTS, user_config)
    validate_config(config)  # check required fields, valid model names, etc.
    return config
```

`SCHEMA_DEFAULTS` is the hardcoded Python dict (what `default_config.py` is today) providing defaults for every field. User's JSON overrides only what they specify.

### What It Replaces

| Before | After |
|--------|-------|
| `default_config.py` `DEFAULT_CONFIG` dict | `SCHEMA_DEFAULTS` in `engine.py` (same data, just defaults) |
| `jadecap_config.py` module globals + `apply_settings()` | `config["jadecap"]` section in JSON |
| WebUI `settings` table read/write | JSON file read/write |
| CLI `get_user_selections()` building config from prompts | CLI overrides JSON fields via command-line args |

---

## 3. Agent Consolidation

### Strategy Registry

A single registry maps strategy names to prompt templates, tool sets, and memory assignments.

```python
# tradingagents/strategies/__init__.py

STRATEGY_REGISTRY = {
    "default": {
        "prompts": {
            "market_analyst": DEFAULT_MARKET_PROMPT,
            "bull_researcher": DEFAULT_BULL_PROMPT,
            # ...
        },
        "tools": {
            "market": [get_stock_data, get_indicators],
            "news": [get_news, get_global_news, get_insider_transactions],
            "fundamentals": [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement],
            "social": [get_news],
        },
        "memory_map": {
            "market": None,
            "bull": "bull_memory",
            "bear": "bear_memory",
            "trader": "trader_memory",
            "judge": "invest_judge_memory",
            "portfolio": "portfolio_manager_memory",
        },
        "analysts": ["market", "social", "news", "fundamentals"],
    },
    "jadecap": {
        "prompts": {
            "market_analyst": JADECAP_MARKET_PROMPT,
            "bull_researcher": JADECAP_BULL_PROMPT,
            # ...
        },
        "tools": {
            "market": ICT_TOOLS,
            "news": [get_news, get_global_news],
        },
        "memory_map": {
            "market": "invest_judge_memory",
            "bull": "bull_memory",
            "bear": "bear_memory",
            "trader": "trader_memory",
            "judge": "invest_judge_memory",
            "portfolio": "portfolio_manager_memory",
        },
        "analysts": ["market", "news"],
    },
}
```

### Unified Agent Files

Each agent file has one factory function that reads from the registry:

```python
# tradingagents/agents/analysts/market_analyst.py (merged)

def create_market_analyst(llm, config, memories):
    strategy = config["strategy"]
    reg = STRATEGY_REGISTRY[strategy]

    prompt = reg["prompts"]["market_analyst"]
    tools = reg["tools"]["market"]
    memory_key = reg["memory_map"]["market"]
    memory = memories[memory_key] if memory_key else None

    # Build the agent with prompt, tools, memory
    return create_react_agent(llm, tools, build_prompt(prompt, config, memory))
```

### Files After Consolidation

| Before (23 files) | After (8 files) |
|--------------------|-----------------|
| `market_analyst.py` + `market_analyst_jadecap.py` | `market_analyst.py` |
| `news_analyst.py` + `news_analyst_jadecap.py` | `news_analyst.py` |
| `bull_researcher.py` + `bull_researcher_jadecap.py` | `bull_researcher.py` |
| `bear_researcher.py` + `bear_researcher_jadecap.py` | `bear_researcher.py` |
| `research_manager.py` + `research_manager_jadecap.py` | `research_manager.py` |
| `portfolio_manager.py` + `portfolio_manager_jadecap.py` | `portfolio_manager.py` |
| `aggressive_debator.py` + `aggressive_debator_jadecap.py` | `aggressive_debator.py` |
| `conservative_debator.py` + `conservative_debator_jadecap.py` | `conservative_debator.py` |
| `neutral_debator.py` + `neutral_debator_jadecap.py` | `neutral_debator.py` |
| `trader.py` + `trader_jadecap.py` | `trader.py` |
| `fundamentals_analyst.py` | `fundamentals_analyst.py` |
| `social_media_analyst.py` | `social_media_analyst.py` |

Plus: `tradingagents/strategies/__init__.py` (the registry), `tradingagents/strategies/default.py` (default prompts), `tradingagents/strategies/jadecap.py` (jadecap prompts).

Adding a new strategy = add a new entry to `STRATEGY_REGISTRY` + a new prompts file. No new agent files.

---

## 4. Unified Memory

### Single Database (`trading.db`)

Merges WebUI's existing `database.py` schema with BM25 persistence:

```sql
-- Existing WebUI tables (unchanged)
CREATE TABLE runs (id, ticker, date, strategy, status, signal, duration, ...);
CREATE TABLE reports (id, run_id, section, content);
CREATE TABLE debates (id, run_id, type, speaker, content, round);

-- BM25 persistence (shared by all frontends)
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    store TEXT NOT NULL,           -- 'bull'|'bear'|'trader'|'judge'|'portfolio'
    situation TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NEW: outcome tracking for post-session learning
CREATE TABLE outcomes (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    signal TEXT NOT NULL,          -- what we predicted
    actual_close REAL,            -- what actually happened
    actual_change_pct REAL,
    correct BOOLEAN,              -- signal aligned with price movement?
    reflection TEXT,              -- LLM reflection with outcome data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Sync Timing

```
run_start:
  SQLite memories → BM25 in-memory (hydrate 5 stores)

during_run:
  BM25 queried by agents (bull/bear/trader/judge/PM)

reflect():
  New lessons added to BM25 in-memory
  BM25 → SQLite (persist immediately, continuous sync)

run_complete:
  RunResult → SQLite runs/reports/debates tables
  Summary → memory/YYYY-MM-DD.md (human-readable for OpenClaw)

post_session reflect():
  Actual price → SQLite outcomes table
  Enhanced reflection → BM25 + SQLite memories
  Key lessons → MEMORY.md (curated by heartbeat or manually)
```

---

## 5. Heartbeat Day-Cycle

### Phase 1: Pre-Session (before market open)

```
Trigger: heartbeat poll during pre-market hours (configurable, e.g., 8:00 AM ET)
Actions:
  1. Check halt flag → skip if halted
  2. For each ticker in config["watchlist"]:
     a. RunEngine.run(ticker, today's date)
     b. Record signal in daily markdown
  3. Update heartbeat-state.json: { lastPreSession: timestamp }
Output: "Pre-session analysis complete. Signals: NVDA=BUY, AAPL=HOLD"
```

### Phase 2: During Session (market hours, every ~30 min)

```
Trigger: heartbeat poll during market hours
Actions:
  1. For each ticker with today's signal:
     a. Fetch current price (yfinance, no LLM)
     b. Compare to morning prediction
     c. Append price update to memory/YYYY-MM-DD.md
  2. Check data provider health
  3. Update heartbeat-state.json: { lastMonitor: timestamp }
Output: "NVDA: BUY signal, now +1.8%. AAPL: HOLD signal, flat." or HEARTBEAT_OK
```

### Phase 3: Post-Session (after market close)

```
Trigger: heartbeat poll after market close (configurable, e.g., 4:30 PM ET)
Actions:
  1. For each ticker analyzed today:
     a. RunEngine.reflect(ticker, today's date)
        - Fetches actual close
        - Compares signal vs reality
        - LLM reflection with outcome data
        - Persists enriched memory
  2. Write daily summary to memory/YYYY-MM-DD.md
  3. Curate key lessons into MEMORY.md (if enough new data)
  4. Update heartbeat-state.json: { lastPostSession: timestamp }
Output: "Post-session: NVDA BUY was correct (+2.1%). AAPL HOLD correct (flat). Lessons stored."
```

### heartbeat-state.json

```json
{
  "lastPreSession": "2026-03-27T08:15:00",
  "lastMonitor": "2026-03-27T14:30:00",
  "lastPostSession": "2026-03-27T16:35:00",
  "todaySignals": {
    "NVDA": { "signal": "BUY", "entry_price": 142.50 },
    "AAPL": { "signal": "HOLD", "entry_price": 198.20 }
  }
}
```

---

## 6. OpenClaw File Updates

### TOOLS.md

```markdown
## Trading

Config: `trading-config.json`
Database: `trading.db`
Results: `memory/YYYY-MM-DD.md`

### Commands
- `python -m openclaw.engine run <ticker> [date]` — full analysis
- `python -m openclaw.engine status` — current state
- `python -m openclaw.engine halt` / `resume` — control analysis
- `python -m openclaw.engine reflect <ticker> [date]` — post-session learning

### Watchlist
Configured in trading-config.json. Current: NVDA, AAPL

### Strategies
- default: stock analysis (market, social, news, fundamentals analysts)
- jadecap: ICT futures analysis (market + news analysts, 23 ICT indicators)

New strategies: add entry to STRATEGY_REGISTRY in tradingagents/strategies/
```

### HEARTBEAT.md

```markdown
## Trading Day-Cycle

### Pre-Session (before market open)
- [ ] Run full analysis for watchlist tickers
- [ ] Record signals in daily memory

### During Session (every ~30 min)
- [ ] Monitor price movement vs predictions
- [ ] Check data provider health

### Post-Session (after market close)
- [ ] Fetch actual closing prices
- [ ] Compare predictions vs reality
- [ ] Run enhanced reflection with outcomes
- [ ] Curate lessons into MEMORY.md
```

### AGENTS.md Addition

```markdown
## Trading Agent

Role: Multi-agent market analysis. Produces BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL signals through a 4-tier pipeline (analysts → debate → risk assessment → final decision).

**This is analysis only — no order execution, no positions, no broker connection.**

Authority: Can run analysis autonomously during market hours (if heartbeat enabled). Cannot spend money. Cannot place orders.

Config: trading-config.json
```

### SOUL.md Addition

```markdown
## Trading Principles

- Analysis is probabilistic. No signal is certain.
- Learn from every outcome — right or wrong.
- When uncertain, HOLD is the correct signal.
- Risk parameters in config are non-negotiable.
- Transparency: always explain reasoning, never hide uncertainty.
```

### .gitignore Additions

```
MEMORY.md
memory/
trading.db
.claude/agent-memory/
.openclaw/
heartbeat-state.json
```

---

## 7. trading-integrator.md Rewrite

Complete rewrite of `.claude/agents/trading-integrator.md` to:
- Remove all fictional execution concepts (orders, positions, kill switch, exchanges, balance)
- Add real `TradingAgentsGraph` API knowledge (constructor, `propagate()`, `reflect_and_remember()`, `process_signal()`)
- Reference `trading-config.json` structure
- Describe the 4-tier pipeline and strategy registry
- Replace hardcoded `/home/hoang/.openclaw/workspace/` paths with relative paths

---

## 8. Critical Bug Fixes (pre-requisites)

These must be fixed before integration as they affect the merged system:

| Bug | File | Fix |
|-----|------|-----|
| Vendor fallback only catches `AlphaVantageRateLimitError` | `dataflows/interface.py` | Catch network/auth errors for fallback |
| ICT indicator KeyError (Title-Case columns) | `dataflows/ict_indicators.py` | Add `_to_smc_format()` to 3 functions |
| `daily_loss_limit` always equals `max_loss_per_trade` | `jadecap_config.py` | Accept separate key (now in JSON config) |
| `apply_settings()` prompt injection | `jadecap_config.py` | Validate/sanitize (simpler with JSON schema) |
| `python-dotenv` undeclared dependency | `pyproject.toml` | Add to dependencies |
| Non-existent model IDs as defaults | `default_config.py` → `SCHEMA_DEFAULTS` | Change to `gpt-4o` / `gpt-4o-mini` |
| Module globals mutation | `jadecap_config.py` | Eliminated — config is per-run from JSON |
| WebUI `PUT /api/keys` no allowlist | `webui/backend/routes/config.py` | Allowlist key names |

---

## 9. Execution Order

1. **Fix critical bugs** — foundation must be solid
2. **Create `trading-config.json`** + config loader with schema defaults
3. **Build strategy registry** (`tradingagents/strategies/`)
4. **Consolidate agent files** (15 → 8, using registry)
5. **Build RunEngine** (`tradingagents/engine.py`) with callback protocol
6. **Build memory layer** (unified SQLite + BM25 hydration)
7. **Build outcome tracking** (post-session reflect with actual prices)
8. **Migrate frontends** (CLI, WebUI, main.py → use RunEngine)
9. **OpenClaw integration** (update TOOLS.md, HEARTBEAT.md, AGENTS.md, SOUL.md, .gitignore)
10. **Rewrite trading-integrator.md**
11. **Tests** (config round-trip, memory round-trip, heartbeat cycle, full pipeline)
