"""
JadeCap Research Manager / ICT Judge (replaces generic Research Manager)
Based on: Kyle Ng JadeCap Playbook

Job: Read both Long and Short analyst arguments, judge which has stronger
ICT evidence, verify all checklist items, and output a final trade plan
or NO TRADE decision.
"""

from tradingagents.agents.utils.agent_utils import build_instrument_context
from tradingagents.agents.utils.ict_tools import fetch_live_price
from tradingagents.jadecap_config import (
    JADECAP_CONFIG,
    HARD_RULES,
    BULL_SETUP,
    BEAR_SETUP,
    RISK,
    INSTRUMENTS,
    KILL_ZONES,
    CHECKLIST,
    TRADE_OUTPUT_FORMAT,
)


def create_research_manager_jadecap(llm, memory):
    def research_manager_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history       = investment_debate_state.get("history", "")
        bull_history  = investment_debate_state.get("bull_history", "")
        bear_history  = investment_debate_state.get("bear_history", "")

        # all analyst reports
        market_report       = state["market_report"]
        sentiment_report    = state["sentiment_report"]
        news_report         = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

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
        max_loss    = RISK["max_loss_per_trade"]
        min_rr      = RISK["min_rr"]

        # BM25 memory — past trade decision lessons
        curr_situation = f"{market_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories  = memory.get_memories(curr_situation, n_matches=2)
        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"
        if not past_memory_str:
            past_memory_str = "No past trade decision memories yet."

        # build setup requirement strings
        bull_req = "\n".join(
            f"  {i+1}. {r}" for i, r in enumerate(BULL_SETUP["requirements"])
        )
        bear_req = "\n".join(
            f"  {i+1}. {r}" for i, r in enumerate(BEAR_SETUP["requirements"])
        )

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

        # Fetch CURRENT live price for real-time context
        ticker = state.get("company_of_interest", f"{active}=F")
        live_price_str = fetch_live_price(ticker)

        # instrument context
        instrument_context = build_instrument_context(
            state.get("company_of_interest", f"{active}=F")
        )

        prompt = f"""You are the JadeCap ICT Judge and Portfolio Manager for {active} Futures.
Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1

{instrument_context}

>>> CURRENT PRICE: {live_price_str} <<<
Use this price for all premium/discount zone checks and R:R calculations.

Your job: Read both the Long Setup Analyst and Short Setup Analyst arguments,
determine which side has STRONGER ICT evidence, verify every requirement, and
output a final trade plan — or NO TRADE if neither side qualifies.

CRITICAL: Do NOT default to HOLD. You must commit to LONG, SHORT, or NO TRADE.
HOLD is not a valid output. If the evidence is ambiguous, the answer is NO TRADE,
not HOLD.

══════════════════════════════════════════════════════════════════
STEP 1: READ BOTH ANALYST ARGUMENTS
══════════════════════════════════════════════════════════════════

LONG SETUP ANALYST FULL ARGUMENT:
{bull_history}

SHORT SETUP ANALYST FULL ARGUMENT:
{bear_history}

FULL DEBATE HISTORY:
{history}

══════════════════════════════════════════════════════════════════
STEP 2: WHICH SIDE HAS STRONGER ICT EVIDENCE?
══════════════════════════════════════════════════════════════════

Compare both arguments on these criteria — use EXACT PRICES, not vague language:

a) HTF Bias: Which analyst cited specific 4H/Daily structure with exact price levels?
   - Long says HTF is bullish because: [summarize with prices]
   - Short says HTF is bearish because: [summarize with prices]
   - WINNER on HTF: LONG / SHORT / NEITHER

b) Liquidity Sweep: Which analyst proved a specific sweep occurred?
   - Long says SSL swept at: [exact price]
   - Short says BSL swept at: [exact price]
   - Was the sweep confirmed with a quick reversal or slow drift?
   - WINNER on Sweep: LONG / SHORT / NEITHER

c) Displacement: Which analyst cited a stronger displacement candle?
   - Long displacement: [X] points, [X]% body, during [Kill Zone]
   - Short displacement: [X] points, [X]% body, during [Kill Zone]
   - WINNER on Displacement: LONG / SHORT / NEITHER

d) FVG/OB Entry: Which analyst identified a cleaner LTF entry?
   - Long FVG/OB at: [exact price range]
   - Short FVG/OB at: [exact price range]
   - WINNER on Entry: LONG / SHORT / NEITHER

e) Premium/Discount: Is price actually in the correct zone for the winning side?
   - Current price vs Midnight Open vs 50% Fib
   - If price is in PREMIUM -> only SHORT is valid
   - If price is in DISCOUNT -> only LONG is valid
   - WINNER on Zone: LONG / SHORT / NEITHER

══════════════════════════════════════════════════════════════════
STEP 3: DOES THE WINNER HAVE ALL SETUP REQUIREMENTS?
══════════════════════════════════════════════════════════════════

If LONG wins — verify ALL Bull Setup requirements:
{bull_req}
Target: {BULL_SETUP['target']}
Stop: {BULL_SETUP['stop']}

If SHORT wins — verify ALL Bear Setup requirements:
{bear_req}
Target: {BEAR_SETUP['target']}
Stop: {BEAR_SETUP['stop']}

State PASS or FAIL for each requirement with evidence.
If ANY requirement FAILS -> the winning side is INVALID.
Then check if the OTHER side passes all requirements.
If NEITHER passes -> output NO TRADE.

══════════════════════════════════════════════════════════════════
STEP 4: VERIFY KILL ZONE, DISPLACEMENT, SWEEP, FVG/OB
══════════════════════════════════════════════════════════════════

Active Kill Zones:
{kz_str}

- Are we currently inside a Kill Zone? State which one.
- If outside Kill Zone -> NO TRADE regardless of setup quality.
- Was the displacement candle INSIDE the Kill Zone? If not -> NO TRADE.
- Was the liquidity sweep BEFORE the displacement? (correct sequence)
- Is there a valid FVG or OB to enter on? State exact price range.

══════════════════════════════════════════════════════════════════
STEP 5: PRE-TRADE CHECKLIST — ALL MUST PASS
══════════════════════════════════════════════════════════════════

{checklist_str}

State PASS or FAIL for each item with one-line evidence.
If ANY item FAILS -> output NO TRADE.

══════════════════════════════════════════════════════════════════
STEP 6: ADVANCED CONFLUENCE CHECKS
══════════════════════════════════════════════════════════════════

a) STACKED FVGs: Is there a 4H FVG AND 1H FVG at the same price level?
   - If YES = HIGHEST CONFLUENCE — flag clearly.
   - If NO = proceed with single-TF FVG (lower confidence).

b) ADX FILTER: What is ADX on 1H?
   - ADX > 25 = STRONG trend = full contracts.
   - ADX 20-25 = BORDERLINE = reduce to 50% contracts.
   - ADX < 20 = CHOPPY = NO TRADE.

c) SILVER BULLET FVG: Did a FVG form during Silver Bullet window?
   - Silver Bullet 1: 10:00-11:00 AM EST
   - Silver Bullet 2: 2:00-3:00 PM EST
   - If YES = SILVER BULLET FVG CONFIRMED — highest probability.
   - If NO = standard FVG still valid, lower probability.

d) MULTI-TIMEFRAME CONFLUENCE:
   - 4H bias: BULLISH / BEARISH
   - 1H order flow: BULLISH / BEARISH
   - 15m entry: BULLISH / BEARISH
   - All 3 agree = FULL CONFLUENCE = full contracts.
   - 2 of 3 agree = PARTIAL CONFLUENCE = 50% contracts.
   - 1 of 3 = NO CONFLUENCE = NO TRADE.

══════════════════════════════════════════════════════════════════
STEP 7: CALCULATE ENTRY, STOP, TARGET, CONTRACTS
══════════════════════════════════════════════════════════════════

- Entry: [exact price — FVG midpoint, OB body, or Breaker level]
- Stop Loss: [exact price — behind candle 1 of FVG or OB body]
- Stop Distance: [X] points
- Contracts: {max_loss} / (stop_points x ${point_value}) = [X]
  - Adjust for ADX filter and multi-TF confluence if needed.
- Target 1: [exact price — first liquidity pool] — close 50%
- Target 2: [exact price — PDH or PDL] — move stop to BE
- R:R Ratio: must be minimum {min_rr}:1
- If R:R < {min_rr}:1 -> NO TRADE regardless of setup quality.

══════════════════════════════════════════════════════════════════
STEP 8: HARD RULES — FINAL GATE
══════════════════════════════════════════════════════════════════

{hard_rules_str}

If ANY hard rule is violated -> output NO TRADE.

══════════════════════════════════════════════════════════════════
STEP 9: IF NEITHER VALID -> NO TRADE
══════════════════════════════════════════════════════════════════

If neither the Long nor Short analyst provided sufficient evidence,
or if any checklist item or hard rule failed:
- Output Direction: NO TRADE
- State exactly which requirements failed
- State what needs to happen before a valid setup exists

══════════════════════════════════════════════════════════════════
STEP 10: OUTPUT IN TRADE FORMAT
══════════════════════════════════════════════════════════════════

{TRADE_OUTPUT_FORMAT}

PAST DECISION LESSONS — apply these to avoid repeating mistakes:
{past_memory_str}

ANALYST REPORTS FOR REFERENCE:
Market ICT Analysis:
{market_report}

Macro News Report:
{news_report}

Sentiment Report:
{sentiment_report}

Fundamentals Report:
{fundamentals_report}

IMPORTANT: Start your output with "Current Price: [price from LIVE PRICE above]"
so everyone can see the price this decision is based on.

NOW: Execute steps 1-10 above. Be decisive. Use exact prices.
Do NOT default to HOLD — commit to LONG, SHORT, or NO TRADE."""

        response = llm.invoke(prompt)

        new_investment_debate_state = {
            "judge_decision":   response.content,
            "history":          investment_debate_state.get("history", ""),
            "bear_history":     investment_debate_state.get("bear_history", ""),
            "bull_history":     investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count":            investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
