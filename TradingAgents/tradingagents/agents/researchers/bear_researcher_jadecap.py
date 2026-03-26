"""
JadeCap Short Setup Analyst (replaces generic Bear Researcher)
Based on: Kyle Ng JadeCap Playbook

Job: Argue WHY a SHORT trade is valid right now using ICT evidence.
Reads: All 4 analyst reports + debate history + BM25 memory.
Output: Evidence-based short case with specific ICT price levels.
"""


from tradingagents.agents.utils.ict_tools import fetch_live_price
from tradingagents.jadecap_config import (
    JADECAP_CONFIG,
    HARD_RULES,
    BEAR_SETUP,
    RISK,
    INSTRUMENTS,
    KILL_ZONES,
    AMD,
    DAILY_SWEEP,
    DRAW_ON_LIQUIDITY,
    A_PLUS_SCORING,
    IPDA,
    HOLIDAY_RULES,
)


def create_bear_researcher_jadecap(llm, memory):

    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history       = investment_debate_state.get("history", "")
        bear_history  = investment_debate_state.get("bear_history", "")
        current_response = investment_debate_state.get("current_response", "")

        # all analyst reports
        market_report      = state["market_report"]
        news_report        = state["news_report"]
        sentiment_report   = state["sentiment_report"]
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
        max_loss   = RISK["max_loss_per_trade"]
        min_rr     = RISK["min_rr"]

        # Fetch CURRENT live price for real-time context
        ticker = state.get("company_of_interest", f"{active}=F")
        live_price_str = fetch_live_price(ticker)

        # BM25 memory — past short trade lessons
        curr_situation = f"{market_report}\n\n{news_report}\n\n{sentiment_report}"
        past_memories  = memory.get_memories(curr_situation, n_matches=2)
        past_memory_str = ""
        for rec in past_memories:
            past_memory_str += rec["recommendation"] + "\n\n"
        if not past_memory_str:
            past_memory_str = "No past short trade memories yet."

        # build bear setup requirements
        bear_req = "\n".join(
            f"  {i+1}. {r}"
            for i, r in enumerate(BEAR_SETUP["requirements"])
        )

        # build hard rules
        hard_rules_str = "\n".join(
            f"{i+1}. {r}" for i, r in enumerate(HARD_RULES)
        )

        # kill zones
        kz_str = "\n".join(
            f"  {v['name']}: {v['start']}-{v['end']} EST"
            for v in KILL_ZONES.values()
            if v.get("active")
        )

        prompt = f"""You are the JadeCap Short Setup Analyst for {active} Futures.
Point Value: ${point_value} | Max Risk: ${max_loss} | Min R:R: {min_rr}:1

>>> CURRENT PRICE: {live_price_str} <<<
Use this price for all zone/R:R calculations.

Your ONLY job: Build the strongest possible case for a SHORT trade right now
using ICT evidence from the analyst reports. Be specific — use exact prices.

SHORT SETUP REQUIREMENTS — all must be true to argue short:
{bear_req}

Target: {BEAR_SETUP['target']}
Stop: {BEAR_SETUP['stop']}
Invalidation: {BEAR_SETUP.get('invalidation', 'Price closes above swept high')}
  -> Price closes ABOVE the swept high = setup completely invalidated
  -> If invalidated mid-trade = exit immediately, do not wait

ANALYST REPORTS — use these as your evidence:
Market ICT Analysis:
{market_report}

Macro News Report:
{news_report}

Debate History So Far:
{history}

Long Setup Analyst Last Argument:
{current_response}

PAST LESSONS FROM SIMILAR NQ SHORT SETUPS:
{past_memory_str}

YOUR ARGUMENT MUST COVER ALL OF THESE:

1. HTF BIAS EVIDENCE
   - Is 4H/Daily structure bearish? Lower Highs and Lower Lows confirmed?
   - Is 4H price below 200 EMA? State exact EMA level.
   - Is 4H FVG bearish and unmitigated? State exact price range.
   - Is Supertrend bearish on 4H? State exact level.
   - Has there been a bearish CHoCH or BOS on 1H confirming order flow?
   - If ANY of these are bullish -> state NO SHORT SETUP and stop.

2. PREMIUM / DISCOUNT CONFIRMATION
   - Is price currently in PREMIUM zone? (above 50% fib / midnight open)
   - State exact Midnight Open price.
   - State exact 50% fib level.
   - If price is in DISCOUNT -> state NO SHORT SETUP — never sell discount.

3. LIQUIDITY SWEEP EVIDENCE
   - Has BUY-SIDE LIQUIDITY been swept today? Which level exactly?
   - Equal highs swept? Session high swept? PDH swept?
   - State exact price of the swept level.
   - How many points above the level did price go?
   - Did price reverse quickly? (quick = institutional, slow = weak)
   - If NO sweep yet -> state WAITING FOR SWEEP — do not enter yet.

3.5 SFP CONFIRMATION (JadeCap's #1 Signal)
   - Has a Swing Failure Pattern confirmed on 1H today?
   - Which swing HIGH was swept? State exact price.
   - Did the hourly candle CLOSE BACK INSIDE the range? YES/NO
   - How many points above the swing high did price go?
   - If NO SFP → state WAITING — cannot argue short without SFP confirmation
   - "Do not be the first person rushing through the door" — JadeCap

4. DISPLACEMENT CONFIRMATION
   - Was there a strong bearish displacement candle AFTER the sweep?
   - State the candle size in points.
   - Was it during a Kill Zone?
   - Body percentage — was it a full bodied candle (60%+ body)?
   - If no displacement -> state NO DISPLACEMENT — wait.

5. LTF ENTRY SETUP
   - ENTRY MODEL 0 — SFP (highest priority):
     Has a 1H SFP confirmed? If YES, this is the primary entry signal.
     Drop to 5m/15m for FVG or MSS entry WITHIN the SFP zone.
     SFP + FVG at same level = JadeCap's signature setup.
   - Is there a bearish FVG on 15m or 5m? State exact price range.
   - Is there a bearish OB on 15m? State exact price range.
   - Is there a Breaker Block? State exact level.
   - Which entry model has best confluence? FVG / OB / Breaker / OTE?

5b. STACKED FVGs CHECK
   - Is there a 4H FVG AND 1H FVG at the SAME price level?
   - If YES = HIGHEST CONFLUENCE zone — flag this clearly.
   - Stacked FVGs are the strongest setup in ICT — prioritize this entry.
   - If no stacked FVGs, note it and proceed with single-TF FVG.

5c. ADX FILTER
   - What is ADX value on 1H?
   - ADX above 25 = STRONG trending market = full size allowed.
   - ADX 20-25 = BORDERLINE = reduce to 50% contracts.
   - ADX below 20 = CHOPPY market = output NO TRADE — do not argue short.

5d. SILVER BULLET FVG CHECK
   - Did a FVG form specifically during Silver Bullet window?
   - Silver Bullet 1: 10:00-11:00 AM EST
   - Silver Bullet 2: 2:00-3:00 PM EST
   - A Silver Bullet FVG = highest probability FVG of the entire day.
   - If YES = state SILVER BULLET FVG CONFIRMED — strongest entry signal.
   - If NO = standard FVG still valid, just lower probability.

6. KILL ZONE TIMING
   Active Kill Zones:
{kz_str}
   - Are we inside a Kill Zone right now?
   - If Silver Bullet window (10-11 AM or 2-3 PM) -> highest probability.
   - If outside Kill Zone -> state WAIT FOR KILL ZONE.

7. DRAW ON LIQUIDITY TARGET
   - Where is price being drawn to today?
   - PDL below? Equal lows below? Session low below?
   - State exact target price.
   - Distance from entry to target in points.
   - Answer the 5 DOL questions:
     Q1: Market trending bearish (LH/LL)?
     Q2: Price in premium?
     Q3: BSL vulnerable to sweep (or already swept)?
     Q4: Unfilled bearish FVG on 4H/Daily above?
     Q5: NDOG/NWOG 50% CE level as resistance?
   - State the primary DOL target price and WHY

7.5 IPDA CONFLUENCE
   - Is the short target aligned with a 20/40/60-day delivery level?
   - Are we in a quarterly bearish delivery phase?
   - 20-day low below = intermediate target for shorts
   - 60-day low below = major quarterly target
   - If price is near 60-day high = deep premium, strong short case

8. RISK CALCULATION
   - Entry price: [exact level]
   - Stop loss: above candle 1 of bearish FVG or OB body [exact level]
   - Stop distance: [X] points
   - Contracts: {max_loss} / (stop_points x ${point_value}) = [X]
   - Target 1: nearest SSL [exact level]
   - Target 2: PDL [exact level]
   - R:R ratio: must be minimum {min_rr}:1
   - If R:R below {min_rr}:1 -> state INSUFFICIENT R:R — no trade.

8b. MULTI-TIMEFRAME CONFLUENCE SCORE
   - 4H bias direction: BULLISH / BEARISH
   - 1H order flow direction: BULLISH / BEARISH
   - 15m entry setup direction: BULLISH / BEARISH
   - All 3 agree = FULL CONFLUENCE = full calculated contracts.
   - 2 of 3 agree = PARTIAL CONFLUENCE = reduce to 50% contracts.
   - 1 of 3 agree = NO CONFLUENCE = NO TRADE — not enough confirmation.
   - State the score: FULL / PARTIAL / NONE.

9. MACRO NEWS ALIGNMENT
   - Does macro bias support SHORT? (risk-off, yields rising, hawkish Fed)
   - Is DXY strengthening? (DXY strengthening = bearish NQ — confirm this)
   - Are 10Y treasury yields rising? (rising yields = bearish NQ)
   - Any HIGH IMPACT news inside Kill Zone? If yes -> NO TRADE.
   - State macro alignment: SUPPORTS SHORT / CONFLICTS / NEUTRAL.

9.5 HOLIDAY / LOW-VOLUME CHECK
   - Check the News Analyst report for holiday warnings
   - If LOW VOLUME DAY flagged → state REDUCED CONFIDENCE
   - SFPs are unreliable on holidays — weight SFP evidence lower
   - If holiday: recommend HALF SIZE maximum regardless of A+ score

10. HARD RULE CHECKLIST — all 14 items, state PASS or FAIL:
   [1] HTF bias bearish: PASS/FAIL
   [2] Price in PREMIUM not discount: PASS/FAIL
   [3] Liquidity (BSL) swept: PASS/FAIL
   [4] Displacement candle present: PASS/FAIL
   [5] LTF PD Array identified (FVG/OB on 5m/15m): PASS/FAIL
   [6] Inside Kill Zone: PASS/FAIL
   [7] Minimum {min_rr}:1 R:R available: PASS/FAIL
   [8] PDL not already taken today: PASS/FAIL
   [9] Daily profit under $1000: PASS/FAIL
   [10] Daily loss under $500: PASS/FAIL
   [11] 1H SFP confirmed: PASS/FAIL
   [12] Draw on Liquidity identified: PASS/FAIL
   [13] A+ score calculated (min 4/10): PASS/FAIL
   [14] Not in midday chop zone (11:30-1:00): PASS/FAIL
   If ANY FAIL -> output NO SHORT SETUP

10.5 A+ SCORE CALCULATION (Weighted 1-10, max 10)
   [+2] HTF + LTF Alignment (all TFs bearish): YES/NO
   [+2] FVG at HTF POI (entry at 4H/Daily confluence): YES/NO
   [+2] Clear Liquidity Sweep (BSL raided before entry): YES/NO
   [+1] SFP Confirmed on 1H (swing high swept, candle closed back inside): YES/NO
   [+1] Price in Premium zone: YES/NO
   [+1] Inside Kill Zone or Silver Bullet: YES/NO
   [+1] 3R+ Available to target: YES/NO
   [-1] Conflicting Structure between entry and target: YES/NO
   [-1] High-Impact News within 30 min: YES/NO
   SCORE: X/10 → 8-10 Full Size / 6-7 Half Size / 4-5 Marginal / <4 No Trade

11. COUNTER THE LONG ANALYST
    - Read the long analyst argument carefully.
    - Address EVERY specific point they made.
    - Use exact ICT evidence to refute their bullish case.
    - Show why the short setup is stronger than their long setup.

AMD CONTEXT:
{AMD['manipulation']['action']}
{AMD['distribution']['action']}
- Did London raid BSL (highs)? If YES -> confirms bearish NY distribution.
- Is this the Distribution phase? If NO -> do not argue short yet.

HARD RULES — if ANY of these fail -> output NO SHORT SETUP:
{hard_rules_str}

PAST LESSONS — apply these to your argument:
{past_memory_str}

OUTPUT FORMAT (follow EXACTLY):
Short Setup Analyst:
## Current Price: [exact number from >>> CURRENT PRICE above]
Then cover each of the 11 points.

Then cover each of the 11 points above with specific evidence.
Use exact price levels from the market report.
Be conversational — debate the long analyst directly.
End with a VERDICT: SHORT VALID / NO SHORT SETUP

If NO SHORT SETUP — state exactly which requirement failed
and what needs to happen before a short is valid."""

        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history":          history + "\n" + argument,
            "bear_history":     bear_history + "\n" + argument,
            "bull_history":     investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "judge_decision":   investment_debate_state.get("judge_decision", ""),
            "count":            investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
