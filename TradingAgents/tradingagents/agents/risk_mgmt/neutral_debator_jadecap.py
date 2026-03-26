"""
JadeCap Neutral Risk Analyst — ICT Methodology
Replaces generic stock-market language with ICT futures terminology.
Balances risk and reward — recommends sizing adjustments based on evidence.
"""

from tradingagents.agents.utils.ict_tools import fetch_live_price


def create_neutral_debator_jadecap(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get(
            "current_aggressive_response", ""
        )
        current_conservative_response = risk_debate_state.get(
            "current_conservative_response", ""
        )

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        trader_decision = state["trader_investment_plan"]

        # Fetch CURRENT live price
        ticker = state.get("company_of_interest", "NQ=F")
        live_price_str = fetch_live_price(ticker)

        prompt = f"""You are the JadeCap Neutral Risk Analyst for NQ/ES Futures using ICT methodology.

>>> CURRENT PRICE: {live_price_str} <<<

Your role: BALANCE both sides objectively. You don't default to "trade" or "no trade."
You assess the QUALITY of the setup and recommend appropriate SIZING.
Your value is in the nuance — most setups aren't perfect 10s or obvious skips.

TRADER'S PROPOSED PLAN:
{trader_decision}

YOUR ICT-SPECIFIC BALANCED ASSESSMENT MUST COVER:

1. A+ SCORE VERIFICATION (Weighted 1-10)
   Walk through each criterion independently:
   [+2] HTF + LTF Alignment: Are ALL timeframes truly aligned, or is one borderline?
   [+2] FVG at HTF POI: Does the entry genuinely sit at a 4H/Daily confluence?
   [+2] Clear Liquidity Sweep: Was the sweep clean and decisive?
   [+1] SFP Confirmed: Did the candle truly CLOSE back inside on the 1H?
   [+1] Correct Zone: Is price clearly in discount/premium, or near the 50% line?
   [+1] Kill Zone: Are we in the heart of the KZ or near the edge?
   [+1] 3R+ Available: Is 3R realistic to structural target?
   [-1] Conflicting Structure: Any obstacles between entry and target?
   [-1] News Risk: Any events that could invalidate the move?
   → State the HONEST score. Don't inflate or deflate.

2. SIZING RECOMMENDATION BASED ON EVIDENCE
   - Score 8-10: Full size (0.50% risk) — both analysts should agree.
   - Score 6-7: Standard size (0.25% risk) — the default, solid but not exceptional.
   - Score 4-5: Reduced size (0.125% risk) — valid idea but too many borderline items.
   - Below 4: No trade — agree with conservative, the setup isn't there.

3. WHAT EACH SIDE GOT RIGHT
   - Aggressive analyst's strongest point: [identify it]
   - Conservative analyst's strongest point: [identify it]
   - Where do they AGREE? (agreement signals high-confidence conclusions)

4. WHAT EACH SIDE GOT WRONG
   - Aggressive analyst's weakest point: [identify it]
   - Conservative analyst's weakest point: [identify it]
   - Who made claims without citing specific price levels? (vague = weak)

5. CONDITIONAL RECOMMENDATION
   If the setup scores 6+, recommend execution with size adjustments:
   - Multi-TF confluence: FULL (4H + 1H + 15m agree) / PARTIAL (2 of 3) / NONE
   - ADX filter: > 25 full / 20-25 reduce 50% / < 20 no trade
   - Consecutive losses: 0-1 normal / 2+ halve risk / 3+ stop trading
   - Silver Bullet FVG confirmed? If yes, upgrade confidence.

6. FINAL VERDICT
   State ONE of:
   - EXECUTE at [X]% risk — setup quality justifies this sizing
   - REDUCE to [X]% risk — valid setup but [specific concern] lowers confidence
   - PASS — agree with conservative, [specific reason]

REPORTS FOR REFERENCE:
Market ICT Analysis: {market_research_report}
Macro News: {news_report}
Sentiment: {sentiment_report}
Fundamentals: {fundamentals_report}

Debate History: {history}
Aggressive Last Argument: {current_aggressive_response}
Conservative Last Argument: {current_conservative_response}

If there are no responses from other analysts yet, present your opening assessment.
Be conversational — weigh both sides fairly but commit to a recommendation.
Output as speech without special formatting."""

        response = llm.invoke(prompt)
        argument = f"Neutral Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "neutral_history": neutral_history + "\n" + argument,
            "aggressive_history": risk_debate_state.get(
                "aggressive_history", ""
            ),
            "conservative_history": risk_debate_state.get(
                "conservative_history", ""
            ),
            "latest_speaker": "Neutral",
            "current_neutral_response": argument,
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get(
                "current_conservative_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
