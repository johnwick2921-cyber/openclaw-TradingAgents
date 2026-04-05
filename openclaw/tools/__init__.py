"""Trading data tools — plain Python functions (no LangChain).

All tool functions, the ToolRegistry class, and registry registrations
live in this single file. Functions route to the configured data vendor
via openclaw.dataflows.interface.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Annotated, Any, Callable, Dict, List, Optional

import requests

from openclaw.dataflows.interface import route_to_vendor
from openclaw.indicators import get_indicator, get_indicators_batch, fetch_live_price

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Registry
# ═══════════════════════════════════════════════════════════════════════════════

def _build_context(ticker: str, date: str, config: Optional[dict] = None) -> dict:
    """Build standard context dict from ticker + date."""
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    return {
        "ticker": ticker,
        "date": date,
        "start_7d": (date_obj - timedelta(days=7)).strftime("%Y-%m-%d"),
        "start_30d": (date_obj - timedelta(days=30)).strftime("%Y-%m-%d"),
        "start_90d": (date_obj - timedelta(days=90)).strftime("%Y-%m-%d"),
        "config": config or {},
    }


class ToolRegistry:
    """Central registry for all callable tools in the trading pipeline."""

    def __init__(self):
        self._tools: Dict[str, dict] = {}

    def register(self, name: str, fn: Callable, param_builder: Callable[[dict], dict],
                 description: str = "", category: str = "general") -> None:
        self._tools[name] = {
            "fn": fn, "param_builder": param_builder,
            "description": description, "category": category,
        }

    def call(self, name: str, ticker: str, date: str, config: Optional[dict] = None) -> str:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not registered. Available: {list(self._tools.keys())}")
        tool = self._tools[name]
        ctx = _build_context(ticker, date, config)
        kwargs = tool["param_builder"](ctx)
        return tool["fn"](**kwargs)

    def call_many(self, names: List[str], ticker: str, date: str,
                  config: Optional[dict] = None) -> Dict[str, str]:
        results = {}
        def _call_one(name: str) -> tuple:
            try:
                return name, self.call(name, ticker, date, config)
            except KeyError:
                logger.warning("Tool '%s' not registered, skipping", name)
                return name, None
            except Exception as exc:
                logger.warning("Tool '%s' failed for %s: %s", name, ticker, exc)
                return name, f"[Data unavailable: {exc}]"
        with ThreadPoolExecutor(max_workers=min(len(names), 8)) as pool:
            futures = {pool.submit(_call_one, n): n for n in names}
            for future in as_completed(futures):
                name, result = future.result()
                if result is not None:
                    results[name] = result
        return results

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def list_by_category(self, category: str) -> List[str]:
        return [n for n, t in self._tools.items() if t["category"] == category]

    def get_info(self, name: str) -> Optional[dict]:
        tool = self._tools.get(name)
        if not tool:
            return None
        return {"name": name, "description": tool["description"], "category": tool["category"]}

    def describe_all(self) -> str:
        lines = []
        for name, tool in sorted(self._tools.items()):
            lines.append(f"- {name} [{tool['category']}]: {tool['description']}")
        return "\n".join(lines)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# Module-level singleton
registry = ToolRegistry()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Stock Data
# ═══════════════════════════════════════════════════════════════════════════════

def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve stock price data (OHLCV) for a given ticker symbol."""
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Technical Indicators
# ═══════════════════════════════════════════════════════════════════════════════

def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """Retrieve a single technical indicator for a given ticker symbol."""
    indicators = [i.strip() for i in indicator.split(",") if i.strip()]
    if len(indicators) > 1:
        results = []
        for ind in indicators:
            results.append(route_to_vendor("get_indicators", symbol, ind, curr_date, look_back_days))
        return "\n\n".join(results)
    return route_to_vendor("get_indicators", symbol, indicator.strip(), curr_date, look_back_days)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Fundamental Data
# ═══════════════════════════════════════════════════════════════════════════════

def get_fundamentals(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    """Retrieve comprehensive fundamental data for a given ticker symbol."""
    return route_to_vendor("get_fundamentals", ticker, curr_date)


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Retrieve balance sheet data for a given ticker symbol."""
    return route_to_vendor("get_balance_sheet", ticker, freq, curr_date)


def get_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Retrieve cash flow statement data for a given ticker symbol."""
    return route_to_vendor("get_cashflow", ticker, freq, curr_date)


def get_income_statement(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "reporting frequency: annual/quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Retrieve income statement data for a given ticker symbol."""
    return route_to_vendor("get_income_statement", ticker, freq, curr_date)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. News Data
# ═══════════════════════════════════════════════════════════════════════════════

def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve news data for a given ticker symbol."""
    return route_to_vendor("get_news", ticker, start_date, end_date)


def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
) -> str:
    """Retrieve global news data."""
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit)


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Retrieve insider transaction information about a company."""
    return route_to_vendor("get_insider_transactions", ticker)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Brave Web Search
# ═══════════════════════════════════════════════════════════════════════════════

_BRAVE_API_KEY = ""
try:
    _oc_path = os.path.join(
        os.environ.get("HOME", "/home/hoang"),
        ".openclaw", "openclaw.json",
    )
    with open(_oc_path) as _f:
        _oc = json.load(_f)
    _BRAVE_API_KEY = _oc.get("plugins", {}).get("entries", {}).get("brave", {}).get("config", {}).get("webSearch", {}).get("apiKey", "")
except Exception:
    pass


def brave_search(query: str, count: int = 10) -> str:
    """Search the web using Brave Search API."""
    if not _BRAVE_API_KEY:
        return "Brave Search unavailable — API key not configured"
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(count, 20)},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": _BRAVE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("web", {}).get("results", [])
        if not results:
            return f"No results found for: {query}"
        lines = [f"## Web Search: {query}\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            desc = r.get("description", "")
            url = r.get("url", "")
            age = r.get("age", "")
            lines.append(f"### {i}. {title}")
            if age:
                lines.append(f"*{age}*")
            if desc:
                lines.append(desc)
            if url:
                lines.append(f"Source: {url}")
            lines.append("")
        return "\n".join(lines)
    except requests.exceptions.Timeout:
        return f"Brave Search timed out for: {query}"
    except Exception as e:
        return f"Brave Search error: {e}"


def brave_news_search(ticker: str, date: str, config: dict = None) -> str:
    """Search for multi-source news headlines about a ticker."""
    futures = {"NQ", "MNQ", "ES", "MES", "YM", "RTY"}
    clean = ticker.upper().replace("=F", "").strip()
    if clean in futures:
        name_map = {"NQ": "Nasdaq", "ES": "S&P 500", "MNQ": "Nasdaq", "MES": "S&P 500", "YM": "Dow", "RTY": "Russell"}
        name = name_map.get(clean, clean)
        queries = [f"{name} futures today {date}", "stock market news today", "Federal Reserve economic news today"]
    else:
        queries = [f"{ticker} stock news today {date}", f"{ticker} earnings analyst rating", f"stock market {ticker} sentiment"]
    return "\n\n".join(brave_search(q, count=5) for q in queries)


def brave_social_search(ticker: str, date: str, config: dict = None) -> str:
    """Search for social media sentiment about a ticker."""
    clean = ticker.upper().replace("=F", "").strip()
    futures = {"NQ", "MNQ", "ES", "MES", "YM", "RTY"}
    if clean in futures:
        name_map = {"NQ": "Nasdaq NQ", "ES": "S&P ES", "MNQ": "Nasdaq", "MES": "S&P"}
        name = name_map.get(clean, clean)
        queries = [f"{name} futures reddit wallstreetbets today", f"{name} futures trader sentiment twitter"]
    else:
        queries = [f"{ticker} stock reddit wallstreetbets sentiment", f"{ticker} stock twitter sentiment retail traders"]
    return "\n\n".join(brave_search(q, count=5) for q in queries)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Agent Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder (backward compatibility)."""
        return {"messages": [{"role": "user", "content": "Continue"}]}
    return delete_messages


# ═══════════════════════════════════════════════════════════════════════════════
# 7. ICT Multi-Timeframe + Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_STOCK_INDICATORS = ["rsi", "macd", "macdh", "boll", "boll_ub", "boll_lb", "atr", "close_50_sma"]
_DEFAULT_ICT_INDICATORS = ["fvg", "order_blocks", "market_structure", "session_levels", "prev_day_levels"]

_ICT_INDICATORS_PER_TF = ["fvg", "order_blocks", "market_structure", "session_levels",
                           "prev_day_levels", "equal_highs_lows"]

_EXTRA_TF_INDICATORS = {
    "1H": ["sfp_detection", "displacement_candle"],
    "15m": ["liquidity_sweep", "breaker_block"],
    "5m": ["displacement_candle"],
}

# Only fetch the 2 most critical timeframes — 15m (entry) and 1H (structure)
# The 5-step process uses 4H/Daily for HTF bias but those come from get_stock_data
_JADECAP_TIMEFRAMES = ["15m", "1H"]


def _get_ict_all_timeframes(symbol: str, date: str) -> str:
    """Fetch ICT levels for ALL JadeCap timeframes in one call."""
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


def _killzone_wrapper(**kwargs):
    from openclaw.indicators import get_indicator as _get_ind
    return _get_ind("", "killzone_status", kwargs.get("date", "2026-01-01"))


def _contract_wrapper(**kwargs):
    from openclaw.indicators import get_contract_calc
    return get_contract_calc(kwargs.get("stop_points", 10))


def _midnight_wrapper(**kwargs):
    from openclaw.indicators import get_indicator as _get_ind
    return _get_ind(kwargs["symbol"], "midnight_open", kwargs["date"], timeframe="1m")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Registry — All Tool Registrations
# ═══════════════════════════════════════════════════════════════════════════════

# Stock data
registry.register(
    name="get_stock_data",
    fn=get_stock_data,
    param_builder=lambda ctx: {"symbol": ctx["ticker"], "start_date": ctx["start_30d"], "end_date": ctx["date"]},
    description="Fetch OHLCV price history (30 days)",
    category="stock",
)

# Unified indicators
registry.register(
    name="get_indicators",
    fn=get_indicators_batch,
    param_builder=_pick_indicators,
    description="Fetch technical indicators (stockstats + ICT from both packages)",
    category="technical",
)

# ICT levels — multi-timeframe
registry.register(
    name="get_ict_levels",
    fn=_get_ict_all_timeframes,
    param_builder=lambda ctx: {"symbol": ctx["ticker"], "date": ctx["date"]},
    description="Fetch ICT levels for ALL timeframes (5m/15m/1H/4H/1D)",
    category="technical",
)

# Intraday RSI
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

# Real-time data
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

# Brave web search
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

# ForexFactory calendar
def _get_forex_calendar(date: str = "", config: dict = None) -> str:
    from openclaw.tools.forex_calendar import load_calendar, get_no_entry_windows
    cal = load_calendar()
    if not cal or "events" not in cal:
        return "No forex calendar data — run: python3 -m openclaw.tools.forex_calendar"
    events = cal.get("events", [])
    if date:
        day_events = [e for e in events if e.get("date") == date]
    else:
        day_events = events
    if not day_events:
        return f"CLEAR — no RED US events for {date or 'this week'}"
    lines = [f"ForexFactory RED Events (US only) — {cal['week_start']} to {cal['week_end']}:"]
    for e in day_events:
        lines.append(f"  {e.get('day', '?'):10s} {e.get('date', '?')}  {e['time_est']:8s}  {e['event']}")
    windows = get_no_entry_windows(date) if date else []
    if windows:
        lines.append("\nNo-Entry Windows:")
        for w in windows:
            lines.append(f"  {w['start_est']} - {w['end_est']} EST ({w['event']})")
    return "\n".join(lines)

registry.register(
    name="get_forex_calendar",
    fn=_get_forex_calendar,
    param_builder=lambda ctx: {"date": ctx.get("date", "")},
    description="Get ForexFactory RED US events and news blackout windows for the week/day",
    category="news",
)
