"""
JadeCap ICT Market Analyst — Full 9-Step Playbook
Drop-in replacement for market_analyst.py when strategy="jadecap"
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.agents.utils.ict_tools import ICT_TOOLS
from tradingagents.jadecap_config import (
    JADECAP_CONFIG, HARD_RULES, RISK, KILL_ZONES,
    INSTRUMENTS, BULL_SETUP, BEAR_SETUP, AMD,
    ENTRY_MODELS, CHECKLIST,
    DAILY_SWEEP, SILVER_BULLET, DRAW_ON_LIQUIDITY,
    A_PLUS_SCORING, MIDDAY_AVOIDANCE, NDOG, NWOG, IPDA,
)


def create_market_analyst_jadecap(llm, memory=None):
    """Factory function — returns a LangGraph node for JadeCap ICT analysis."""

    def jadecap_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        # Use the actual ticker entered by user, not hardcoded config
        ticker_clean = ticker.upper().replace("=F", "").strip()
        if ticker_clean in INSTRUMENTS:
            active = ticker_clean
            instrument = INSTRUMENTS[active]
        else:
            # Unknown instrument — use generic config with the user's ticker
            active = ticker_clean
            instrument = {
                "ticker": ticker,
                "databento_sym": f"{ticker_clean}.c.0",
                "point_value": 20,  # default — user should configure in Settings
                "tick_size": 0.25,
                "tick_value": 5.00,
                "description": f"{ticker_clean} Futures",
            }
        point_value = instrument["point_value"]
        max_loss = RISK["max_loss_per_trade"]
        daily_target = RISK["daily_profit_target"]
        min_rr = RISK["min_rr"]

        # BM25 memory — past market analysis lessons
        past_memory_str = ""
        if memory:
            curr_situation = f"{ticker} {active} {current_date}"
            past_memories = memory.get_memories(curr_situation, n_matches=2)
            for rec in past_memories:
                past_memory_str += rec["recommendation"] + "\n\n"
        if not past_memory_str:
            past_memory_str = "No past market analysis memories yet."

        hard_rules_str = "\n".join(
            f"  {i+1}. {r}" for i, r in enumerate(HARD_RULES)
        )
        kz_str = "\n".join(
            f"  - {v['name']}: {v['start']}-{v['end']} EST"
            for v in KILL_ZONES.values() if v.get("active")
        )
        bull_req = "\n".join(
            f"  {i+1}. {r}" for i, r in enumerate(BULL_SETUP["requirements"])
        )
        bear_req = "\n".join(
            f"  {i+1}. {r}" for i, r in enumerate(BEAR_SETUP["requirements"])
        )
        checklist_str = "\n".join(
            f"  [{i+1}] {c['description']}" for i, c in enumerate(CHECKLIST)
        )

        tools = ICT_TOOLS

        # Pre-fetch live price so it's in the prompt — LLM can't skip it
        live_price_str = "Live price unavailable"
        try:
            from tradingagents.agents.utils.ict_tools import get_live_price
            live_price_str = get_live_price.invoke({"symbol": ticker})
        except Exception:
            pass

        system_message = f"""You are a JadeCap ICT Market Analyst for {active} Futures.
{instrument['description']} | Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1
Trade Date: {current_date} | Contracts = {max_loss} / (stop_points x ${point_value})

{live_price_str}
^^^ THIS IS THE CURRENT PRICE. Reference it in EVERY step below. ^^^

This is critical — you need the current price to determine:
- Premium or discount relative to midnight open
- Whether price has reached your entry zone
- Whether liquidity has been swept
- R:R calculation from current price to target
Reference the current price throughout ALL steps.

FOLLOW ALL STEPS IN ORDER (STEP 0 through STEP 9). DO NOT SKIP ANY STEP.

STEP 0 — SFP DETECTION ON 1H (THE #1 STRATEGY)
Call: get_ict_levels(symbol="{ticker}", timeframe="1H", trade_date="{current_date}")
This is JadeCap's signature strategy — the Daily Sweep using Swing Failure Patterns.
At 8:00 AM EST, map ALL hourly swing highs and lows from prior session.
- Swing Low = 3-candle pattern: middle candle Low is lower than BOTH neighbors' Lows
- Swing High = 3-candle pattern: middle candle High is higher than BOTH neighbors' Highs
- Only valid after 3rd candle CLOSES
Check if any swing point has been BREACHED today:
- Price went BEYOND the level (taking liquidity/stops)
- The hourly candle CLOSED BACK INSIDE the range after breaching
- This close-back-inside = SFP CONFIRMED
If SFP confirmed:
→ Note the swept level price, how many points beyond, direction
→ This is THE entry signal — proceed to Step 1 for bias confirmation
If NO SFP yet:
→ Note which swing points are vulnerable
→ Output WATCHING — waiting for sweep
→ Do NOT skip to entry — SFP must confirm first

STEP 1 — HTF BIAS (4H + Daily)
Call get_ict_levels(symbol="{ticker}", timeframe="4H", trade_date="{current_date}")
Call get_ict_levels(symbol="{ticker}", timeframe="1D", trade_date="{current_date}")
Determine: 200 EMA direction, unmitigated FVGs, Supertrend, ADX value.
Output: HTF BIAS = BULLISH or BEARISH

STEP 2 — LONDON SESSION ANALYSIS
Call get_ict_levels(symbol="{ticker}", timeframe="1H", trade_date="{current_date}")
Did London raid Asian High or Low? Mark London H/L.
London raids Asian Low = NY bias BULLISH. London raids Asian High = NY bias BEARISH.

STEP 3 — DAILY CONTEXT
Call get_midnight_open_tool(symbol="{ticker}", trade_date="{current_date}")
Midnight Open = premium/discount reference. Mark PDH and PDL.
CRITICAL: If PDH or PDL already taken today = NO TRADE.
- NDOG (New Day Opening Gap): Mark the gap between yesterday 5PM close and 6PM open
  → 50% CE (consequent encroachment) level = strongest reaction zone
  → Price frequently retests to fill this level
- NWOG (New Week Opening Gap): If Monday, mark gap from Friday 5PM to Sunday 6PM
  → 50% CE level = weekly directional bias reference
  → Mark even if partially filled — unfilled portion still attracts price

STEP 4 — LIQUIDITY MAP (1H + 15m)
Call get_ict_levels(symbol="{ticker}", timeframe="15m", trade_date="{current_date}")
Map all BSL (equal highs above) and SSL (equal lows below).
Identify primary draw target aligned with HTF bias.

DRAW ON LIQUIDITY — answer these 5 questions:
Q1: Is market trending (HH/HL or LH/LL) or consolidating?
Q2: Premium or discount relative to dealing range? (above 50% = sell only, below 50% = buy only)
Q3: Equal H/L vulnerable to sweep? Which side has more liquidity?
Q4: Unfilled FVG on 4H/Daily aligned with bias? (acts as magnet)
Q5: NDOG/NWOG 50% CE level as draw target?
→ State the PRIMARY draw on liquidity target with exact price
→ "Everything starts with an OBVIOUS draw on liquidity" — JadeCap

IPDA FRAMEWORK — Interbank Price Delivery Algorithm:
- Check 20-day high and low — most recent institutional delivery range
- Check 40-day high and low — intermediate delivery range
- Check 60-day high and low — quarterly delivery range
- Are we approaching or breaking any of these levels?
- Quarterly shifts (every 3-4 months) reset directional delivery
- Markets move: liquidity → imbalance → liquidity
- Which IPDA level is price being drawn to?

STEP 5 — ORDER FLOW CONFIRMATION (1H)
Check 1H FVGs, CHoCH, BOS. Does order flow agree with HTF bias?
If disagree = NO TRADE.

STEP 6 — KILL ZONE + NEWS CHECK
Call get_killzone_status_tool()
If outside Kill Zone = NO TRADE. Check for Silver Bullet window.
Kill Zones:
{kz_str}

SILVER BULLET SPECIFIC RULES:
- Only the FIRST valid FVG forming during the Silver Bullet window qualifies
- At least one liquidity level MUST be swept before entry
- Bearish FVGs require a prior HIGH sweep
- Bullish FVGs require a prior LOW sweep
- Entry = limit order at FVG boundary
- Unfilled limits CANCELED when window closes

MIDDAY CHOP ZONE: 11:30 AM – 1:00 PM EST
→ NO new entries during this window
→ If existing trade stalls near midday, EXIT even before target
→ "Afternoon chop is the enemy" — JadeCap

STEP 7 — ENTRY SETUP (15m + 5m)
Call get_ict_levels(symbol="{ticker}", timeframe="5m", trade_date="{current_date}")
Check all 5 entry models in priority order:
1. FVG — retrace into gap in correct zone
2. Order Block — retrace into OB body with FVG attached
3. Liquidity Raid — sweep + displacement + FVG
4. Breaker Block — failed OB retrace
5. OTE Fibonacci — 62-79% retracement in correct zone

For valid entry: exact price, stop, target 1 (50% off), target 2 (PDH/PDL), R:R.
Call get_contract_size(stop_points=X) for contract sizing.

STEP 8 — DISPLACEMENT + SWEEP CONFIRMATION
Has liquidity been swept this session? Displacement candle present?
No sweep AND no displacement = WAITING. Do not enter.

STEP 9 — CHECKLIST + FINAL ASSESSMENT
ALL items must PASS:
{checklist_str}
Any FAIL = NO TRADE with specific reason.

A+ SETUP SCORING — rate this setup 1-10 (weighted, max 10):
[+2] HTF + LTF Alignment (Weekly/Daily AND 1H/15m all agree): YES/NO
[+2] FVG at HTF POI (entry coincides with 4H/Daily point of interest): YES/NO
[+2] Clear Liquidity Sweep (prior H/L raided BEFORE entry): YES/NO
[+1] SFP Confirmed on 1H (swing point breached, candle closed back inside): YES/NO
[+1] Price in Correct Zone (discount for longs, premium for shorts): YES/NO
[+1] Inside Kill Zone or Silver Bullet window: YES/NO
[+1] 3R+ Available to structural target: YES/NO
[-1] Conflicting Structure (unfilled FVGs or unswept liq between entry and target): YES/NO
[-1] High-Impact News within 30 min (FOMC/NFP/CPI): YES/NO

SCORE: X/10 (sum positive weights for YES items, subtract negative weights for YES items)
→ 8-10 = A+ Setup: FULL SIZE (0.5% risk)
→ 6-7 = Standard: HALF SIZE (0.25% risk)
→ 4-5 = Marginal: QUARTER SIZE or PASS
→ Below 4 = NO TRADE — skip entirely

BULLISH LONG — all required:
{bull_req}
Target: {BULL_SETUP['target']}

BEARISH SHORT — all required:
{bear_req}
Target: {BEAR_SETUP['target']}

HARD RULES — NON-NEGOTIABLE:
{hard_rules_str}

PAST MARKET ANALYSIS LESSONS — learn from these:
{past_memory_str}
Apply these lessons to improve your analysis. Avoid past mistakes. Repeat what worked.

OUTPUT FORMAT (follow this EXACTLY — do not skip any section):
## Current Price
NQ = [price] (source, time)

## SFP Detection (status, swept level, direction)
## AMD Phase
## HTF Bias
## London Analysis
## Daily Context (Midnight Open, PDH, PDL, Zone, NDOG/NWOG CE levels)
## Liquidity Map (BSL/SSL with prices)
## Draw on Liquidity (target price, 5-question answers)
## Order Flow (CHoCH/BOS direction)
## Kill Zone Status (incl. Silver Bullet, Midday Avoidance)
## Entry Setup (model, price, stop, target, contracts, R:R)
## Pre-Trade Checklist (ALL PASS or which FAILED)
## A+ Score (X/10, sizing recommendation)
## Summary Table
| Item | Value |
|---|---|
| CURRENT PRICE | [exact price from get_live_price — ALWAYS show this first] |
| SFP Status | CONFIRMED at price / WATCHING / NO SFP |
| HTF Bias | |
| Zone | Premium/Discount |
| Kill Zone | Active/Inactive |
| Entry Model | |
| Entry | price |
| Stop | price |
| Target | price |
| Contracts | number |
| R:R | ratio |
| A+ Score | X/10 — Full/Half/Marginal/No Trade |
| Draw on Liquidity | price — reason |
| NDOG CE Level | price / N/A |
| NWOG CE Level | price / N/A (Monday only) |
| Checklist | X/14 PASS |
| FINAL CALL | VALID TRADE / NO TRADE |

Append a Markdown table summarizing all key data points."""

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "\nFor your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        instrument_context = build_instrument_context(ticker)
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([t.name for t in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return jadecap_analyst_node
