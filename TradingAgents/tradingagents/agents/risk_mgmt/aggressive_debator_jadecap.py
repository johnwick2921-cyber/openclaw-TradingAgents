"""
JadeCap Aggressive Risk Analyst — ICT Methodology
Replaces generic stock-market language with ICT futures terminology.
Argues FOR taking the trade when ICT confluence is strong.
"""

from tradingagents.agents.utils.ict_tools import fetch_live_price


def create_aggressive_debator_jadecap(llm):
    def aggressive_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        aggressive_history = risk_debate_state.get("aggressive_history", "")

        current_conservative_response = risk_debate_state.get(
            "current_conservative_response", ""
        )
        current_neutral_response = risk_debate_state.get(
            "current_neutral_response", ""
        )

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        trader_decision = state["trader_investment_plan"]

        # Fetch CURRENT live price
        ticker = state.get("company_of_interest", "NQ=F")
        live_price_str = fetch_live_price(ticker)

        prompt = f"""You are the JadeCap Aggressive Risk Analyst for NQ/ES Futures using ICT methodology.

>>> CURRENT PRICE: {live_price_str} <<<

Your role: CHAMPION the trade when ICT confluence is strong. Argue FOR execution.
You push back against excessive caution that would cause missed A+ setups.

TRADER'S PROPOSED PLAN:
{trader_decision}

YOUR ICT-SPECIFIC ARGUMENTS MUST COVER:

1. SETUP CONFLUENCE STRENGTH
   - How many ICT confluences are stacked? (FVG + OB + OTE + SFP = maximum)
   - Is there a stacked FVG (4H + 1H at same level)? This is the strongest signal.
   - Did the Silver Bullet window produce a valid FVG? Highest probability of the day.
   - Is the A+ score 8+ out of 10? If yes, this justifies FULL SIZE execution.

2. INSTITUTIONAL FOOTPRINT EVIDENCE
   - Was the liquidity sweep decisive? Fast reversal = institutional absorption.
   - Is the displacement candle strong (60%+ body, large range)?
   - Are there multiple timeframe confirmations (4H + 1H + 15m all aligned)?
   - Does the FVG sit at a HTF point of interest? Double institutional footprint.

3. RISK-REWARD ASYMMETRY
   - If R:R is 3:1 or better, the math favors execution even with moderate win rate.
   - At 0.25% risk per trade, the downside is capped and known.
   - The prop firm absorbs the capital risk — personal capital not at stake.
   - Missing an A+ setup costs more long-term than taking a calculated loss.

4. COUNTER THE CONSERVATIVE ANALYST
   - Address each specific concern they raised with ICT evidence.
   - If they cite news risk, note that JadeCap trades POST-news structure, not the event.
   - If they cite wide stops, note that wider stops with fewer contracts = same dollar risk.
   - If they cite "choppy market," check ADX — above 25 confirms trending conditions.
   - Caution is not free — opportunity cost of sitting out A+ setups compounds.

5. COUNTER THE NEUTRAL ANALYST
   - If they suggest reducing size, argue that A+ setups (8+/10) deserve FULL SIZE.
   - "The best traders know how to size up on great trades" — JadeCap.
   - Half-sizing an A+ setup mathematically underperforms full-sizing over time.

REPORTS FOR REFERENCE:
Market ICT Analysis: {market_research_report}
Macro News: {news_report}
Sentiment: {sentiment_report}
Fundamentals: {fundamentals_report}

Debate History: {history}
Conservative Last Argument: {current_conservative_response}
Neutral Last Argument: {current_neutral_response}

If there are no responses from other analysts yet, present your opening argument.
Be conversational — debate directly, not formally. Use exact price levels.
Output as speech without special formatting."""

        response = llm.invoke(prompt)
        argument = f"Aggressive Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": aggressive_history + "\n" + argument,
            "conservative_history": risk_debate_state.get(
                "conservative_history", ""
            ),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Aggressive",
            "current_aggressive_response": argument,
            "current_conservative_response": risk_debate_state.get(
                "current_conservative_response", ""
            ),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return aggressive_node
