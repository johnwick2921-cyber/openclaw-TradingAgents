# TOOLS.md - OpenClaw Tools & Environment

## Infrastructure

| Service | Port | Managed By |
|---------|------|-----------|
| OpenClaw Gateway | 18789 | systemctl --user (openclaw-gateway) |
| 9router AI Router | 20128 | systemctl --user (9router) |
| Control UI | 18789 | Same as gateway |

## Trading Module

Config: `trading-config.json`
Database: `trading.db`
Agent definitions: `agents/trading/*.md`
Daily memory: `memory/YYYY-MM-DD.md`

### Dispatch Flow

```
RunEngine → OpenClaw Gateway (18789) → 9router (20128) → AI Provider
```

### Pipeline

```
Tier 1: Analysts (parallel)     → market, social, news, fundamentals
Tier 2: Bull/Bear Debate        → N rounds
Tier 3: Judge + Trader + Risk   → research-manager → trader → 3 risk agents
Tier 4: Portfolio Manager       → BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
```

### Strategies

- **stocks**: 4 analysts, standard indicators (RSI, MACD, Bollinger, etc.)
- **jadecap**: 2 analysts (market + social/news), ICT indicators (FVG, order blocks, liquidity sweeps, etc.)

### 15 Registered Tools

Agents declare tools in frontmatter. RunEngine prefetches data before sending prompts.

| Tool | Description | Category |
|------|-------------|----------|
| `get_stock_data` | OHLCV price data via yfinance | data |
| `get_indicators` | 13 stockstats indicators (RSI, MACD, BB, SMA, EMA, etc.) | data |
| `get_ict_levels` | 17 ICT/SMC indicators (FVG, OB, BOS, CHoCH, liquidity, etc.) | data |
| `get_fundamentals` | Company fundamentals overview | data |
| `get_balance_sheet` | Balance sheet data | data |
| `get_cashflow` | Cash flow statement | data |
| `get_income_statement` | Income statement | data |
| `get_news` | Ticker-specific news | data |
| `get_global_news` | Macro/global market news | data |
| `get_insider_transactions` | Insider buying/selling | data |
| `fetch_live_price` | Current live price (Databento Live → Historical → yfinance fallback) | price |
| `get_live_price` | Current live price (alias for fetch_live_price) | price |
| `get_killzone_status_tool` | Current ICT kill zone status | jadecap |
| `get_contract_size` | Futures contract point value | jadecap |
| `get_midnight_open_tool` | Midnight open level for ICT analysis | jadecap |

### Indicator Coverage

**stockstats (13):** rsi, macd, macdh, macds, boll, boll_ub, boll_lb, close_5_sma, close_20_sma, close_50_sma, close_5_ema, close_20_ema, atr

**smartmoneyconcepts (17):** fvg, ob, bos, choch, liquidity, swing_highs_lows, premium_discount, session_highs_lows, retracements, displacement, market_structure, order_flow, breaker_blocks, mitigation_blocks, equal_highs_lows, previous_day_levels, volume_profile

### Gateway Handlers (16)

**Read:** `trading.status`, `trading.models`, `trading.runs`, `trading.run.get`
**Write:** `trading.setBias`, `trading.setHalt`, `trading.updateWatchlist`, `trading.setRisk`, `trading.setLlm`, `trading.setAnalysis`, `trading.setJadecap`, `trading.setStrategy`, `trading.run`, `trading.run.cancel`, `trading.run.delete`, `trading.run.reflect`

### Config Quick Reference

- Change strategy: UI Trading tab → strategy buttons or `trading-config.json` → `"strategy": "jadecap"`
- Set bias: UI bias panel or `trading-config.json` → `"bias.direction": "bullish"`
- Add to watchlist: UI watchlist panel or config → `"watchlist": ["NQ"]`
- Halt: UI halt button or `"halt": true`
- Change model: UI LLM Config dropdown or `"llm.default": "cc/claude-opus-4-6"`
- Per-agent model: `"llm.per_agent.market-analyst": "cc/claude-haiku-4-5-20251001"`

### Available Models (via 9router)

```
cc/claude-opus-4-6
cc/claude-opus-4-5-20251101
cc/claude-sonnet-4-6
cc/claude-sonnet-4-5-20250929
cc/claude-haiku-4-5-20251001
```

Add more providers in 9router dashboard at http://localhost:20128

## My Specific Tools
- **get_fundamentals** — company overview and key ratios
- **get_balance_sheet** — quarterly balance sheet
- **get_cashflow** — quarterly cash flow statement
- **get_income_statement** — quarterly income statement
