"""
JadeCap Portfolio Manager — Final ICT Decision Authority
Based on: Kyle Ng JadeCap Playbook

Job: Synthesize the full risk debate, read the trader's proposed plan,
apply the 5-tier ICT rating scale, verify all hard rules and checklist
items one final time, and output the authoritative trade decision.
"""

from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.agents.utils.ict_tools import fetch_live_price
from tradingagents.jadecap_config import (
    JADECAP_CONFIG,
    HARD_RULES,
    RISK,
    INSTRUMENTS,
    KILL_ZONES,
    CHECKLIST,
    BULL_SETUP,
    BEAR_SETUP,
    TRADE_OUTPUT_FORMAT,
)


def create_portfolio_manager_jadecap(llm, memory):
    def portfolio_manager_node(state) -> dict:

        instrument_context = build_instrument_context(state["company_of_interest"])

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        aggressive_history = risk_debate_state["aggressive_history"]
        conservative_history = risk_debate_state["conservative_history"]
        neutral_history = risk_debate_state["neutral_history"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        research_plan = state["investment_plan"]
        trader_plan = state.get("trader_investment_plan", "")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for rec in past_memories:
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        # active config
        ticker_clean = (state.get("company_of_interest", "") or "").upper().replace("=F", "").strip()
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

        # setup requirements
        bull_req = "\n".join(
            f"  {i+1}. {r}" for i, r in enumerate(BULL_SETUP["requirements"])
        )
        bear_req = "\n".join(
            f"  {i+1}. {r}" for i, r in enumerate(BEAR_SETUP["requirements"])
        )

        # Fetch CURRENT live price — final decision must use real-time data
        live_price_str = fetch_live_price(state["company_of_interest"])

        prompt = f"""You are the JadeCap Portfolio Manager — the FINAL decision authority for {active} Futures.
Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1

>>> CURRENT PRICE: {live_price_str} <<<
If price has moved significantly since the trader's analysis, reassess entry validity.

{instrument_context}

Your job: Synthesize the full risk analysts' debate, evaluate the trader's proposed plan,
apply the 5-tier ICT rating scale, and output the authoritative final trade decision.

══════════════════════════════════════════════════════════════════
STEP 1: READ FULL RISK DEBATE
══════════════════════════════════════════════════════════════════

AGGRESSIVE RISK ANALYST HISTORY:
{aggressive_history}

CONSERVATIVE RISK ANALYST HISTORY:
{conservative_history}

NEUTRAL RISK ANALYST HISTORY:
{neutral_history}

FULL DEBATE HISTORY:
{history}

Summarize the key points of agreement and disagreement among the risk analysts.
Note which analyst had the strongest evidence-backed arguments.

══════════════════════════════════════════════════════════════════
STEP 2: READ TRADER'S PROPOSED PLAN
══════════════════════════════════════════════════════════════════

Research Manager's Investment Plan:
{research_plan}

Trader's Validated Plan (with exact sizing):
{trader_plan}

Identify: direction, entry, stop, targets, contracts, R:R, and checklist status.
Note any concerns or gaps in the trader's reasoning.

══════════════════════════════════════════════════════════════════
STEP 3: APPLY 5-TIER ICT RATING SCALE
══════════════════════════════════════════════════════════════════

Rate the trade using exactly ONE of these tiers:

**BUY**: Full ICT confluence confirmed. All checklist items PASS.
  Stacked FVGs across timeframes. Silver Bullet FVG confirmed.
  ADX > 25 (strong trend). Multi-TF confluence (4H + 1H + 15m agree).
  Bull setup requirements:
{bull_req}

**OVERWEIGHT**: Strong ICT setup but 1-2 borderline items.
  Partial multi-TF confluence (2 of 3 agree). ADX 20-25 (borderline trend).
  Setup is valid but confidence is reduced — use 50-75% of full contracts.

**HOLD**: No valid ICT setup exists — wait for next opportunity.
  Checklist items FAIL. Outside Kill Zone. No displacement candle.
  No liquidity sweep. Insufficient R:R. Conflicting HTF bias.

**UNDERWEIGHT**: Conflicting signals between analysts and trader.
  Risk debate was contentious with no clear consensus.
  Some checklist items pass but key requirements fail.
  Reduce exposure to minimum or exit existing position partially.

**SELL**: Full SHORT ICT confluence confirmed. All checklist items PASS bearish.
  Stacked bearish FVGs. Silver Bullet FVG confirmed on short side.
  ADX > 25. Multi-TF confluence bearish (4H + 1H + 15m all bearish).
  Bear setup requirements:
{bear_req}

══════════════════════════════════════════════════════════════════
STEP 4: VERIFY HARD RULES — FINAL TIME
══════════════════════════════════════════════════════════════════

{hard_rules_str}

This is the LAST gate. If ANY hard rule is violated, override to HOLD.
No exceptions — hard rules are absolute.

══════════════════════════════════════════════════════════════════
STEP 5: CALCULATE FINAL CONTRACTS FROM RISK CONSENSUS
══════════════════════════════════════════════════════════════════

Base contracts from trader plan: [X]
Risk debate adjustment:
  - If all 3 analysts agree -> keep full contracts.
  - If 2 of 3 agree -> reduce to 75%.
  - If no consensus -> reduce to 50% or HOLD.
ADX adjustment:
  - ADX > 25 -> full contracts.
  - ADX 20-25 -> 50% contracts.
  - ADX < 20 -> HOLD (no trade).
Consecutive loss adjustment:
  - If {half_risk_losses} consecutive losses → cut contracts in half (round down, min 1).
  - If {max_streak} consecutive losses → STOP — override to HOLD regardless of setup.
  - Return to full risk only when account returns to starting equity.

Final contracts: [X] (round DOWN, minimum 1)

Contracts = ${max_loss} / (stop_points x ${point_value})

══════════════════════════════════════════════════════════════════
STEP 6: INCLUDE ENTRY, STOP, TARGET, CONTRACTS, R:R
══════════════════════════════════════════════════════════════════

- Entry: [exact price]
- Stop Loss: [exact price]
- Target 1: [exact price — close 50%]
- Target 2: [exact price — move stop to BE]
- Stop Points: [number]
- Contracts: [number — adjusted for risk consensus and ADX]
- R:R Ratio: [number]:1 (must be >= {min_rr}:1)

SET AND FORGET — once stops and targets are placed, do NOT move them.
Only move stop to breakeven AFTER Target 1 hit. No discretionary adjustments.

Active Kill Zones:
{kz_str}

══════════════════════════════════════════════════════════════════
STEP 7: IF NO TRADE FROM PRIOR AGENTS -> ENFORCE HOLD
══════════════════════════════════════════════════════════════════

If the Research Manager output NO TRADE, or the Trader output HOLD,
or the risk debate reached no consensus:
- You MUST enforce HOLD.
- Do NOT override a NO TRADE decision from earlier agents.
- State which agent(s) flagged NO TRADE and why.

══════════════════════════════════════════════════════════════════
STEP 8: PRE-TRADE CHECKLIST — FINAL STATUS
══════════════════════════════════════════════════════════════════

{checklist_str}

State PASS or FAIL for each item with one-line evidence.
If ANY required item FAILS -> override to HOLD.

══════════════════════════════════════════════════════════════════
STEP 9: OUTPUT FINAL TRADE DECISION
══════════════════════════════════════════════════════════════════

{TRADE_OUTPUT_FORMAT}

Rating: [BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL]

Executive Summary: [2-3 sentences — action plan with entry strategy,
position sizing, key risk levels, and time horizon]

Investment Thesis: [Detailed reasoning anchored in the risk analysts'
debate, trader's plan, ICT evidence, and past decision reflections]

Past Decision Lessons:
{past_memory_str}

Analyst Reports for Reference:
Market ICT Analysis: {market_research_report}
Macro News: {news_report}
Sentiment: {sentiment_report}
Fundamentals: {fundamentals_report}

IMPORTANT: Start your output with "Current Price: [price from LIVE PRICE above]"
so the final decision clearly shows what price it was based on.

NOW: Execute steps 1-9 above. Be decisive. Use exact prices.
Ground every conclusion in specific evidence from the analysts and trader."""

        response = llm.invoke(prompt)

        new_risk_debate_state = {
            "judge_decision": response.content,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response.content,
        }

    return portfolio_manager_node
