# Trading Control Panel

> OpenClaw-native trading interface. Agent reads on startup.
> Changes sync to `trading-config.json` automatically.

## Status

- **State:** ACTIVE
- **Strategy:** jadecap
- **Halt:** false
- **Last Run:** NQ on 2026-03-31 → HOLD (13m 40s, 12 agents, full pipeline)

## Market Bias

- **Your Bias:** (set in UI or here)
- **Agent Bias:** HOLD (from last NQ analysis)
- **Confluence:** (computed after each run)

Options: BULLISH | BEARISH | NEUTRAL
Confidence: LOW | MEDIUM | HIGH

## Watchlist

| Ticker | Strategy | Last Signal | Date |
|--------|----------|-------------|------|
| NQ | jadecap | HOLD | 2026-03-31 |

## Active Strategy: JadeCap ICT

- **Instruments:** NQ (primary), ES
- **Prop Firm:** Apex
- **Point Value:** $20/pt (NQ), $50/pt (ES)
- **Kill Zones:** NY AM (9:30-11:30), NY PM (1:00-4:00), Silver Bullet (10:00-11:00, 2:00-3:00)
- **Hard Close:** 15:45 ET
- **Midday Avoidance:** 11:30-13:00 ET

## Risk Parameters

| Parameter | Value |
|-----------|-------|
| Max Loss Per Trade | $500 |
| Daily Loss Limit | $1,200 |
| Max Drawdown | 5% |
| Max Consecutive Losses | 3 |
| Min Risk/Reward | 3:1 |
| ATR Stop Multiplier | 1.5x |
| T1 Close | 50% |

## LLM Configuration (via 9router)

| Role | Model |
|------|-------|
| Default | cc/claude-opus-4-6 |
| Deep Think | cc/claude-opus-4-5-20251101 |
| Quick Think | cc/claude-sonnet-4-6 |

All models route: OpenClaw (18789) → 9router (20128) → AI provider

## Pipeline

```
Tier 1: Analysts (parallel)     → market, social
Tier 2: Bull/Bear Debate        → 1 round
Tier 3: Judge → Trader → Risk   → 2 risk rounds
Tier 4: Portfolio Manager        → FINAL SIGNAL
```

## Dispatch Flow

```
UI "Analyze" → Gateway → Python subprocess → OpenClaw /v1/chat/completions
  → 9router → Claude → response → signal → auto-bias → confluence → DB
```

## Commands

- "Set bias to BULLISH — reason"
- "Add NQ to watchlist"
- "Run analysis for NQ"
- "Halt trading" / "Resume trading"
- "Show last analysis"
