"""
JadeCap Conservative Risk Analyst — ICT Methodology
Replaces generic stock-market language with ICT futures terminology.
Argues for CAUTION — protects the prop firm account from marginal setups.
"""

from tradingagents.agents.utils.ict_tools import fetch_live_price


def create_conservative_debator_jadecap(llm):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get(
            "current_aggressive_response", ""
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

        prompt = f"""You are the JadeCap Conservative Risk Analyst for NQ/ES Futures using ICT methodology.

>>> CURRENT PRICE: {live_price_str} <<<

Your role: PROTECT the prop firm account. Challenge marginal setups ruthlessly.
You are the last line of defense against overtrading and blown accounts.
JadeCap's edge is SELECTIVITY — $4.5M came from passing on 90% of setups.

TRADER'S PROPOSED PLAN:
{trader_decision}

YOUR ICT-SPECIFIC RISK ASSESSMENT MUST COVER:

1. CHECKLIST COMPLIANCE — ANY FAILURE = NO TRADE
   - Did ALL 14 checklist items pass? Which ones are borderline?
   - Is the SFP truly confirmed (hourly candle CLOSED back inside)?
   - Is the displacement candle real (60%+ body) or a weak doji?
   - Is the FVG in the correct zone (discount for longs, premium for shorts)?
   - A single failed checklist item means NO TRADE — no exceptions.

2. STRUCTURAL RISK — WHAT CAN GO WRONG
   - Are there unfilled FVGs between entry and target that could stall the move?
   - Is there unswept liquidity (equal H/L) between entry and target?
   - Is ADX below 20? If yes, market is CHOPPY — NO TRADE regardless of setup.
   - Is the stop behind proper structure or arbitrarily tight?
   - Could the stop get hunted before the move? (check for nearby liquidity pools)

3. TIMING AND SESSION RISK
   - Are we inside a valid Kill Zone? If borderline (near end), skip.
   - Is midday chop (11:30-1:00 EST) approaching? Exit or don't enter.
   - Is there enough time before 4:00 PM hard close for T1 to be reached?
   - Is this the FIRST trade this Kill Zone? If already took a loss, window is CLOSED.

4. NEWS AND MACRO RISK
   - HIGH impact events (FOMC, CPI, NFP) within 30 min = NO TRADE.
   - Is today a holiday or low-volume day? SFPs are "sketchy and unreliable."
   - Is DXY moving against the trade direction?
   - VIX above 20? Wider stops needed. Above 30? NO TRADE.

5. PROP FIRM ACCOUNT PROTECTION
   - After 2 consecutive losses: risk must be HALVED.
   - After 3 consecutive losses: STOP TRADING for the day.
   - Is daily P&L near the $500 loss limit? If yes, NO MORE TRADES.
   - Is daily profit already at $1,000? LOCK IN and stop.
   - The trailing drawdown is the account killer — protect it above all.

6. COUNTER THE AGGRESSIVE ANALYST
   - "Missing a setup" costs nothing. A blown account costs everything.
   - Challenge their R:R calculation — is the target realistic or optimistic?
   - If they cite "stacked confluence," verify each layer independently.
   - Remind: JadeCap's record came from DISCIPLINE, not from taking every setup.

REPORTS FOR REFERENCE:
Market ICT Analysis: {market_research_report}
Macro News: {news_report}
Sentiment: {sentiment_report}
Fundamentals: {fundamentals_report}

Debate History: {history}
Aggressive Last Argument: {current_aggressive_response}
Neutral Last Argument: {current_neutral_response}

If there are no responses from other analysts yet, present your opening argument.
Be conversational — debate directly, challenge specific claims with evidence.
Output as speech without special formatting."""

        response = llm.invoke(prompt)
        argument = f"Conservative Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "conservative_history": conservative_history + "\n" + argument,
            "aggressive_history": risk_debate_state.get(
                "aggressive_history", ""
            ),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_conservative_response": argument,
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
