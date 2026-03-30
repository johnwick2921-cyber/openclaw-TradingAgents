# Trading Control Panel

> This file is the OpenClaw-native interface for trading configuration.
> The agent reads this on startup and can update it via the trading-integrator.
> Changes here sync to `trading-config.json` automatically.

## Status

- **State:** ACTIVE
- **Strategy:** jadecap
- **Halt:** false

## Market Bias

> Set your directional bias before each session. The agent uses this to weight analysis.

- **Daily Bias:** NEUTRAL
- **Bias Reason:** (none set)
- **Bias Confidence:** MEDIUM

Options: BULLISH | BEARISH | NEUTRAL

## Watchlist

| Ticker | Strategy | Last Signal | Date | Correct? |
|--------|----------|-------------|------|----------|
| _(empty — add tickers below)_ |

### Add/Remove Tickers
To add: tell OpenClaw "add NVDA to watchlist"
To remove: tell OpenClaw "remove NVDA from watchlist"

## Active Strategy: JadeCap ICT

- **Instrument:** NQ (Nasdaq 100 E-mini Futures)
- **Prop Firm:** Apex
- **Point Value:** $20/point
- **Kill Zones:** NY AM (9:30-11:30), NY PM (1:00-4:00), Silver Bullet (10:00-11:00, 2:00-3:00)
- **Hard Close:** 15:45 ET
- **Midday Avoidance:** 11:30-13:00 ET

## Risk Parameters

| Parameter | Value |
|-----------|-------|
| Max Loss Per Trade | $500 |
| Daily Loss Limit | $1,000 |
| Max Drawdown | 5% |
| Max Consecutive Losses | 3 |
| Min Risk/Reward | 3:1 |
| ATR Stop Multiplier | 1.5x |
| T1 Close | 50% |

## LLM Configuration

| Role | Model |
|------|-------|
| Default | gpt-4o |
| Deep Think | claude-opus-4-6 |
| Quick Think | gpt-4o-mini |

### Per-Agent Overrides
_(none set — add via "set bull-researcher model to claude-sonnet-4-6")_

## Data Providers

| Category | Provider |
|----------|----------|
| Stock Data | yfinance |
| Indicators | yfinance |
| Fundamentals | yfinance |
| News | yfinance |
| Live Price | auto |

## Schedule

| Phase | Enabled | Time (ET) |
|-------|---------|-----------|
| Pre-Session Analysis | No | Before market open |
| During Session Monitor | — | Every 30 min |
| Post-Session Reflect | No | After market close |

### Market Hours
- **Stock:** 9:30 AM - 4:00 PM ET
- **Futures:** 6:00 PM - 5:00 PM ET (nearly 24h)
- **Mode:** auto (picks based on strategy)

## Pipeline

```
Tier 1: Analysts (parallel)     → market, news
Tier 2: Bull/Bear Debate        → 1 round
Tier 3: Judge → Trader → Risk   → 1 round (aggressive → conservative → neutral)
Tier 4: Portfolio Manager        → FINAL SIGNAL
```

## How to Use

Tell OpenClaw any of these:
- "Set bias to BULLISH — NQ showing strong displacement above midnight open"
- "Add NVDA to watchlist"
- "Switch strategy to default"
- "Change deep think model to claude-sonnet-4-6"
- "Halt trading" / "Resume trading"
- "Run analysis for NQ"
- "Show me the last analysis"
- "What's the current market phase?"

The trading-integrator agent handles all of these by reading/writing `trading-config.json` and dispatching the RunEngine.

---

_Last updated: auto-managed by OpenClaw trading-integrator agent_
