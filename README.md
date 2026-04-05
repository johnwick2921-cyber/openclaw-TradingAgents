# OpenClaw

Self-evolving AI agent framework with integrated trading analysis module.

## Architecture

```
OpenClaw Control UI (port 18789)
  |
  v
OpenClaw Gateway (TypeScript, WebSocket RPC)
  |
  v
9router (port 20128) ── AI request router (40+ providers, fallback chains)
  |
  v
AI Providers (Claude, GPT, Gemini, DeepSeek, etc.)
```

OpenClaw is the **brain** — all AI dispatch, auth, model routing, and session management go through its gateway. 9router handles multi-provider routing and failover.

## 12 Registered Agents

| Agent | Role | Tier |
|-------|------|------|
| `main` | General-purpose OpenClaw agent | - |
| `trading-monitor` | Orchestrates trading analysis | - |
| `market-analyst` | Technical analysis, price action, ICT levels | T1 |
| `news-analyst` | News analysis, macro bias | T1 |
| `bull-researcher` | Bullish case with BM25 memory | T2 |
| `bear-researcher` | Bearish case with BM25 memory | T2 |
| `research-manager` | Judges debate, creates investment plan | T3 (deep) |
| `trader` | Sizes the trade, entry/exit levels | T3 |
| `aggressive-risk` | Aggressive risk perspective | T3 |
| `conservative-risk` | Conservative risk perspective | T3 |
| `neutral-risk` | Balanced risk perspective | T3 |
| `portfolio-manager` | Final BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL | T4 (deep) |

## Trading Pipeline

Analysis-only — no order execution, no broker connection.

```
Tier 1: Analysts (parallel)     → market, news reports
Tier 2: Bull/Bear Debate        → N rounds of argument/counter-argument
Tier 3: Judge + Trader + Risk   → investment plan, trade sizing, risk assessment
Tier 4: Portfolio Manager       → final signal (BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL)
```

After each run:
- **Auto-bias update**: signal updates the agent bias in config
- **Confluence scoring**: user bias vs agent bias → -6 to +6 score (ALIGNED / CONFLICT)
- **Memory persistence**: BM25 memories saved to SQLite for future runs

## Strategies

| Strategy | Instruments | Analysts | Indicators |
|----------|------------|----------|------------|
| `stocks` | NVDA, AAPL, etc. | market, social, news, fundamentals | 13 stockstats (RSI, MACD, Bollinger, etc.) |
| `jadecap` | NQ, ES futures | market, news | 17 ICT (FVG, order blocks, market structure, etc.) |

## Quick Start

### 1. Install dependencies

```bash
pip install -e .                    # core
pip install -e '.[ict]'             # + ICT/JadeCap indicators
npm install -g 9router              # AI router
```

### 2. Start services

```bash
9router --tray --no-browser         # AI router on port 20128
systemctl --user start openclaw-gateway  # OpenClaw on port 18789
```

### 3. Configure

- **9router dashboard**: http://localhost:20128 — add AI providers (Claude Code OAuth, API keys, etc.)
- **OpenClaw Control UI**: http://localhost:18789 — Trading tab for all controls

### 4. Run analysis

**From the UI**: Trading tab → enter ticker + date → click Analyze

**From Python**:
```python
from openclaw.engine import RunEngine
from openclaw.run_bridge import openclaw_dispatch, openclaw_dispatch_parallel

engine = RunEngine("trading-config.json")
result = engine.run(
    "NVDA", "2026-03-31",
    dispatch_fn=openclaw_dispatch,
    dispatch_parallel_fn=openclaw_dispatch_parallel,
)
print(result.signal)  # BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL
```

## Control UI Features

All at http://localhost:18789 → Trading tab:

- **Trading Engine** — halt/resume, strategy switch (stocks/jadecap)
- **Run Analysis** — ticker + date input, live 12-agent progress monitor
- **Bias Confluence** — user bias (editable) + agent bias (auto from last run) + confluence score
- **Run History** — paginated table with View/Reflect/Delete per run
- **Run Detail** — tabbed: reports, debates, outcome
- **Watchlist** — add/remove tickers with signal tracking
- **Pipeline Config** — toggle analysts, debate rounds, risk rounds, timeout
- **Risk Parameters** — editable (max loss, daily limit, drawdown, consecutive losses, risk/reward)
- **LLM Config** — model dropdowns pulling live from 9router
- **JadeCap Settings** — instrument, prop firm, hard close time, ATR stop, T1 close %
- **Memory Stats** — agent memory counts

## Config

Single source of truth: `trading-config.json`

```json
{
  "strategy": "jadecap",
  "llm": {
    "default": "cc/claude-sonnet-4-6",
    "deep_think": "cc/claude-opus-4-6",
    "quick_think": "cc/claude-sonnet-4-6",
    "per_agent": {}
  },
  "analysis": {
    "analysts": ["market", "news"],
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1
  },
  "risk": {
    "max_loss_per_trade": 500,
    "daily_loss_limit": 1000,
    "max_drawdown_pct": 5
  }
}
```

## File Structure

```
workspace/
├── SOUL.md, AGENTS.md, HEARTBEAT.md, TOOLS.md   ← OpenClaw framework (trading-aware)
├── TRADING.md                                     ← Trading control panel
├── trading-config.json                            ← Single config source
├── trading.db                                     ← SQLite (runs, reports, debates, memories, outcomes)
├── .env                                           ← 9router API key
├── agents/trading/                                ← 12 agent .md definitions
├── openclaw/                                      ← Python package
│   ├── engine.py                                  ← RunEngine orchestrator
│   ├── run_bridge.py                              ← Subprocess entry point (gateway dispatch)
│   ├── config.py                                  ← Config loader + schema defaults
│   ├── database.py                                ← SQLite schema
│   ├── indicators.py                              ← Unified indicators (stockstats + SMC)
│   ├── tool_registry.py                           ← Dynamic tool registry
│   ├── memory.py                                  ← BM25 financial memory
│   ├── memory_persistence.py                      ← BM25 ↔ SQLite sync
│   ├── callbacks.py                               ← RunCallback protocol
│   ├── heartbeat.py                               ← Market phase detection
│   ├── jadecap_config.py                          ← JadeCap runtime constants
│   ├── dataflows/                                 ← Data vendor integrations
│   └── tools/                                     ← Tool functions (auto-registered)
└── dashboard/terminal/                            ← Rich terminal monitor
```

## Dispatch Flow

```
UI "Analyze" button
  → Gateway trading.run handler (TypeScript)
    → spawns: python3 -m openclaw.run_bridge --ticker NVDA --date 2026-03-31
      → RunEngine.run(dispatch_fn=openclaw_dispatch)
        → For each of 12 agents:
          → POST http://127.0.0.1:18789/v1/chat/completions (OpenClaw gateway)
            → OpenClaw routes via 9router provider config
              → 9router routes to AI provider (Claude Code, etc.)
            → AI response returned
        → Signal extracted → bias updated → confluence scored → saved to DB
      → Progress events broadcast to UI via WebSocket
```

## License

MIT
