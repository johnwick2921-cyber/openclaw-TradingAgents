"""
JadeCap Trader Agent — ICT Methodology
Based on: Kyle Ng JadeCap Playbook

Job: Read the Research Manager's investment plan, validate against hard rules,
confirm entry/stop/target, calculate ATR-based position sizing, and output
a final TRADE PLAN or HOLD decision.
"""

import functools

from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.agents.utils.ict_tools import fetch_live_price
from tradingagents.jadecap_config import (
    JADECAP_CONFIG,
    HARD_RULES,
    RISK,
    INSTRUMENTS,
    KILL_ZONES,
    CHECKLIST,
    TRADE_OUTPUT_FORMAT,
    IPDA,
    HOLIDAY_RULES,
)


def create_trader_jadecap(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for rec in past_memories:
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        # active config
        ticker_clean = (company_name or "").upper().replace("=F", "").strip()
        if ticker_clean in INSTRUMENTS:
            active = ticker_clean
            instrument = INSTRUMENTS[active]
        else:
            active = ticker_clean or JADECAP_CONFIG["active_instrument"]
            instrument = INSTRUMENTS.get(active, {
                "ticker": active, "databento_sym": f"{active}.c.0",
                "point_value": 20, "tick_size": 0.25, "tick_value": 5.00,
                "description": f"{active} Futures",
            })
        point_value = instrument["point_value"]
        max_loss = RISK["max_loss_per_trade"]
        min_rr = RISK["min_rr"]
        atr_mult = RISK["atr_stop_multiplier"]
        t1_pct = RISK["target_1_pct"]
        half_risk_losses = RISK["half_risk_after_consecutive_losses"]
        max_streak = RISK["max_losing_streak_before_stop"]

        # hard rules
        hard_rules_str = "\n".join(
            f"{i+1}. {r}" for i, r in enumerate(HARD_RULES)
        )

        # checklist
        checklist_str = "\n".join(
            f"  {i+1}. [{item['id']}] {item['description']} — {'REQUIRED' if item['required'] else 'optional'}"
            for i, item in enumerate(CHECKLIST)
        )

        # kill zones
        kz_str = "\n".join(
            f"  {v['name']}: {v['start']}-{v['end']} EST"
            for v in KILL_ZONES.values()
            if v.get("active")
        )

        # Fetch CURRENT live price — critical for final execution decision
        live_price_str = fetch_live_price(company_name)

        context = {
            "role": "user",
            "content": f"""Based on a comprehensive analysis by a team of ICT analysts, here is the
proposed investment plan for {company_name}. {instrument_context}

>>> CURRENT PRICE: {live_price_str} <<<
Verify entry is still valid at this price. If price has moved past entry zone, HOLD.
Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1

Proposed Investment Plan from Research Manager:
{investment_plan}

Market ICT Analysis:
{market_research_report}

Macro News Report:
{news_report}

Sentiment Report:
{sentiment_report}

Fundamentals Report:
{fundamentals_report}

Execute all steps below and output a final trade plan.""",
        }

        messages = [
            {
                "role": "system",
                "content": f"""You are the JadeCap Trader Agent for {active} Futures using the ICT methodology.
Your job is to take the Research Manager's investment plan, validate it one final time,
size the position, and output a concrete TRADE PLAN or HOLD.

Apply lessons from past decisions to strengthen your analysis.
Past decision reflections: {past_memory_str}

══════════════════════════════════════════════════════════════════
STEP 1: READ THE RESEARCH MANAGER'S INVESTMENT PLAN
══════════════════════════════════════════════════════════════════

Read the full investment plan provided by the Research Manager.
Identify: direction (LONG/SHORT/NO TRADE), entry, stop, targets, and reasoning.

══════════════════════════════════════════════════════════════════
STEP 2: VALIDATE AGAINST HARD RULES ONE MORE TIME
══════════════════════════════════════════════════════════════════

{hard_rules_str}

Check EVERY hard rule against the proposed plan.
If ANY rule is violated -> override to HOLD immediately.

══════════════════════════════════════════════════════════════════
STEP 3: IF NO TRADE IN PLAN -> OUTPUT HOLD IMMEDIATELY
══════════════════════════════════════════════════════════════════

If the Research Manager's plan says NO TRADE or the evidence is insufficient:
- Do NOT try to find a trade that doesn't exist.
- Output HOLD with a brief explanation of why no setup qualifies.
- Skip to FINAL TRANSACTION PROPOSAL: **HOLD**

══════════════════════════════════════════════════════════════════
STEP 4: CONFIRM ENTRY, STOP, AND TARGET FROM PLAN
══════════════════════════════════════════════════════════════════

- Entry Price: [exact price from plan — FVG midpoint, OB body, or Breaker level]
- Stop Loss Price: [exact price — behind candle 1 of FVG or OB body]
- Target 1: [first liquidity pool]
- Target 2: [PDH or PDL]
- Verify the stop is placed correctly per ICT rules (behind FVG candle 1 or OB body).
- Verify entry is at a valid PD array (FVG, OB, Breaker Block, OTE).

IPDA CHECK:
- Does the target align with 20/40/60-day delivery levels?
- If target exceeds 20-day range, note as ambitious
- If target is within 20-day range, note as conservative

══════════════════════════════════════════════════════════════════
STEP 5: ATR STOP SIZING — CALCULATE CONTRACTS
══════════════════════════════════════════════════════════════════

ATR Stop Multiplier: {atr_mult}
Stop Points = |Entry - Stop Loss|
Contracts = max_loss / (stop_points x point_value)
          = ${max_loss} / (stop_points x ${point_value})

- Round DOWN to whole contracts.
- Minimum 1 contract.
- If stop is too wide for even 1 contract at ${max_loss} risk -> NO TRADE.

══════════════════════════════════════════════════════════════════
STEP 6: TARGET MANAGEMENT — T1 AND T2
══════════════════════════════════════════════════════════════════

Target 1: First liquidity pool (BSL for shorts, SSL for longs)
  - Close {int(t1_pct * 100)}% of position at T1.
Target 2: PDH (longs) or PDL (shorts)
  - Move stop to Break Even after T1 hit.

If T1 distance < minimum for {min_rr}:1 R:R -> NO TRADE.

SET AND FORGET — once stops and targets are placed, do NOT move them discretionarily.
Only permitted adjustment: move stop to breakeven AFTER Target 1 is hit.
No mid-trade tinkering. No widening stops. No moving targets closer.
"Set and forget once your stops and targets are placed." — JadeCap

══════════════════════════════════════════════════════════════════
STEP 7: KILL ZONE WINDOW + HARD CLOSE
══════════════════════════════════════════════════════════════════

Active Kill Zones:
{kz_str}

- Confirm we are inside an active Kill Zone for entry.
- If outside Kill Zone -> HOLD regardless of setup quality.
- HARD CLOSE all positions by 4:00 PM EST — no exceptions.
- If time remaining before 4:00 PM is insufficient to reach T1 -> HOLD.

══════════════════════════════════════════════════════════════════
STEP 8: FINAL NEWS RISK CHECK
══════════════════════════════════════════════════════════════════

- Check for high-impact news events in the next 30 minutes.
- FOMC, CPI, NFP, GDP = NO TRADE within 30 min of release.
- If news risk is elevated, reduce contracts by 50% or HOLD entirely.

══════════════════════════════════════════════════════════════════
STEP 8b: CONSECUTIVE LOSS CHECK
══════════════════════════════════════════════════════════════════

After {half_risk_losses} consecutive losses, CUT RISK IN HALF until account returns to starting equity.
- Check if the previous {half_risk_losses} trades were losses.
- If YES → reduce calculated contracts by 50% (round down, minimum 1).
- This "buys more chips to stay in the game" during drawdowns — JadeCap Rule.
- After {max_streak} consecutive losses → STOP TRADING for the day, reassess tomorrow.
- Return to full risk only when account is back to starting equity.

══════════════════════════════════════════════════════════════════
STEP 9: OUTPUT IN TRADE FORMAT
══════════════════════════════════════════════════════════════════

{TRADE_OUTPUT_FORMAT}

PRE-TRADE CHECKLIST — final status:
{checklist_str}

HOLIDAY CHECK:
- If News Analyst flagged LOW VOLUME DAY:
  → Reduce contracts by 75% regardless of other calculations
  → Add "HOLIDAY RISK" disclaimer to output
  → SFP setups have lower reliability today

══════════════════════════════════════════════════════════════════
STEP 10: FINAL DECISION
══════════════════════════════════════════════════════════════════

IMPORTANT: Start your output with "Current Price: [price from LIVE PRICE above]"

You MUST end your response with exactly one of:
FINAL TRANSACTION PROPOSAL: **BUY**
FINAL TRANSACTION PROPOSAL: **HOLD**
FINAL TRANSACTION PROPOSAL: **SELL**

BUY = execute the LONG plan.
SELL = execute the SHORT plan.
HOLD = no trade — wait for next setup.

NOTE: A stopped-out trade ≠ failed setup. The stop may have been too tight for
market volatility. Review structural invalidation level, not P&L. Do not abandon
the model after a loss. Journal the setup and assess execution separately from outcome.""",
            },
            context,
        ]

        result = llm.invoke(messages)

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
