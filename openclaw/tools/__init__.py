"""Trading data tools — plain Python functions (no LangChain).

All tools auto-register with the global ToolRegistry on import.
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

# Lazy-import ICT tools to avoid heavy deps unless jadecap is used
def _register_ict_tools():
    from openclaw.tools.ict_tools import (
        get_ict_levels,
        fetch_live_price,
        get_midnight_open_tool,
        get_killzone_status_tool,
        get_contract_size,
        get_multi_tf_levels,
    )
    return {
        "get_ict_levels": get_ict_levels,
        "fetch_live_price": fetch_live_price,
        "get_live_price": fetch_live_price,  # alias
        "get_midnight_open_tool": get_midnight_open_tool,
        "get_killzone_status_tool": get_killzone_status_tool,
        "get_contract_size": get_contract_size,
        "get_multi_tf_levels": get_multi_tf_levels,
    }


# ─── Auto-register all tools with the global registry ───────────────────

from openclaw.tool_registry import registry

# Default indicators per strategy
_DEFAULT_STOCK_INDICATORS = ["rsi", "macd", "macdh", "boll", "boll_ub", "boll_lb", "atr", "close_50_sma"]
_DEFAULT_ICT_INDICATORS = ["fvg", "order_blocks", "market_structure", "session_levels", "prev_day_levels"]


# Stock data
registry.register(
    name="get_stock_data",
    fn=get_stock_data,
    param_builder=lambda ctx: {"symbol": ctx["ticker"], "start_date": ctx["start_30d"], "end_date": ctx["date"]},
    description="Fetch OHLCV price history (30 days)",
    category="stock",
)

# Unified indicators — one tool, routes to stockstats or smartmoneyconcepts
from openclaw.indicators import get_indicators_batch

def _pick_indicators(ctx):
    """Select which indicators to fetch based on strategy."""
    strategy = ctx.get("config", {}).get("strategy", "default")
    if strategy == "jadecap":
        indicators = _DEFAULT_ICT_INDICATORS + ["rsi", "atr"]
    else:
        indicators = _DEFAULT_STOCK_INDICATORS
    return {"symbol": ctx["ticker"], "indicators": indicators, "date": ctx["date"]}

registry.register(
    name="get_indicators",
    fn=get_indicators_batch,
    param_builder=_pick_indicators,
    description="Fetch technical indicators (stockstats + ICT from both packages)",
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

# Real-time data tools (NOT indicators — these are live data, contract info, etc.)
# Lazy-registered to avoid heavy imports unless jadecap strategy is active.
def _ensure_ict_registered():
    """Register ICT real-time data tools on first use."""
    if "fetch_live_price" in registry:
        return
    try:
        ict_tools = _register_ict_tools()
        registry.register(
            name="fetch_live_price",
            fn=ict_tools["fetch_live_price"],
            param_builder=lambda ctx: {"symbol": ctx["ticker"]},
            description="Fetch current live price",
            category="realtime",
        )
        registry.register(
            name="get_live_price",
            fn=ict_tools["get_live_price"],
            param_builder=lambda ctx: {"symbol": ctx["ticker"]},
            description="Fetch current live price (alias)",
            category="realtime",
        )
        registry.register(
            name="get_killzone_status_tool",
            fn=ict_tools["get_killzone_status_tool"],
            param_builder=lambda _: {},
            description="Get current killzone status",
            category="realtime",
        )
        registry.register(
            name="get_contract_size",
            fn=ict_tools["get_contract_size"],
            param_builder=lambda _: {},
            description="Get futures contract specifications",
            category="realtime",
        )
        # get_ict_levels = convenience alias that fetches full ICT report via unified indicators
        from openclaw.indicators import get_indicators_batch
        registry.register(
            name="get_ict_levels",
            fn=get_indicators_batch,
            param_builder=lambda ctx: {
                "symbol": ctx["ticker"], "date": ctx["date"],
                "indicators": ["fvg", "order_blocks", "market_structure", "session_levels",
                               "prev_day_levels", "equal_highs_lows"],
            },
            description="Fetch all ICT levels (via unified indicator system)",
            category="technical",
        )
        registry.register(
            name="get_midnight_open_tool",
            fn=ict_tools["get_midnight_open_tool"],
            param_builder=lambda ctx: {"symbol": ctx["ticker"], "trade_date": ctx["date"]},
            description="Fetch midnight open reference price",
            category="realtime",
        )
    except ImportError:
        pass  # ICT deps not installed
