# CLAUDE.md — OpenClaw Workspace

## What This Is

**OpenClaw** is the main project — a self-evolving AI agent framework with an integrated trading analysis pipeline. It gives AI assistants persistent identity, memory, personality, and behavioral protocols across sessions. The agent wakes up fresh each time and uses these files as its continuity.

## OpenClaw Framework Files

| File | Purpose |
|------|---------|
| `SOUL.md` | Core personality & behavior rules — the agent's character |
| `IDENTITY.md` | Name, creature type, vibe, emoji, avatar |
| `USER.md` | Profile of the human being helped |
| `AGENTS.md` | Session startup protocol, memory system, heartbeats, group chat rules, red lines |
| `TOOLS.md` | Local environment notes (cameras, SSH, TTS, device names) |
| `HEARTBEAT.md` | Periodic task checklist for proactive background work |
| `TRADING.md` | Trading control panel — bias, watchlist, strategy, risk, status |
| `MEMORY.md` | Curated long-term memory (main session only) |
| `.openclaw/` | Internal state (workspace-state.json) |

## Key Concepts

- **Session startup**: Read SOUL.md → USER.md → recent memory files → MEMORY.md (main session only)
- **Memory system**: Daily notes in `memory/YYYY-MM-DD.md` (raw logs), curated long-term in `MEMORY.md`
- **Heartbeats**: Periodic polls where agent can check email, calendar, weather, do background maintenance
- **MEMORY.md security**: Only loaded in direct (main) sessions, never in shared/group contexts
- **Boundaries**: No data exfiltration, `trash` over `rm`, ask before external actions
- **Identity evolution**: Agent fills in IDENTITY.md during first conversation, evolves SOUL.md over time

## TradingAgents Merge (COMPLETE)

The `TradingAgents/` directory has been fully merged into `openclaw/` and deleted. All trading functionality now lives in the `openclaw/` Python package.

**Full plan:** `docs/superpowers/plans/2026-03-27-openclaw-tradingagents-merge.md`
**Tag:** `v0.1.0-merge`

### Architecture

- **Full subagent architecture.** No LangGraph, no LangChain. Zero langchain/langgraph dependencies.
- Each of the 12 trading agents is a **subdirectory** in `agents/trading/{name}/` with 9 OpenClaw files (SOUL.md, IDENTITY.md, USER.md, AGENTS.md, TOOLS.md, HEARTBEAT.md, TRADING.md, MEMORY.md, PROMPT.md). Each agent gets the full OpenClaw context plus role-specific additions.
- **`dispatch_fn(agent_name, prompt, model) -> str`** is the critical hook. The RunEngine orchestrates the pipeline but does NOT call LLMs directly. The caller provides their own AI dispatch mechanism.
- **`dispatch_parallel_fn`** for Tier 1 analysts (4 at once). Everything else is sequential — pipeline order enforced.
- All tool functions are plain Python (no `@tool` decorators), merged into `openclaw/tools/__init__.py`.

### Pipeline

```
Tier 1: 4 Analysts → PARALLEL (market, social, news, fundamentals)
Tier 2: Bull/Bear Debate → SEQUENTIAL (N rounds, each counters the prior)
Tier 3: Research Manager → Trader → Risk Debate (aggressive → conservative → neutral) → SEQUENTIAL
Tier 4: Portfolio Manager → FINAL SIGNAL (BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL)
```

### Config

- **Schema defaults** in `openclaw/config.py` — auto-loads `trading-config.json` on first access if present
- **Per-agent model:** `llm.per_agent.bull-researcher: "claude-sonnet-4-6"` overrides the default model for that agent
- **Strategies:** `"default"` (stocks, 4 analysts) or `"jadecap"` (ICT futures, 2 analysts, 23 indicators)
- **JadeCap config:** `openclaw/jadecap_config.py` — full ICT strategy definitions, indicators, playbooks

### Market Hours

- All timestamps use **server UTC** — no local machine dependency
- Stocks: 9:30 AM - 4:00 PM ET
- Futures: 6:00 PM - 5:00 PM ET (nearly 24h, Sunday open to Friday close)
- Config `market_hours.use: "auto"` picks based on strategy (default=stock, jadecap=futures)
- User is in Houston (US/Central) — display converts, logic stays ET

### Memory

- **BM25** (`openclaw/memory.py`) for runtime retrieval — **12 stores** (one per agent)
- **SQLite** (`trading.db`) for persistence — memories survive restarts
- **Per-agent MEMORY.md** — each agent subdirectory has its own `MEMORY.md` with role-specific lessons
- **Outcome tracking** — post-run: fetch actual close price, compare to signal, store reflection, write lessons
- **No lost work** — partial state saved to SQLite after each pipeline tier completes

### Error Handling

- Each tier wrapped in try/except — completed work saved before failure propagates
- Dispatch timeout: 5 min default per agent (configurable). Uses `concurrent.futures.ThreadPoolExecutor`.
- If agent hangs → `TimeoutError` → partial state saved → run marked "partial" → dashboard shows completed reports

### Concurrent Runs

- Two analyses CAN overlap (e.g., NVDA + AAPL). Each `run()` call gets own UUID, own state, own BM25 copy.
- SQLite WAL mode for concurrent writes.
- `halt()` blocks NEW runs, does not kill running ones.

### File Structure

```
TRADING.md                ← Trading control panel (bias, watchlist, status)
openclaw/                 ← THE Python package (everything)
├── engine.py             ← RunEngine (dispatch_fn hook)
├── config.py             ← Config loader + SCHEMA_DEFAULTS (auto-loads trading-config.json)
├── indicators.py         ← Unified indicator interface (stockstats + smartmoneyconcepts)
├── jadecap_config.py     ← Full JadeCap/ICT strategy configuration
├── memory.py             ← BM25 financial situation memory (12 stores)
├── memory_persistence.py ← BM25 ↔ SQLite sync
├── database.py           ← SQLite schema (runs, reports, debates, memories, outcomes)
├── agent_states.py       ← Agent state management during pipeline runs
├── run_bridge.py         ← Bridge between RunEngine and Claude Code dispatch
├── heartbeat.py          ← Market phase detection
├── callbacks.py          ← RunCallback protocol (Print, Collector, FileMemory)
├── dataflows/            ← Data vendor integrations (yfinance, Alpha Vantage, Databento)
└── tools/                ← Plain Python tool functions (merged into __init__.py)

agents/trading/           ← 12 subagent directories, each with 9 OpenClaw files
├── market-analyst/       ← SOUL.md, IDENTITY.md, USER.md, AGENTS.md, TOOLS.md,
├── social-analyst/          HEARTBEAT.md, TRADING.md, MEMORY.md, PROMPT.md
├── news-analyst/
├── fundamentals-analyst/
├── bull-researcher/
├── bear-researcher/
├── research-manager/
├── trader/
├── aggressive-risk/
├── conservative-risk/
├── neutral-risk/
└── portfolio-manager/

dashboard/terminal/       ← Rich terminal monitor + analysis viewer
```

### Key Dependencies

Core: `pandas`, `yfinance`, `stockstats`, `rank-bm25`, `requests`, `rich`, `python-dotenv`
Optional ICT: `smartmoneyconcepts`, `databento`
Optional web: `websockets`
Dev: `pytest`
**ZERO langchain/langgraph**

### Data Flow

- **OHLCV data**: yfinance for all timeframes (fast); Databento for live price only
- **Indicators**: stockstats for standard TA; smartmoneyconcepts for ICT (FVG, OB, BOS, etc.)
- **News/social**: Alpha Vantage news API + Brave Search pre-fetch for news + social agents
- **Fundamentals**: Alpha Vantage fundamentals API

### Gotchas for Future Sessions

- `dataflows/config.py` has a thread-safe singleton (`get_config()`/`set_config()`) — RunEngine must call `set_config()` at start of `run()` to bridge new config into old dataflow code
- `dataflows/interface.py` `route_to_vendor()` has a fallback chain — catches ALL exceptions
- JadeCap prompts use runtime variables (`{bull_req}`, `{hard_rules_str}`, `{kz_str}`, etc.) — RunEngine injects these from jadecap config section
- Agent subdirectories have 9 files each — core files are strategy-neutral, strategy details live in PROMPT.md only
- User bias score is capped at ±2 — pre-session gut feel shouldn't dominate
- Confluence strength thresholds: ±2 is moderate (not weak)
- Databento OHLCV uses 12s prefetch; live price uses Databento Live API
- Smart dispatch routing: only news + social agents use Brave web search tools
- Parallel tool prefetch runs at pipeline start for all data-gathering tools

---

## Key Rules

- OpenClaw files are the agent's persistent self — update carefully, tell the user if changing SOUL.md
- Write things down — "mental notes" don't survive session restarts, files do
- Private things stay private. Period.
- Be helpful without being annoying — quality over quantity in interactions
