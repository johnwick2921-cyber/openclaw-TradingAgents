"""Trading data tools — plain Python functions (no LangChain).

All tools auto-register with the global ToolRegistry on import.
One unified indicator system — no duplicate tool files.
"""

from openclaw.tools.agent_utils import build_instrument_context, create_msg_delete
from openclaw.tools.core_stock_tools import get_stock_data
from openclaw.tools.technical_indicators_tools import get_indicators
from openclaw.tools.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)
from openclaw.tools.news_data_tools import (
    get_news,
    get_global_news,
    get_insider_transactions,
)


# ─── Auto-register all tools with the global registry ───────────────────

from openclaw.tool_registry import registry
from openclaw.indicators import get_indicator, get_indicators_batch, fetch_live_price

# Default indicators per strategy
_DEFAULT_STOCK_INDICATORS = ["rsi", "macd", "macdh", "boll", "boll_ub", "boll_lb", "atr", "close_50_sma"]
_DEFAULT_ICT_INDICATORS = ["fvg", "order_blocks", "market_structure", "session_levels", "prev_day_levels"]

# ─── ICT indicators per timeframe (what market-analyst prompt asks for) ──
# The prompt requests get_ict_levels at 5m, 15m, 1H, 4H, 1D separately.
# We provide ALL timeframes in a single prefetch so the LLM gets complete data.

_ICT_INDICATORS_PER_TF = ["fvg", "order_blocks", "market_structure", "session_levels",
                           "prev_day_levels", "equal_highs_lows"]

# Additional per-timeframe indicators the agents reference
_EXTRA_TF_INDICATORS = {
    "1H": ["sfp_detection", "displacement_candle"],
    "15m": ["liquidity_sweep", "breaker_block"],
    "5m": ["displacement_candle"],
}

# All timeframes the JadeCap market analyst references
_JADECAP_TIMEFRAMES = ["5m", "15m", "1H", "4H", "1D"]


def _get_ict_all_timeframes(symbol: str, date: str) -> str:
    """Fetch ICT levels for ALL JadeCap timeframes in one call.

    Returns a combined report with sections per timeframe, so the LLM
    gets the data it would have gotten from 5 separate tool calls.
    """
    sections = []
    for tf in _JADECAP_TIMEFRAMES:
        indicators = list(_ICT_INDICATORS_PER_TF)
        indicators.extend(_EXTRA_TF_INDICATORS.get(tf, []))
        section_header = f"\n{'='*60}\n## ICT LEVELS — {tf} TIMEFRAME\n{'='*60}\n"
        try:
            result = get_indicators_batch(
                symbol=symbol, indicators=indicators, date=date, timeframe=tf,
            )
            sections.append(section_header + result)
        except Exception as exc:
            sections.append(section_header + f"[Error fetching {tf}: {exc}]")
    return "\n".join(sections)


def _get_intraday_rsi(symbol: str, date: str) -> str:
    """Fetch RSI on 5m timeframe for intraday momentum context."""
    try:
        return get_indicator(symbol, "rsi", date, timeframe="5m", look_back_days=5)
    except Exception as exc:
        return f"[5m RSI error: {exc}]"


def _pick_indicators(ctx):
    """Select which indicators to fetch based on strategy."""
    strategy = ctx.get("config", {}).get("strategy", "default")
    if strategy == "jadecap":
        indicators = _DEFAULT_ICT_INDICATORS + ["rsi", "atr"]
    else:
        indicators = _DEFAULT_STOCK_INDICATORS
    return {"symbol": ctx["ticker"], "indicators": indicators, "date": ctx["date"]}


# Stock data
registry.register(
    name="get_stock_data",
    fn=get_stock_data,
    param_builder=lambda ctx: {"symbol": ctx["ticker"], "start_date": ctx["start_30d"], "end_date": ctx["date"]},
    description="Fetch OHLCV price history (30 days)",
    category="stock",
)

# Unified indicators — one tool, routes to stockstats or smartmoneyconcepts
registry.register(
    name="get_indicators",
    fn=get_indicators_batch,
    param_builder=_pick_indicators,
    description="Fetch technical indicators (stockstats + ICT from both packages)",
    category="technical",
)

# ICT levels — multi-timeframe (5m, 15m, 1H, 4H, 1D) in one call
registry.register(
    name="get_ict_levels",
    fn=_get_ict_all_timeframes,
    param_builder=lambda ctx: {"symbol": ctx["ticker"], "date": ctx["date"]},
    description="Fetch ICT levels for ALL timeframes (5m/15m/1H/4H/1D) — FVG, OB, BOS/CHoCH, sessions, liquidity, SFP",
    category="technical",
)

# Intraday RSI (5-minute) — so agents can reference short-term momentum
registry.register(
    name="get_intraday_rsi",
    fn=_get_intraday_rsi,
    param_builder=lambda ctx: {"symbol": ctx["ticker"], "date": ctx["date"]},
    description="Fetch 5-minute RSI for intraday momentum",
    category="technical",
)

# Fundamentals
registry.register(
    name="get_fundamentals",
    fn=get_fundamentals,
    param_builder=lambda ctx: {"ticker": ctx["ticker"], "curr_date": ctx["date"]},
    description="Fetch comprehensive fundamental data",
    category="fundamental",
)
registry.register(
    name="get_balance_sheet",
    fn=get_balance_sheet,
    param_builder=lambda ctx: {"ticker": ctx["ticker"], "freq": "quarterly", "curr_date": ctx["date"]},
    description="Fetch quarterly balance sheet",
    category="fundamental",
)
registry.register(
    name="get_cashflow",
    fn=get_cashflow,
    param_builder=lambda ctx: {"ticker": ctx["ticker"], "freq": "quarterly", "curr_date": ctx["date"]},
    description="Fetch quarterly cash flow statement",
    category="fundamental",
)
registry.register(
    name="get_income_statement",
    fn=get_income_statement,
    param_builder=lambda ctx: {"ticker": ctx["ticker"], "freq": "quarterly", "curr_date": ctx["date"]},
    description="Fetch quarterly income statement",
    category="fundamental",
)

# News
registry.register(
    name="get_news",
    fn=get_news,
    param_builder=lambda ctx: {"ticker": ctx["ticker"], "start_date": ctx["start_30d"], "end_date": ctx["date"]},
    description="Fetch ticker-specific news",
    category="news",
)
registry.register(
    name="get_global_news",
    fn=get_global_news,
    param_builder=lambda ctx: {"curr_date": ctx["date"]},
    description="Fetch global market news",
    category="news",
)
registry.register(
    name="get_insider_transactions",
    fn=get_insider_transactions,
    param_builder=lambda ctx: {"ticker": ctx["ticker"]},
    description="Fetch insider trading activity",
    category="news",
)

# Real-time data (live price, killzone, contract size, midnight open)
registry.register(
    name="fetch_live_price",
    fn=fetch_live_price,
    param_builder=lambda ctx: {"symbol": ctx["ticker"]},
    description="Fetch current live price",
    category="realtime",
)
registry.register(
    name="get_live_price",
    fn=fetch_live_price,
    param_builder=lambda ctx: {"symbol": ctx["ticker"]},
    description="Fetch current live price (alias)",
    category="realtime",
)

# Killzone and contract size — use ICT indicators directly
def _killzone_wrapper(**kwargs):
    from openclaw.indicators import get_indicator
    return get_indicator("", "killzone_status", kwargs.get("date", "2026-01-01"))

def _contract_wrapper(**kwargs):
    from openclaw.dataflows.ict_indicators import get_contract_calc
    return get_contract_calc(kwargs.get("stop_points", 10))

def _midnight_wrapper(**kwargs):
    from openclaw.indicators import get_indicator
    return get_indicator(kwargs["symbol"], "midnight_open", kwargs["date"], timeframe="1m")

registry.register(
    name="get_killzone_status_tool",
    fn=_killzone_wrapper,
    param_builder=lambda ctx: {"date": ctx["date"]},
    description="Get current killzone status",
    category="realtime",
)
registry.register(
    name="get_contract_size",
    fn=_contract_wrapper,
    param_builder=lambda _: {"stop_points": 10},
    description="Get futures contract specifications",
    category="realtime",
)
registry.register(
    name="get_midnight_open_tool",
    fn=_midnight_wrapper,
    param_builder=lambda ctx: {"symbol": ctx["ticker"], "date": ctx["date"]},
    description="Fetch midnight open reference price",
    category="realtime",
)

# Brave web search — multi-source news headlines
from openclaw.tools.brave_search import brave_news_search, brave_social_search

registry.register(
    name="brave_news_search",
    fn=brave_news_search,
    param_builder=lambda ctx: {"ticker": ctx["ticker"], "date": ctx["date"]},
    description="Search web for multi-source news headlines (Brave API)",
    category="news",
)
registry.register(
    name="brave_social_search",
    fn=brave_social_search,
    param_builder=lambda ctx: {"ticker": ctx["ticker"], "date": ctx["date"]},
    description="Search web for social media sentiment (Reddit, Twitter)",
    category="news",
)
