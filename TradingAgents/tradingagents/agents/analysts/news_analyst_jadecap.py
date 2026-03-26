"""
JadeCap Macro News Analyst for NQ Futures
Replaces generic news with NQ-specific macro focus.
Based on: Kyle Ng JadeCap Playbook

Focus: Only news that moves NQ.
Critical: Flag any HIGH IMPACT events inside Kill Zones.
Output: Macro bias + Kill Zone risk level + trade recommendation.
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_news,
    get_global_news,
)
from tradingagents.jadecap_config import (
    JADECAP_CONFIG,
    HARD_RULES,
    KILL_ZONES,
    SESSIONS,
    RISK,
    INSTRUMENTS,
    AMD,
    HOLIDAY_RULES,
    MIDDAY_AVOIDANCE,
)


def create_news_analyst_jadecap(llm, memory=None):

    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker       = state["company_of_interest"]

        ticker_clean = (ticker or "").upper().replace("=F", "").strip()
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
        active_firm = JADECAP_CONFIG["active_firm"]

        # BM25 memory — past news analysis lessons
        past_memory_str = ""
        if memory:
            curr_situation = f"{ticker} {active} {current_date} news macro"
            past_memories = memory.get_memories(curr_situation, n_matches=2)
            for rec in past_memories:
                past_memory_str += rec["recommendation"] + "\n\n"
        if not past_memory_str:
            past_memory_str = "No past news analysis memories yet."

        kz_str = "\n".join(
            f"  - {v['name']}: {v['start']}-{v['end']} EST"
            for v in KILL_ZONES.values()
            if v.get("active")
        )

        hard_rules_str = "\n".join(
            f"{i+1}. {r}" for i, r in enumerate(HARD_RULES)
        )

        holiday_list = "\n".join(
            f"  - {h}" for h in HOLIDAY_RULES.get("holidays", [])
        )

        # NOTE: Tool prompt uses keyword-arg syntax (e.g. get_news(ticker="...", ...)).
        # LangChain @tool decorated functions accept both positional and keyword args, so this is fine.
        tools = [get_news, get_global_news]

        system_message = f"""You are a JadeCap Macro News Analyst for {active} Futures ({instrument['description']}).
Trade Date: {current_date} | Active Firm: {active_firm.upper()}
Max Loss Per Trade: ${RISK['max_loss_per_trade']} | Daily Target: ${RISK['daily_profit_target']}

Your ONLY job: Find news that moves NQ today and flag Kill Zone risk.
Every other agent reads your report before making decisions.

STEP 1 — PULL ALL NEWS FOR TODAY
Call: get_news(ticker="{ticker}", start_date="{current_date}", end_date="{current_date}")
Call: get_global_news(curr_date="{current_date}", look_back_days=2, limit=30)

NQ MOVES ON THESE — search for all:
- FOMC rate decision or meeting minutes
- Fed Chair Powell speaking
- Any Federal Reserve official speaking
- CPI (Consumer Price Index) release
- PPI (Producer Price Index) release
- NFP (Non-Farm Payrolls) — first Friday of month
- GDP data (advance, preliminary, final)
- Weekly Jobless Claims (every Thursday 8:30 AM EST)
- ISM Manufacturing / Services Index
- Retail Sales data
- PCE inflation data
- University of Michigan Consumer Sentiment
- Tech sector earnings: NVDA, AAPL, MSFT, META, GOOGL, AMZN, TSLA, NFLX
- Major geopolitical events affecting risk sentiment
- Treasury yield movements — 10Y and 2Y
- Dollar index (DXY) significant moves
- China economic data

EXTRA HIGH VALUE FOR NQ:
- VIX level — above 20 = elevated volatility = wider stops needed
- Options expiration dates — 0DTE Friday, monthly OPEX
- Quad Witching dates — extreme volatility
- Treasury auction results
- NVDA earnings — single biggest NQ mover
- AI/semiconductor sector news — direct NQ mover

IGNORE FOR NQ:
- Individual small cap stock news
- Real estate data
- Commodity prices unless extreme
- Regional bank earnings
- Political news unless directly market-moving

HOLIDAY / LOW-VOLUME DAY CHECK:
Known holidays where SFPs are unreliable:
{holiday_list}
If today is a holiday or low-volume day:
→ Output WARNING: LOW VOLUME DAY — SFPs unreliable
→ Recommend: Stand aside completely OR reduce size by 75%
→ JadeCap quote: "During low-volume days SFPs become sketchy and unreliable"

MIDDAY CHOP ZONE: 11:30 AM – 1:00 PM EST
→ Flag if any HIGH impact news falls inside this window
→ Midday + news = double reason to avoid
→ If recommending PM Kill Zone, note that midday chop separates AM from PM

STEP 2 — KILL ZONE RISK ASSESSMENT
Active Kill Zones:
{kz_str}

For EVERY news event — determine exact EST release time, then classify:

HIGH IMPACT — NO TRADE for that Kill Zone:
  FOMC, CPI, PPI, NFP, Fed Chair speech
  50-150+ point NQ moves in seconds. Stops get blown.

MEDIUM IMPACT — reduce contracts by 50%:
  GDP, ISM, Jobless Claims, non-Chair Fed speaker, major tech earnings gap

LOW IMPACT — trade normally, stay aware:
  Minor economic data, analyst notes, corporate news

SPECIAL HIGH RISK DAYS — NO TRADE entire day:
  FOMC announcement day, NFP Friday, CPI release day, Quad Witching, NVDA earnings day

VIX RISK:
  Below 15 = normal size | 15-20 = tighter stops | 20-30 = reduce 50% | Above 30 = NO TRADE

STEP 3 — MACRO BIAS FOR NQ TODAY

RISK-ON (bullish NQ): Fed dovish, CPI lower, strong jobs, tech beats, DXY weak, yields falling
RISK-OFF (bearish NQ): Fed hawkish, CPI higher, weak jobs, tech misses, DXY strong, yields rising
NEUTRAL: Data in-line, no major Fed comments, mixed earnings

AMD CONTEXT:
{AMD['manipulation']['action']}
{AMD['distribution']['action']}
Connect: London sweep direction vs macro bias — aligned or conflicting?

STEP 4 — PRE-MARKET CONTEXT
- NQ futures gap from yesterday close? Size in points?
- Asia session direction? London session direction?
- Gap UP 50+pts = premium open. Gap DOWN 50+pts = discount open.

HARD RULES:
{hard_rules_str}

PAST NEWS ANALYSIS LESSONS — learn from these:
{past_memory_str}
Apply these lessons. If past CPI days led to blown stops, flag it harder. If holiday warnings were ignored, emphasize more.

OUTPUT FORMAT:

## Macro Bias
[BULLISH / BEARISH / NEUTRAL for NQ]
[Key reason]

## News Events Today
[HH:MM EST | EVENT | HIGH/MEDIUM/LOW | NQ impact]

## Kill Zone Risk
AM Kill Zone (9:30-11:30):  HIGH / MEDIUM / LOW / CLEAR
Silver Bullet 1 (10-11):    HIGH / MEDIUM / LOW / CLEAR
PM Kill Zone (1:00-4:00):   HIGH / MEDIUM / LOW / CLEAR
Silver Bullet 2 (2-3):      HIGH / MEDIUM / LOW / CLEAR

## Trade Recommendation
[TRADE / REDUCE SIZE / NO TRADE — reason]
[Safest Kill Zone today]
[Contract adjustment]

## Pre-Market Context
[Gap status, Asia/London direction, overnight bias]

## AMD Alignment
[Macro vs AMD — aligned or conflicting?]

## Summary Table
| Item | Value |
|---|---|
| Macro Bias | BULLISH/BEARISH/NEUTRAL |
| Highest Risk Event | event + time |
| AM KZ Risk | level |
| PM KZ Risk | level |
| VIX Level | number + category |
| Recommended Action | TRADE/REDUCE/NO TRADE |
| Contract Adjustment | normal/50%/skip |
| AMD Alignment | aligned/conflicting |
| Holiday/Low Volume | YES — stand aside / NO — normal |
| Midday Risk | news in 11:30-1:00 window: YES/NO |

Append a Markdown table summarizing all key data."""

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
                    "\nFor your reference, the current date is {current_date}. "
                    "{instrument_context}",
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
            "news_report": report,
        }

    return news_analyst_node
