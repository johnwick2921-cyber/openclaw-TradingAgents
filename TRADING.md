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

> Source of truth: `trading-config.json` (jadecap section)

- **Instruments:** per `jadecap.instruments` in config (NQ primary, ES, MNQ)
- **Prop Firm:** per `jadecap.prop_firm` in config (runtime override via UI or `apply_settings()`)
- **Point Value:** per instrument config ($20/pt NQ, $50/pt ES, $2/pt MNQ)
- **Kill Zones:** per `jadecap.kill_zones` in config (NY AM, NY PM, Silver Bullet x2)
- **Hard Close:** per `jadecap.hard_close_time` in config (default 15:45 ET)
- **Midday Avoidance:** per `jadecap.midday_avoidance` in config (default 11:30-13:00 ET)

## Risk Parameters

> Source of truth: `trading-config.json` (risk section) + `jadecap_config.py` RISK dict

| Parameter | Config Key | Default |
|-----------|-----------|---------|
| Max Loss Per Trade | `risk.max_loss_per_trade` | $500 |
| Daily Loss Limit | `risk.daily_loss_limit` | $1,200 |
| Max Drawdown | `risk.max_drawdown_pct` | 5% |
| Max Consecutive Losses | `risk.max_consecutive_losses` | 3 |
| Min Risk/Reward | `risk.min_risk_reward` | 3:1 |
| ATR Stop Multiplier | `jadecap.atr_stop_multiplier` | 1.5x |
| T1 Close | `jadecap.t1_close_pct` | 50% |

## Scaling and Cashout Rules

> Source of truth: `jadecap_config.py` PROP_FIRMS dict, keyed by `jadecap.prop_firm` in config.
> Active firm is set in `trading-config.json` and overridable at runtime via `apply_settings()`.

Rules vary by prop firm. The active firm's entry in `PROP_FIRMS` defines:

| Field | Description |
|-------|-------------|
| `trailing_drawdown` | Max trailing drawdown before account blow |
| `safety_net` | Balance floor to protect drawdown |
| `profit_target` | Target to pass evaluation / qualify for payout |
| `scaling_step` | Profit increment to unlock more contracts |
| `scaling_increment` | Contracts added per step (MNQ) |
| `max_contracts_nq` / `max_contracts_mnq` | Contract caps |
| `payout_ladder` | Progressive payout amounts per cashout step |
| `post_ladder_floor` | Min balance after completing ladder |
| `consistency_rule` | Max single-day profit as % of total (50%) |
| `min_days_between_payouts` | Cooling period between cashouts |

To change active firm: update `jadecap.prop_firm` in `trading-config.json` or pass `active_firm` to `apply_settings()`.

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
