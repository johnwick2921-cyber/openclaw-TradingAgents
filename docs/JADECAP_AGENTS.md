# JadeCap ICT Agent Prompts — Complete Reference

> **Version:** v2 (March 2026)
> **Playbook:** Kyle Ng JadeCap ICT Methodology
> **Instruments:** NQ / MNQ Futures (Apex Trader Funding)

---

## Architecture Overview

```
                    ┌─────────────────┐
                    │   Market Analyst │──┐
                    │   (ICT 9-step)   │  │
                    └─────────────────┘  │
                    ┌─────────────────┐  │    ┌──────────────┐    ┌────────────┐
                    │   News Analyst   │──┼───▶│ Bull vs Bear │───▶│  Research   │
                    │   (Macro/DXY)    │  │    │   Debate     │    │  Manager    │
                    └─────────────────┘  │    │ (Long/Short) │    │  (Judge)    │
                    ┌─────────────────┐  │    └──────────────┘    └─────┬──────┘
                    │  Social Analyst  │──┤                              │
                    │  (generic)       │  │                              ▼
                    └─────────────────┘  │                       ┌────────────┐
                    ┌─────────────────┐  │                       │   Trader   │
                    │ Fundamentals    │──┘                       │  (Validate)│
                    │  (generic)       │                          └─────┬──────┘
                    └─────────────────┘                                │
                                                                       ▼
                                                              ┌──────────────┐
                                                              │  Risk Debate  │
                                                              │ Agg/Con/Neu  │
                                                              └──────┬───────┘
                                                                     │
                                                                     ▼
                                                              ┌──────────────┐
                                                              │  Portfolio   │
                                                              │  Manager     │
                                                              │ (FINAL CALL) │
                                                              └──────────────┘
```

**10 JadeCap-specific agents** (all use ICT terminology):
1. Market Analyst
2. News Analyst
3. Bull Researcher (Long Setup Analyst)
4. Bear Researcher (Short Setup Analyst)
5. Research Manager (Judge)
6. Trader
7. Aggressive Risk Debater
8. Conservative Risk Debater
9. Neutral Risk Debater
10. Portfolio Manager

**2 generic agents** (unchanged — not applicable to ICT futures):
- Social Media Analyst
- Fundamentals Analyst

---

## 1. Market Analyst (`market_analyst_jadecap.py`)

**Role:** Primary ICT analysis engine. Runs the full 10-step playbook.

**Tools:** `get_live_price`, `get_ict_levels`, `get_midnight_open_tool`, `get_killzone_status_tool`, `get_contract_size`

**Config imports:** `JADECAP_CONFIG`, `HARD_RULES`, `RISK`, `KILL_ZONES`, `INSTRUMENTS`, `BULL_SETUP`, `BEAR_SETUP`, `AMD`, `ENTRY_MODELS`, `CHECKLIST`, `DAILY_SWEEP`, `SILVER_BULLET`, `DRAW_ON_LIQUIDITY`, `A_PLUS_SCORING`, `MIDDAY_AVOIDANCE`, `NDOG`, `NWOG`, `IPDA`

### 10-Step Process

| Step | Name | What It Does |
|------|------|-------------|
| 0 | SFP Detection | Maps 1H swing points, checks for breach + close-back-inside = SFP confirmed |
| 1 | HTF Bias | 4H + Daily structure, 200 EMA, unmitigated FVGs, Supertrend, ADX |
| 2 | London Analysis | Did London raid Asian H/L? Sets NY bias direction |
| 3 | Daily Context | Midnight Open (premium/discount), PDH/PDL, NDOG 50% CE, NWOG 50% CE |
| 4 | Liquidity Map | BSL/SSL mapping, 5 Draw on Liquidity questions, IPDA 20/40/60-day levels |
| 5 | Order Flow | 1H FVGs, CHoCH, BOS — must agree with HTF bias or NO TRADE |
| 6 | Kill Zone + News | Kill Zone status, Silver Bullet rules, midday avoidance |
| 7 | Entry Setup | 5 models in priority: FVG → OB → Liquidity Raid → Breaker → OTE |
| 8 | Displacement | Sweep + displacement confirmation required |
| 9 | Checklist + Score | 14-item checklist, weighted A+ scoring (1-10) |

### A+ Scoring (Weighted 1-10)

| Weight | Criterion |
|--------|-----------|
| +2 | HTF + LTF Alignment |
| +2 | FVG at HTF POI |
| +2 | Clear Liquidity Sweep |
| +1 | SFP Confirmed on 1H |
| +1 | Price in Correct Zone |
| +1 | Inside Kill Zone or Silver Bullet |
| +1 | 3R+ Available |
| -1 | Conflicting Structure |
| -1 | High-Impact News within 30 min |

**Sizing:** 8-10 = Full (0.5%) · 6-7 = Standard (0.25%) · 4-5 = Marginal · <4 = NO TRADE

### Output Format
Summary table with: SFP Status, HTF Bias, Zone, Kill Zone, Entry Model, Entry/Stop/Target prices, Contracts, R:R, A+ Score, Draw on Liquidity, NDOG/NWOG CE levels, Checklist pass count, FINAL CALL.

---

## 2. News Analyst (`news_analyst_jadecap.py`)

**Role:** NQ-specific macro analysis. Flags Kill Zone risk levels.

**Tools:** `get_news`, `get_global_news`

**Config imports:** `JADECAP_CONFIG`, `HARD_RULES`, `KILL_ZONES`, `SESSIONS`, `RISK`, `INSTRUMENTS`, `AMD`, `HOLIDAY_RULES`, `MIDDAY_AVOIDANCE`

### 4-Step Process

| Step | Name | What It Does |
|------|------|-------------|
| 1 | Pull News | Searches for FOMC, CPI, NFP, GDP, Fed speakers, tech earnings, DXY, VIX |
| 2 | Kill Zone Risk | Classifies each event as HIGH/MEDIUM/LOW impact per Kill Zone window |
| 3 | Macro Bias | RISK-ON (bullish NQ) vs RISK-OFF (bearish NQ) vs NEUTRAL |
| 4 | Pre-Market | Futures gap size, Asia/London direction, overnight bias |

### Key NQ Movers Tracked
FOMC, CPI, PPI, NFP, GDP, Jobless Claims, ISM, Retail Sales, PCE, Michigan Sentiment, NVDA/AAPL/MSFT/META/GOOGL/AMZN earnings, DXY, 10Y/2Y yields, VIX, options expiration, Quad Witching.

### VIX Risk Levels
- Below 15: Normal size
- 15-20: Tighter stops
- 20-30: Reduce 50%
- Above 30: NO TRADE

### Special Rules
- **Holiday check:** Low-volume days → SFPs unreliable → stand aside or reduce 75%
- **Midday chop:** Flags news in 11:30-1:00 window as double-risk
- **FOMC/CPI/NFP days:** Recommends NO TRADE entire day

### Output Format
Summary table with: Macro Bias, Highest Risk Event, AM/PM KZ Risk, VIX Level, Recommended Action, Contract Adjustment, AMD Alignment, Holiday/Low Volume, Midday Risk.

---

## 3. Bull Researcher (`bull_researcher_jadecap.py`)

**Role:** Argues FOR a LONG trade using ICT evidence. Debates the Bear Researcher.

**Config imports:** `JADECAP_CONFIG`, `HARD_RULES`, `BULL_SETUP`, `RISK`, `INSTRUMENTS`, `KILL_ZONES`, `AMD`, `DAILY_SWEEP`, `DRAW_ON_LIQUIDITY`, `A_PLUS_SCORING`, `IPDA`, `HOLIDAY_RULES`

**Memory:** BM25 memory of past long trade lessons (2 matches).

### 11-Point Argument Structure

| # | Section | Key Questions |
|---|---------|--------------|
| 1 | HTF Bias | 4H/Daily bullish? Above 200 EMA? Bullish FVG unmitigated? Supertrend? |
| 2 | Premium/Discount | Below Midnight Open? Below 50% Fib? Never buy premium. |
| 3 | Liquidity Sweep | SSL swept? Equal lows taken? How far below? Fast reversal? |
| 3.5 | SFP Confirmation | 1H swing low swept + candle closed back inside? |
| 4 | Displacement | Bullish displacement candle after sweep? Size? Body %? |
| 5 | LTF Entry | SFP → FVG → OB → Breaker → OTE priority. Stacked FVGs check. |
| 5b | Stacked FVGs | 4H + 1H FVG at same level = highest confluence |
| 5c | ADX Filter | >25 full / 20-25 reduce / <20 no trade |
| 5d | Silver Bullet | FVG formed during 10-11 AM or 2-3 PM window? |
| 6 | Kill Zone | Inside active window? Silver Bullet bonus? |
| 7 | Draw on Liquidity | 5 DOL questions + IPDA 20/40/60-day confluence |
| 7.5 | IPDA | Long target aligned with delivery levels? |
| 8 | Risk Calc | Entry, stop, target, contracts, R:R (min 2:1) |
| 8b | Multi-TF Confluence | 4H + 1H + 15m: FULL / PARTIAL / NONE |
| 9 | Macro Alignment | Risk-on? DXY weakening? Yields falling? |
| 9.5 | Holiday Check | Low-volume day reduces SFP confidence |
| 10 | Hard Rules | 11-item pass/fail checklist |
| 10.5 | A+ Score | Weighted 1-10 calculation |
| 11 | Counter Bear | Refute every specific short argument |

### Bull Setup Requirements (all must pass)
1. HTF structure bullish (HH/HL on Weekly/4H/Daily)
2. Price in DISCOUNT (below 50% Fib)
3. Price below Midnight Open
4. Bullish FVG on 4H/Daily unmitigated
5. SSL swept (equal lows, prior session low)
6. Displacement candle to upside after sweep
7. Bullish FVG or OB on 5m/15m for entry
8. Inside AM or Silver Bullet Kill Zone
9. 1H SFP confirmed (swept + closed back inside)
10. Draw on Liquidity identified
11. OTE zone (62-79%) contains FVG/OB
12. NDOG/NWOG 50% level marked

**Target:** Previous Daily HIGH (BSL above)
**Stop:** Behind candle 1 of bullish FVG or OB body
**Invalidation:** Price closes below swept low

---

## 4. Bear Researcher (`bear_researcher_jadecap.py`)

**Role:** Mirror of Bull Researcher. Argues FOR a SHORT trade.

Identical 11-point structure but inverted:
- Requires PREMIUM zone (above 50%)
- Requires BSL swept (equal highs, session high)
- Bearish displacement, bearish FVG/OB
- Target: Previous Daily LOW (SSL below)
- Invalidation: Price closes above swept high

---

## 5. Research Manager (`research_manager_jadecap.py`)

**Role:** Judge. Reads both bull and bear arguments, determines which has stronger ICT evidence.

**Config imports:** `JADECAP_CONFIG`, `HARD_RULES`, `BULL_SETUP`, `BEAR_SETUP`, `RISK`, `INSTRUMENTS`, `KILL_ZONES`, `CHECKLIST`, `TRADE_OUTPUT_FORMAT`

**Memory:** BM25 memory of past trade decisions (2 matches).

### 10-Step Judging Process

| Step | What It Does |
|------|-------------|
| 1 | Read both analyst arguments |
| 2 | Compare on 5 criteria: HTF Bias, Sweep, Displacement, FVG/OB, Zone — with exact prices |
| 3 | Verify winner has ALL setup requirements |
| 4 | Verify Kill Zone, displacement timing, sweep sequence, valid entry array |
| 5 | 14-item checklist — ALL must pass |
| 6 | Advanced confluence: Stacked FVGs, ADX filter, Silver Bullet, Multi-TF |
| 7 | Calculate entry, stop, target, contracts, R:R |
| 8 | Hard rules final gate |
| 9 | If neither valid → NO TRADE |
| 10 | Output in trade format |

**Key rule:** Does NOT default to HOLD. Must commit to LONG, SHORT, or NO TRADE.

---

## 6. Trader (`trader_jadecap.py`)

**Role:** Validates the Research Manager's plan, sizes the position, outputs final trade plan.

**Config imports:** `JADECAP_CONFIG`, `HARD_RULES`, `RISK`, `INSTRUMENTS`, `KILL_ZONES`, `CHECKLIST`, `TRADE_OUTPUT_FORMAT`, `IPDA`, `HOLIDAY_RULES`

**Memory:** BM25 memory of past trade decisions (2 matches).

### 11-Step Validation

| Step | What It Does |
|------|-------------|
| 1 | Read Research Manager's plan |
| 2 | Validate against all 21 hard rules |
| 3 | If NO TRADE in plan → output HOLD immediately |
| 4 | Confirm entry, stop, target with IPDA check |
| 5 | ATR stop sizing — calculate contracts |
| 6 | Target management: T1 (close 50%), T2 (stop to BE) + **SET AND FORGET** |
| 7 | Kill Zone window + hard close 4:00 PM |
| 8 | Final news risk check (30 min window) |
| 8b | **Consecutive loss check** — half risk after 2 losses, stop after 3 |
| 9 | Output in trade format with 14-item checklist |
| 10 | Final decision: BUY / SELL / HOLD |

**Set and Forget:** Once stops and targets placed, do NOT move discretionarily. Only permitted: stop to BE after T1 hit.

**Stopped Out ≠ Failed Setup:** Review structural invalidation, not P&L. Journal and assess execution separately from outcome.

### Contract Formula
```
contracts = max_loss / (stop_points × point_value)
NQ:  500 / (stop × 20)
MNQ: 500 / (stop × 2)
```

---

## 7. Aggressive Risk Debater (`aggressive_debator_jadecap.py`)

**Role:** Champions the trade when ICT confluence is strong. Pushes back against excessive caution.

### 5 Argument Areas
1. **Setup Confluence Strength** — stacked FVGs, Silver Bullet FVG, A+ score 8+
2. **Institutional Footprint** — decisive sweep, strong displacement, multi-TF alignment
3. **Risk-Reward Asymmetry** — 3:1+ R:R, 0.25% capped risk, prop firm absorbs capital risk
4. **Counter Conservative** — "missing a setup costs more than a calculated loss"
5. **Counter Neutral** — A+ setups (8+/10) deserve full size, half-sizing underperforms

---

## 8. Conservative Risk Debater (`conservative_debator_jadecap.py`)

**Role:** Protects the prop firm account. Last line of defense against overtrading.

### 6 Argument Areas
1. **Checklist Compliance** — any of 14 items fail = NO TRADE
2. **Structural Risk** — unfilled FVGs between entry/target, ADX <20, nearby liquidity traps
3. **Timing/Session Risk** — Kill Zone edge, midday chop, insufficient time to T1
4. **News/Macro Risk** — HIGH impact within 30 min, holidays, DXY, VIX >20
5. **Prop Firm Protection** — half risk after 2 losses, stop after 3, trailing drawdown
6. **Counter Aggressive** — "blown account costs everything, missing a setup costs nothing"

---

## 9. Neutral Risk Debater (`neutral_debator_jadecap.py`)

**Role:** Balances both sides. Recommends sizing adjustments based on honest A+ score.

### 6 Argument Areas
1. **A+ Score Verification** — walks through all 9 weighted criteria independently
2. **Sizing Recommendation** — 8-10 full / 6-7 standard / 4-5 reduced / <4 no trade
3. **What Each Side Got Right** — identifies strongest point from aggressive and conservative
4. **What Each Side Got Wrong** — identifies weakest point, flags vague claims
5. **Conditional Recommendation** — multi-TF confluence, ADX filter, consecutive losses, Silver Bullet
6. **Final Verdict** — EXECUTE at X% / REDUCE to X% / PASS

---

## 10. Portfolio Manager (`portfolio_manager_jadecap.py`)

**Role:** FINAL decision authority. Synthesizes risk debate + trader plan.

**Config imports:** `JADECAP_CONFIG`, `HARD_RULES`, `RISK`, `INSTRUMENTS`, `KILL_ZONES`, `CHECKLIST`, `BULL_SETUP`, `BEAR_SETUP`, `TRADE_OUTPUT_FORMAT`

**Memory:** BM25 memory of past decisions (2 matches).

### 9-Step Final Decision

| Step | What It Does |
|------|-------------|
| 1 | Read full risk debate (aggressive + conservative + neutral) |
| 2 | Read trader's validated plan |
| 3 | Apply 5-tier rating: BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL |
| 4 | Hard rules final gate |
| 5 | Calculate final contracts (risk consensus + ADX + consecutive losses) |
| 6 | Entry/stop/target/contracts/R:R + **SET AND FORGET** |
| 7 | If prior agents said NO TRADE → enforce HOLD |
| 8 | 14-item checklist final status |
| 9 | Output final decision with rating + executive summary |

### 5-Tier Rating Scale

| Rating | Meaning |
|--------|---------|
| **BUY** | Full LONG confluence. All checklist PASS. Stacked FVGs. Silver Bullet. ADX >25. |
| **OVERWEIGHT** | Strong but 1-2 borderline items. 50-75% contracts. |
| **HOLD** | No valid setup. Checklist fails. Outside KZ. No displacement. |
| **UNDERWEIGHT** | Conflicting signals. No consensus. Reduce to minimum. |
| **SELL** | Full SHORT confluence. All checklist PASS bearish. |

---

## Configuration Reference (`jadecap_config.py`)

### 27 Sections

| # | Section | Items |
|---|---------|-------|
| 1 | INSTRUMENTS | NQ ($20/pt), MNQ ($2/pt) |
| 2 | PROP_FIRMS | Apex, MFF, Lucid — risk rules per firm |
| 3 | LIVE_PRICE | Databento real-time feed config |
| 4 | SESSIONS | Asia 8PM-12AM, London 2-5AM, NY 8AM-4PM EST |
| 5 | KILL_ZONES | AM 9:30-11:30, PM 1:00-4:00, SB1 10-11, SB2 2-3 |
| 6 | SILVER_BULLET | First FVG only, liquidity swept required |
| 7 | MIDDAY_AVOIDANCE | 11:30 AM - 1:00 PM EST chop zone |
| 8 | TIMEFRAMES | Bar lookbacks and indicator assignments |
| 9 | ICT_INDICATORS | 23 indicators with playbook notes |
| 10 | AMD | Accumulation → Manipulation → Distribution |
| 11 | DAILY_SWEEP | SFP on 1H — the #1 strategy |
| 12 | DRAW_ON_LIQUIDITY | 5-question pre-trade framework |
| 13 | NDOG | New Day Opening Gap (5PM-6PM) |
| 14 | NWOG | New Week Opening Gap (Fri 5PM - Sun 6PM) |
| 15 | IPDA | 20/40/60-day delivery ranges |
| 16 | ENTRY_MODELS | 6 models: SFP, FVG, OB, Liq Raid, Breaker, OTE |
| 17 | RISK | $500 max loss, 2:1 min R:R, half risk after 2 losses |
| 18 | A_PLUS_SCORING | 9 weighted criteria (max 10), 4 sizing tiers |
| 19 | HARD_RULES | 21 non-negotiable rules |
| 20 | BULL_SETUP | 12 requirements for valid long |
| 21 | BEAR_SETUP | 12 requirements for valid short |
| 22 | CHECKLIST | 14-item pre-trade checklist |
| 23 | HOLIDAY_RULES | Low-volume day avoidance |
| 24 | TRADE_OUTPUT_FORMAT | Required output structure |
| 25 | calculate_contracts | Sizing function |
| 26 | apply_settings | Runtime UI overrides |
| 27 | JADECAP_CONFIG | Master dict |

### 21 Hard Rules (injected into every agent)

1. Never trade against HTF order flow
2. Only enter inside Kill Zones (AM 9:30-11:30 or PM 1:00-4:00)
3. Minimum 2R before entry
4. Stop behind candle 1 of FVG or OB body
5. One trade per Kill Zone
6. Hard close all positions by 4:00 PM EST
7. If PDH/PDL already taken → NO TRADE
8. Never buy premium, never sell discount
9. Wait for liquidity sweep before entry
10. No trade without displacement candle
11. Max loss $500 per trade
12. Stop trading at $1,000 daily profit
13. No single day loss exceeds $500
14. Only trade during Distribution phase
15. 1H SFP must confirm before LTF entry
16. Only first FVG in Silver Bullet window valid
17. Cancel unfilled Silver Bullet orders when window closes
18. No new entries 11:30 AM - 1:00 PM (midday chop)
19. Stand aside or reduce 75% on holidays
20. A+ score below 4/10 = NO TRADE
21. After 2 consecutive losses, cut risk in half

---

## File Locations

```
tradingagents/
├── jadecap_config.py                          # All 27 config sections
├── agents/
│   ├── analysts/
│   │   ├── market_analyst_jadecap.py          # 10-step ICT analysis
│   │   └── news_analyst_jadecap.py            # NQ macro + Kill Zone risk
│   ├── researchers/
│   │   ├── bull_researcher_jadecap.py         # 11-point long case
│   │   └── bear_researcher_jadecap.py         # 11-point short case
│   ├── managers/
│   │   ├── research_manager_jadecap.py        # Judge (long vs short)
│   │   └── portfolio_manager_jadecap.py       # Final 5-tier decision
│   ├── trader/
│   │   └── trader_jadecap.py                  # Validate + size + execute
│   └── risk_mgmt/
│       ├── aggressive_debator_jadecap.py      # Argues FOR the trade
│       ├── conservative_debator_jadecap.py    # Argues for CAUTION
│       └── neutral_debator_jadecap.py         # Balances + sizes
└── graph/
    └── setup.py                               # Wires JadeCap agents when strategy="jadecap"
```
