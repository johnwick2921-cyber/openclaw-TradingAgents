---
name: trading
description: "Use this skill for ANY trading-related request — running analysis, fetching indicators, checking market data, managing trading config, setting bias, updating watchlist, viewing run history, or controlling the trading pipeline. Trigger when user mentions: analyze, indicators, RSI, MACD, FVG, order blocks, ICT, bias, watchlist, risk parameters, trading config, run history, confluence, signal, NQ, ES, futures, stocks, market analysis, kill zones, or any ticker symbol with trading intent. Also trigger for 'what does the market look like', 'should I trade', 'show me NQ levels', 'set bias bullish', 'add NVDA to watchlist', 'change model to opus', 'halt trading', 'reflect on last run', or similar."
---

# Trading Skill

You have access to OpenClaw's full trading system — 12 AI agents, 15 data tools, 30+ indicators, and complete pipeline control. Everything routes through OpenClaw gateway (18789) → 9router (20128) → AI.

## Quick Reference

| Command | What it does |
|---------|-------------|
| "analyze NQ" | Run full 10-agent pipeline for NQ futures |
| "get RSI MACD for NVDA" | Fetch specific indicators |
| "show FVG and order blocks for NQ" | ICT indicator lookup |
| "set bias bullish high — displacement above midnight" | Set your pre-session bias |
| "add NVDA to watchlist" | Watchlist management |
| "set risk max loss 750" | Update risk parameters |
| "change model to cc/claude-opus-4-6" | Switch LLM model |
| "halt trading" / "resume" | Emergency stop |
| "show last run" / "run history" | View past analyses |
| "reflect on NQ 2026-03-31" | Compare signal vs actual outcome |
| "what's the confluence?" | Show user bias vs agent bias alignment |

## How to Execute

### 1. Run Full Analysis

```python
import subprocess, json

# Spawn via gateway (preferred — goes through OpenClaw)
# Or call directly:
result = subprocess.run([
    "python3", "-m", "openclaw.run_bridge",
    "--ticker", "NQ",
    "--date", "2026-03-31",
    "--progress-file", "/tmp/trading-run.jsonl",
    "--config", "/home/hoang/.openclaw/workspace/trading-config.json"
], cwd="/home/hoang/.openclaw/workspace",
   env={**dict(__import__('os').environ), "PYTHONPATH": "/home/hoang/.openclaw/workspace"},
   capture_output=True, text=True, timeout=900)

output = json.loads(result.stdout.strip().split('\n')[-1])
# output = {"ok": true, "run_id": "abc123", "signal": "BUY", "duration": 142.3}
```

The run dispatches 10 agents through OpenClaw → 9router → Claude. Takes 8-15 minutes depending on model speed.

### 2. Fetch Indicators (No AI needed)

```python
# Stock indicators (stockstats)
from openclaw.indicators import get_indicator, get_indicators_batch
data = get_indicator("NVDA", "rsi_14")     # single
batch = get_indicators_batch("NVDA", ["rsi_14", "macd", "boll_ub", "boll_lb", "close_20_sma"])

# ICT indicators (smartmoneyconcepts)
ict = get_indicator("NQ=F", "fvg")          # Fair Value Gaps
obs = get_indicator("NQ=F", "ob")           # Order Blocks
bos = get_indicator("NQ=F", "bos")          # Break of Structure
choch = get_indicator("NQ=F", "choch")      # Change of Character
liq = get_indicator("NQ=F", "liquidity")    # Liquidity levels
```

**Available stockstats (13):** rsi, macd, macdh, macds, boll, boll_ub, boll_lb, close_5_sma, close_20_sma, close_50_sma, close_5_ema, close_20_ema, atr

**Available ICT/SMC (17):** fvg, ob, bos, choch, liquidity, swing_highs_lows, premium_discount, session_highs_lows, retracements, displacement, market_structure, order_flow, breaker_blocks, mitigation_blocks, equal_highs_lows, previous_day_levels, volume_profile

### 3. Fetch Market Data (No AI needed)

```python
from openclaw.tool_registry import registry
import openclaw.tools  # auto-registers all 15 tools

# Stock data
data = registry.call("get_stock_data", "NVDA", "2026-03-31", {})

# Live price
price = registry.call("fetch_live_price", "NQ=F", "", {})

# Fundamentals
fund = registry.call("get_fundamentals", "NVDA", "", {})
bs = registry.call("get_balance_sheet", "NVDA", "", {})
cf = registry.call("get_cashflow", "NVDA", "", {})
inc = registry.call("get_income_statement", "NVDA", "", {})

# News
news = registry.call("get_news", "NVDA", "", {})
global_news = registry.call("get_global_news", "", "", {})

# ICT-specific
kz = registry.call("get_killzone_status_tool", "", "", {})
midnight = registry.call("get_midnight_open_tool", "NQ=F", "", {})
contract = registry.call("get_contract_size", "NQ", "", {})
```

### 4. Config Management

Read and write `trading-config.json` directly:

```python
from openclaw.config import load_config, save_config

config = load_config("/home/hoang/.openclaw/workspace/trading-config.json")

# Set bias
config["bias"] = {"direction": "bullish", "confidence": "high", "reason": "NQ above midnight open"}

# Change model
config["llm"]["default"] = "cc/claude-opus-4-6"

# Update risk
config["risk"]["max_loss_per_trade"] = 750

# Toggle analysts
config["analysis"]["analysts"] = ["market", "news", "fundamentals"]

# Halt/resume
config["halt"] = True  # or False

# Save
save_config(config, "/home/hoang/.openclaw/workspace/trading-config.json")
```

### 5. View Run History

```python
from openclaw.database import get_db

with get_db("/home/hoang/.openclaw/workspace/trading.db") as conn:
    # Last 5 runs
    runs = conn.execute(
        "SELECT id, ticker, trade_date, signal, status, duration_seconds FROM runs ORDER BY created_at DESC LIMIT 5"
    ).fetchall()

    # Specific run details
    run_id = "a08f8483"
    reports = conn.execute("SELECT section_name, content FROM reports WHERE run_id = ?", (run_id,)).fetchall()
    debates = conn.execute("SELECT debate_type, full_history FROM debates WHERE run_id = ?", (run_id,)).fetchall()
```

### 6. Confluence Score

```python
from openclaw.engine import RunEngine

engine = RunEngine("/home/hoang/.openclaw/workspace/trading-config.json")

# Check current confluence
config = engine.config
user_bias = config.get("bias", {})
agent_bias = config.get("agent_bias", {})
confluence = config.get("confluence", {})

# Or compute fresh
score = engine._compute_confluence("BUY")  # against current user bias
# Returns: {total: 6, direction: "bullish", strength: "strong", aligned: True, conflicting: False}
```

### 7. Reflect on Past Run

```python
engine = RunEngine("/home/hoang/.openclaw/workspace/trading-config.json")
result = engine.reflect("NQ", "2026-03-31")
# Returns: {ticker, date, actual_close, signal, correct, actual_change_pct, reflection}
```

## File Locations

| File | Purpose |
|------|---------|
| `trading-config.json` | All config (strategy, LLM, risk, bias, watchlist) |
| `trading.db` | SQLite (runs, reports, debates, memories, outcomes) |
| `agents/trading/*.md` | 10 agent prompt definitions |
| `openclaw/engine.py` | RunEngine orchestrator |
| `openclaw/run_bridge.py` | Subprocess dispatch (OpenClaw → 9router → AI) |
| `openclaw/indicators.py` | Unified indicator interface |
| `openclaw/tool_registry.py` | Dynamic tool registry (15 tools) |
| `openclaw/config.py` | Config loader + schema defaults |
| `TRADING.md` | Human-readable control panel |

## Models (via 9router)

```
cc/claude-opus-4-6          (deep think — research-manager, portfolio-manager)
cc/claude-opus-4-5-20251101 (deep think alternate)
cc/claude-sonnet-4-6        (default — most agents)
cc/claude-sonnet-4-5-20250929
cc/claude-haiku-4-5-20251001 (fast/cheap)
```

## Important Rules

- **Analysis only** — no order execution, no broker, no positions
- All AI calls route through OpenClaw gateway (18789) → 9router (20128)
- Risk parameters in config are non-negotiable — the system enforces them
- When uncertain, HOLD is the correct signal
- Always update TRADING.md after config changes to keep it in sync
