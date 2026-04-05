# CLAUDE.md — OpenClaw Workspace

## What This Is

**OpenClaw** is the main project — a self-evolving AI agent framework. It gives AI assistants persistent identity, memory, personality, and behavioral protocols across sessions. The agent wakes up fresh each time and uses these files as its continuity.

## OpenClaw Framework Files

| File | Purpose |
|------|---------|
| `SOUL.md` | Core personality & behavior rules — the agent's character |
| `IDENTITY.md` | Name, creature type, vibe, emoji, avatar |
| `USER.md` | Profile of the human being helped |
| `AGENTS.md` | Session startup protocol, memory system, heartbeats, group chat rules, red lines |
| `BOOTSTRAP.md` | First-run onboarding — deleted after initial setup |
| `TOOLS.md` | Local environment notes (cameras, SSH, TTS, device names) |
| `HEARTBEAT.md` | Periodic task checklist for proactive background work |
| `TRADING.md` | Trading control panel — bias, watchlist, strategy, risk, status |
| `.openclaw/` | Internal state (workspace-state.json) |

## Key Concepts

- **Session startup**: Read SOUL.md → USER.md → recent memory files → MEMORY.md (main session only)
- **Memory system**: Daily notes in `memory/YYYY-MM-DD.md` (raw logs), curated long-term in `MEMORY.md`
- **Heartbeats**: Periodic polls where agent can check email, calendar, weather, do background maintenance
- **MEMORY.md security**: Only loaded in direct (main) sessions, never in shared/group contexts
- **Boundaries**: No data exfiltration, `trash` over `rm`, ask before external actions
- **Identity evolution**: Agent fills in IDENTITY.md during first conversation, evolves SOUL.md over time

## Merge: TradingAgents → OpenClaw (COMPLETE)

**Full plan:** `docs/superpowers/plans/2026-03-27-openclaw-tradingagents-merge.md`
**Tag:** `v0.1.0-merge`

### Architecture Decisions (locked in)

- **OpenClaw is MAIN.** TradingAgents dissolves into `openclaw/` Python package. The `TradingAgents/` directory will be FULLY DELETED after merge.
- **Full subagent architecture.** No LangGraph. Each of the 12 trading agents becomes an AI-agnostic `.md` file in `agents/trading/`. Any AI can execute them.
- **Zero LangChain.** All `@tool` decorators removed from tool files. Plain Python functions. All langchain/langgraph dependencies deleted from pyproject.toml.
- **`dispatch_fn(agent_name, prompt, model) -> str`** is the critical hook. The RunEngine orchestrates the pipeline but does NOT call LLMs directly. The caller provides their own AI dispatch mechanism (Claude Code Agent tool, direct API, etc.).
- **`dispatch_parallel_fn`** for Tier 1 analysts (4 at once). Everything else is sequential — pipeline order enforced.

### Pipeline (preserved from original TradingAgents)

```
Tier 1: 4 Analysts → PARALLEL (market, social, news, fundamentals)
Tier 2: Bull/Bear Debate → SEQUENTIAL (N rounds, each counters the prior)
Tier 3: Research Manager → Trader → Risk Debate (aggressive → conservative → neutral) → SEQUENTIAL
Tier 4: Portfolio Manager → FINAL SIGNAL (BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL)
```

### Config

- **Single source:** `trading-config.json` (replaces default_config.py, jadecap_config.py, WebUI SQLite settings)
- **Schema defaults** in `openclaw/config.py` — user only specifies overrides
- **Per-agent model:** `llm.per_agent.bull-researcher: "claude-sonnet-4-6"` overrides the default model for that agent
- **Strategies:** `"default"` (stocks, 4 analysts) or `"jadecap"` (ICT futures, 2 analysts, 23 indicators)

### Market Hours

- All times in **exchange server time (US/Eastern)**, NOT machine local time
- Stocks: 9:30 AM - 4:00 PM ET
- Futures: 6:00 PM - 5:00 PM ET (nearly 24h, Sunday open to Friday close)
- Config `market_hours.use: "auto"` picks based on strategy (default=stock, jadecap=futures)
- User is in Houston (US/Central) — display converts, logic stays ET

### Memory

- **BM25** (`openclaw/memory.py`) for runtime retrieval — 5 stores (bull, bear, trader, judge, portfolio)
- **SQLite** (`trading.db`) for persistence — memories survive restarts
- **Markdown** (`memory/YYYY-MM-DD.md`) for OpenClaw session context — human-readable summaries
- **Outcome tracking** — post-session: fetch actual close price, compare to signal, store reflection
- **No lost work** — partial state saved to SQLite after each pipeline tier completes

### Error Handling

- Each tier wrapped in try/except — completed work saved before failure propagates
- Dispatch timeout: 5 min default per agent (configurable). Uses `concurrent.futures.ThreadPoolExecutor`.
- If agent hangs → `TimeoutError` → partial state saved → run marked "partial" → dashboard shows completed reports

### Concurrent Runs

- Two analyses CAN overlap (e.g., NVDA + AAPL). Each `run()` call gets own UUID, own state, own BM25 copy.
- SQLite WAL mode for concurrent writes.
- `halt()` blocks NEW runs, does not kill running ones.

### File Structure After Merge

```
TRADING.md             ← Trading control panel (bias, watchlist, status)
openclaw/              ← THE Python package (everything)
├── engine.py          ← RunEngine (dispatch_fn hook)
├── config.py          ← trading-config.json loader + SCHEMA_DEFAULTS
├── indicators.py      ← Unified indicator interface (stockstats + smartmoneyconcepts)
├── tool_registry.py   ← Dynamic tool registry (register/call by name)
├── memory.py          ← BM25 financial situation memory
├── database.py        ← SQLite schema (runs, reports, debates, memories, outcomes)
├── memory_persistence.py ← BM25 ↔ SQLite sync
├── heartbeat.py       ← market phase detection
├── callbacks.py       ← RunCallback protocol (Print, Collector, FileMemory)
├── dataflows/         ← data vendor integrations (15 files)
└── tools/             ← plain Python tool functions (5 files, auto-registered)

agents/trading/        ← 12 subagent .md definitions
dashboard/terminal/    ← Rich monitor + analysis viewer
dashboard/web/         ← React + FastAPI web dashboard
```

### Key Dependencies (after merge)

Core: `pandas`, `yfinance`, `stockstats`, `rank-bm25`, `requests`, `aiosqlite`, `rich`, `python-dotenv`
Optional (webui): `fastapi`, `uvicorn`, `websockets`, `smartmoneyconcepts`, `databento`
**ZERO langchain/langgraph**

### 9 Phases (see full plan for detail)

1. Bug fixes + @tool removal
2. Config system (trading-config.json)
3. Agent .md files (12 subagent definitions with verbatim prompts)
4. RunEngine (dispatch_fn, parallel Tier 1, debate loops, error recovery)
5. Memory + outcomes (SQLite, BM25 persistence, outcome tracking)
6. Dashboard (Rich terminal + React WebUI migration)
7. OpenClaw integration (TOOLS.md, HEARTBEAT.md, AGENTS.md, SOUL.md, trading-integrator.md)
8. Cleanup (move to openclaw/, delete TradingAgents/ entirely)
9. Full review + test (code-reviewer agent, regression, all tests pass)

Each phase has a **verification gate** — must pass before proceeding to next phase.

### Gotchas for Future Sessions

- `dataflows/config.py` has a thread-safe singleton (`get_config()`/`set_config()`) — RunEngine must call `set_config()` at start of `run()` to bridge new config into old dataflow code
- `dataflows/interface.py` `route_to_vendor()` has a fallback chain — catches ALL exceptions now (was only AlphaVantageRateLimitError)
- JadeCap prompts use runtime variables (`{bull_req}`, `{hard_rules_str}`, `{kz_str}`, etc.) — RunEngine must inject these from jadecap config section
- `fundamentals_analyst.py` has a bug: system_message is a tuple `(string,)` — extract the string when creating .md file
- Agent .md files have YAML frontmatter — `model: null` means use config default, set specific model ID to override
- `tier: deep` in frontmatter = use `llm.deep_think` model (research-manager, portfolio-manager)
- BOOTSTRAP.md still exists — merge doesn't trigger it, leave for OpenClaw lifecycle

---

## Subprojects

- **TradingAgents/** — **DEPRECATED. Being merged into OpenClaw.** See merge plan above. After merge, this directory will be deleted.

## Indicator Standards (ICT/JCAP)

- EMA: standard `ewm(adjust=True)` — NOT Wilder (`adjust=False`)
- ATR: Wilder exponential `ewm(alpha=1/period, adjust=False)` — NOT simple rolling mean
- ADX: Wilder smoothing — same as ATR
- SFP: minimum 3-point penetration past swing level on NQ
- When changing indicator calculations, update BOTH `backtest.py` AND `indicators.py` — they must compute identically

## Common Pitfalls

- Template vars in agent prompts: use `{KEY['subkey']}` bracket notation, NOT `.get()` — the resolver doesn't handle `.get()`
- After deleting agents: clean up config.py SCHEMA_DEFAULTS, engine.py memories dict, engine.py analyst_map, run_bridge.py, trading-integrator.md
- Engine `_get_ema200_context` must use `_fetch_ohlcv_df` directly — no `get_multi_tf_indicators` function exists
- Apex 2026 rules: $2K trailing DD (not $2.5K), 6-step payout ladder, 50% consistency rule
- Bulk fetch: use `_fetch_bulk` with 365-day lookback for proper indicator warmup (EMA 200 needs 200+ daily bars)
- Prop firm config: PROP_FIRMS in jadecap_config.py is source of truth, injected via `{firm_*}` template vars — never hardcode firm values in prompts

## Key Rules

- OpenClaw files are the agent's persistent self — update carefully, tell the user if changing SOUL.md
- BOOTSTRAP.md is meant to be deleted after first onboarding conversation
- Write things down — "mental notes" don't survive session restarts, files do
- Private things stay private. Period.
- Be helpful without being annoying — quality over quantity in interactions
