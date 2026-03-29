"""Unified indicator interface — one entry point for both packages.

Routes indicator requests to the correct backend:
- Standard indicators (rsi, macd, boll, atr, sma, ema, etc.) → stockstats
- ICT indicators (fvg, order_blocks, market_structure, etc.) → smartmoneyconcepts

Usage:
    from openclaw.indicators import get_indicator, list_indicators

    # Standard
    result = get_indicator("NVDA", "rsi", "2026-03-28")

    # ICT
    result = get_indicator("NQ", "fvg", "2026-03-28", timeframe="15m")

    # All available
    list_indicators()  # ["rsi", "macd", ..., "fvg", "order_blocks", ...]
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Indicator catalog ──────────────────────────────────────────────────
# Maps indicator name → backend ("stockstats" or "smc")

STOCKSTATS_INDICATORS = {
    # Moving averages
    "close_50_sma", "close_200_sma", "close_10_ema",
    # MACD
    "macd", "macds", "macdh",
    # Momentum
    "rsi", "mfi",
    # Volatility
    "boll", "boll_ub", "boll_lb", "atr",
    # Volume
    "vwma",
}

SMC_INDICATORS = {
    # Smart Money Concepts (via smartmoneyconcepts package)
    "fvg",                # Fair Value Gaps
    "order_blocks",       # Order Blocks
    "session_levels",     # Session Highs/Lows (Asia/London/NY)
    "equal_highs_lows",   # Liquidity Pools (BSL/SSL)
    "market_structure",   # BOS/CHoCH
    "prev_day_levels",    # Previous day high/low
    "midnight_open",      # Midnight (6pm ET) open
    "killzone_status",    # Kill zone timer
    "fib_ote",            # Fibonacci OTE
    "math_indicators",    # SMC math patterns
    "ndog",               # New Day Open Gap
    "nwog",               # New Week Open Gap
    "sfp_detection",      # Sell-side Fair Price
    "displacement_candle",# Large displacement candles
    "liquidity_sweep",    # Liquidity sweep detection
    "breaker_block",      # Breaker blocks
    "amd_phase",          # Market phase analysis
}

ALL_INDICATORS = STOCKSTATS_INDICATORS | SMC_INDICATORS


def get_indicator(
    symbol: str,
    indicator: str,
    date: str,
    timeframe: str = "1D",
    look_back_days: int = 30,
) -> str:
    """Fetch a single indicator from the appropriate backend.

    Args:
        symbol: Ticker symbol (e.g., "NVDA", "NQ").
        indicator: Indicator name (e.g., "rsi", "fvg", "order_blocks").
        date: Trade date YYYY-MM-DD.
        timeframe: Candle timeframe for ICT indicators (default "1D").
        look_back_days: Lookback window for stockstats (default 30).

    Returns:
        Formatted string with indicator data.
    """
    indicator = indicator.strip().lower()

    if indicator in STOCKSTATS_INDICATORS:
        return _get_stockstats(symbol, indicator, date, look_back_days)
    elif indicator in SMC_INDICATORS:
        return _get_smc(symbol, indicator, date, timeframe)
    else:
        # Try stockstats first (it supports many more than our explicit set)
        try:
            return _get_stockstats(symbol, indicator, date, look_back_days)
        except Exception:
            return f"[Unknown indicator: {indicator}. Available: {', '.join(sorted(ALL_INDICATORS))}]"


def get_indicators_batch(
    symbol: str,
    indicators: list,
    date: str,
    timeframe: str = "1D",
    look_back_days: int = 30,
) -> str:
    """Fetch multiple indicators at once. Returns combined result string."""
    results = []
    for ind in indicators:
        try:
            result = get_indicator(symbol, ind, date, timeframe, look_back_days)
            results.append(f"--- {ind} ---\n{result}")
        except Exception as exc:
            results.append(f"--- {ind} ---\n[Error: {exc}]")
    return "\n\n".join(results)


def list_indicators() -> dict:
    """Return all available indicators grouped by backend."""
    return {
        "stockstats": sorted(STOCKSTATS_INDICATORS),
        "smartmoneyconcepts": sorted(SMC_INDICATORS),
    }


# ─── Backend: stockstats ────────────────────────────────────────────────

def _get_stockstats(symbol: str, indicator: str, date: str, look_back_days: int) -> str:
    """Route to stockstats via the configured vendor."""
    from openclaw.dataflows.interface import route_to_vendor
    return route_to_vendor("get_indicators", symbol, indicator, date, look_back_days)


# ─── Backend: smartmoneyconcepts ────────────────────────────────────────

def _get_smc(symbol: str, indicator: str, date: str, timeframe: str) -> str:
    """Route to smartmoneyconcepts ICT indicators."""
    from openclaw.tools.ict_tools import _get_ohlcv_df

    # Get OHLCV data for the indicator
    df = _get_ohlcv_df(symbol, timeframe, date)
    if df is None or df.empty:
        return f"[No data available for {symbol} on {date}]"

    from openclaw.dataflows import ict_indicators as ict

    dispatch = {
        "fvg": lambda: ict.get_fvg(df, timeframe),
        "order_blocks": lambda: ict.get_order_blocks(df, timeframe),
        "session_levels": lambda: ict.get_session_levels(df),
        "equal_highs_lows": lambda: ict.get_equal_highs_lows(df, timeframe),
        "market_structure": lambda: ict.get_market_structure(df, timeframe),
        "prev_day_levels": lambda: ict.get_prev_day_levels(df),
        "midnight_open": lambda: ict.get_midnight_open(df, date),
        "killzone_status": lambda: ict.get_killzone_status(),
        "fib_ote": lambda: ict.get_fib_ote(df, timeframe),
        "math_indicators": lambda: ict.get_math_indicators(df, timeframe),
        "ndog": lambda: str(ict.calc_ndog(df, date)),
        "nwog": lambda: str(ict.calc_nwog(df, date)),
        "sfp_detection": lambda: str(ict.calc_sfp_detection(df)),
        "displacement_candle": lambda: str(ict.calc_displacement_candle(df)),
        "liquidity_sweep": lambda: str(ict.calc_liquidity_sweep(df)),
        "breaker_block": lambda: str(ict.calc_breaker_block(df)),
        "amd_phase": lambda: str(ict.calc_amd_phase()),
    }

    fn = dispatch.get(indicator)
    if not fn:
        return f"[ICT indicator '{indicator}' not implemented]"

    return fn()
