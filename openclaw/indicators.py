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
import os
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional

import pandas as pd

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
        return _get_stockstats(symbol, indicator, date, look_back_days, timeframe)
    elif indicator in SMC_INDICATORS:
        return _get_smc(symbol, indicator, date, timeframe)
    else:
        # Try stockstats first (it supports many more than our explicit set)
        try:
            return _get_stockstats(symbol, indicator, date, look_back_days, timeframe)
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

def _get_stockstats(symbol: str, indicator: str, date: str, look_back_days: int, timeframe: str = "1D") -> str:
    """Route to stockstats via the configured vendor.

    For intraday timeframes (5m, 15m, 1H, 4H), fetches intraday OHLCV
    and computes the indicator directly via stockstats, bypassing the
    daily-only vendor path.
    """
    if timeframe in ("1D", "1W") or not timeframe:
        # Daily path — use vendor routing (yfinance/databento/alpha_vantage)
        from openclaw.dataflows.interface import route_to_vendor
        return route_to_vendor("get_indicators", symbol, indicator, date, look_back_days)

    # Intraday path — fetch intraday bars, compute indicator locally
    df = _fetch_ohlcv_df(symbol, timeframe, date)
    if isinstance(df, str):
        return df  # error message
    if df is None or df.empty:
        return f"[No {timeframe} data for {symbol}]"

    try:
        import stockstats
        ss = stockstats.wrap(df.rename(columns={
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
        }))
        values = ss[indicator]
        # Return last N values
        n = min(20, len(values))
        tail = values.tail(n).dropna()
        if tail.empty:
            return f"[{indicator} on {timeframe}: no data after computation]"

        lines = [f"## {indicator} on {timeframe} (last {len(tail)} bars):\n"]
        for idx, val in tail.items():
            ts = idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, "strftime") else str(idx)
            lines.append(f"{ts}: {val:.4f}")

        # Add interpretation for RSI
        if indicator == "rsi" and len(tail) > 0:
            last_rsi = tail.iloc[-1]
            lines.append(f"\nCurrent {timeframe} RSI: {last_rsi:.1f}")
            if last_rsi > 70:
                lines.append("⚠ OVERBOUGHT (>70)")
            elif last_rsi < 30:
                lines.append("⚠ OVERSOLD (<30)")
            elif last_rsi > 60:
                lines.append("Bullish momentum")
            elif last_rsi < 40:
                lines.append("Bearish momentum")
            else:
                lines.append("Neutral zone")

        return "\n".join(lines)
    except Exception as exc:
        return f"[{indicator} on {timeframe} error: {exc}]"


# ─── Backend: smartmoneyconcepts ────────────────────────────────────────

def _get_smc(symbol: str, indicator: str, date: str, timeframe: str) -> str:
    """Route to smartmoneyconcepts ICT indicators."""
    df = _fetch_ohlcv_df(symbol, timeframe, date)
    if isinstance(df, str):
        return df  # error message
    if df is None or df.empty:
        return f"[No data available for {symbol} on {date}]"

    try:
        from openclaw.dataflows import ict_indicators as ict
        if ict.smc is None:
            return f"[smartmoneyconcepts not installed — pip install 'openclaw[ict]']"
    except ImportError:
        return f"[smartmoneyconcepts not installed — pip install 'openclaw[ict]']"

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

    try:
        return fn()
    except Exception as exc:
        return f"[{indicator} error: {exc}]"


# ─── Data fetching (moved from ict_tools.py) ─────────────────────────

def _get_configured_vendor() -> str:
    """Read data vendor from config singleton."""
    try:
        from openclaw.dataflows.config import get_config
        cfg = get_config()
        return cfg.get("data_vendors", {}).get("core_stock_apis", "yfinance")
    except Exception:
        return "yfinance"


def _fetch_ohlcv_df(symbol: str, timeframe: str, trade_date: str):
    """Fetch OHLCV and return as DataFrame. Used by ICT indicators."""
    vendor = _get_configured_vendor()

    # Calculate lookback based on timeframe — 400 bars per jadecap_config
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    lookback_map = {
        "1m": 3,      # 400 1m bars ≈ 6.7h → 3 calendar days
        "5m": 7,      # 400 5m bars ≈ 33h → 7 calendar days
        "15m": 14,    # 400 15m bars ≈ 100h → 14 calendar days
        "30m": 25,    # 400 30m bars ≈ 200h → 25 calendar days
        "1H": 45,     # 400 1H bars ≈ 400h → 45 calendar days
        "4H": 180,    # 400 4H bars ≈ 1600h → 180 calendar days
        "1D": 600,    # 400 daily bars → 600 calendar days
        "1W": 2800,   # 400 weekly bars → ~7.7 years
    }
    days_back = lookback_map.get(timeframe, 600)
    start_dt = end_dt - timedelta(days=days_back)
    # Databento Historical has ~15min delay. If trade_date is today,
    # use "now minus 20 min" as end to include today's bars.
    # If trade_date is in the past, add 1 day to capture full day.
    from datetime import timezone as _tz
    now = datetime.now(_tz.utc).replace(tzinfo=None)
    if end_dt.date() >= now.date():
        fetch_end = (now - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M")
    else:
        fetch_end = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        # Databento supports all timeframes natively
        if vendor == "databento":
            from openclaw.dataflows.databento_nq import get_databento_ohlcv
            csv_data = get_databento_ohlcv(
                symbol, start_dt.strftime("%Y-%m-%d"), fetch_end, timeframe=timeframe
            )
        elif timeframe not in ("1D", "1W"):
            # For intraday timeframes, try Databento first (it supports them),
            # then fall back to yfinance intraday if available
            databento_key = os.environ.get("DATABENTO_API_KEY", "")
            if not databento_key:
                try:
                    from openclaw.dataflows.config import get_config
                    databento_key = get_config().get("api_keys", {}).get("databento", "")
                except Exception:
                    pass
            if databento_key:
                from openclaw.dataflows.databento_nq import get_databento_ohlcv
                csv_data = get_databento_ohlcv(
                    symbol, start_dt.strftime("%Y-%m-%d"), fetch_end, timeframe=timeframe
                )
            else:
                # yfinance intraday fallback
                csv_data = _fetch_yfinance_intraday(symbol, timeframe, start_dt, end_dt)
        else:
            from openclaw.dataflows.interface import route_to_vendor
            csv_data = route_to_vendor(
                "get_stock_data", symbol, start_dt.strftime("%Y-%m-%d"), trade_date
            )
    except Exception as exc:
        return f"[Failed to fetch OHLCV for {symbol} {timeframe}: {exc}]"

    if not csv_data or csv_data.startswith("No data"):
        return None

    # Parse CSV
    lines = csv_data.split("\n")
    data_lines = [l for l in lines if not l.startswith("#")]
    df = pd.read_csv(StringIO("\n".join(data_lines)))
    if df.empty:
        return None

    # Normalize columns
    rename = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl in ("open", "high", "low", "close", "volume"):
            rename[c] = cl.capitalize()
    df = df.rename(columns=rename)

    # Set Date as index
    for col in ("Date", "date", "datetime"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df = df.set_index(col)
            break

    return df


def _fetch_yfinance_intraday(symbol: str, timeframe: str, start_dt, end_dt) -> str:
    """Fetch intraday OHLCV from yfinance as CSV string.

    yfinance supports: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h.
    Max lookback: 1m=7d, 5m/15m/30m=60d, 1h=730d.
    """
    import yfinance as yf

    tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1H": "60m", "4H": "60m"}
    yf_interval = tf_map.get(timeframe)
    if not yf_interval:
        return f"No data available for {symbol} at {timeframe} (yfinance does not support this interval)"

    futures = {"NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K", "CL", "GC"}
    clean = symbol.upper().replace("=F", "").strip()
    ticker_str = f"{clean}=F" if clean in futures else symbol

    hist = yf.Ticker(ticker_str).history(
        start=start_dt.strftime("%Y-%m-%d"),
        end=(end_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
        interval=yf_interval,
    )
    if hist.empty:
        return f"No data available for {symbol} at {timeframe}"

    # If 4H requested, resample from 1H
    if timeframe == "4H":
        hist = hist.resample("4h").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
        ).dropna()

    lines = [f"# {symbol} {timeframe} (yfinance intraday) | {len(hist)} bars"]
    lines.append("Date,Open,High,Low,Close,Volume")
    for idx, row in hist.iterrows():
        ts = idx.strftime("%Y-%m-%d %H:%M")
        lines.append(f"{ts},{row['Open']:.2f},{row['High']:.2f},{row['Low']:.2f},{row['Close']:.2f},{int(row['Volume'])}")
    return "\n".join(lines)


def fetch_live_price(symbol: str) -> str:
    """Fetch current live price for any instrument.

    Tries: Databento → yfinance fallback.
    """
    clean = symbol.upper().replace("=F", "").strip()

    # Get Databento API key: runtime config → JSON file → env var
    api_key = ""
    try:
        from openclaw.dataflows.config import get_config
        api_key = get_config().get("api_keys", {}).get("databento", "")
    except Exception:
        pass
    if not api_key:
        try:
            import json as _json
            cfg_path = os.path.join(
                os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace"),
                "trading-config.json",
            )
            with open(cfg_path) as _f:
                api_key = _json.load(_f).get("api_keys", {}).get("databento", "")
        except Exception:
            pass
    if not api_key:
        api_key = os.environ.get("DATABENTO_API_KEY", "")
    if api_key:
        # Live API — real-time price
        try:
            import databento as dbn
            logger.info("Databento Live: connecting for %s", clean)
            client = dbn.Live(key=api_key)
            client.subscribe(
                dataset="GLBX.MDP3",
                schema="mbp-1",
                stype_in="continuous",
                symbols=f"{clean}.c.0",
            )
            for rec in client:
                rtype = type(rec).__name__
                # Skip non-price messages
                if rtype in ("SystemMsg", "SymbolMappingMsg", "ErrorMsg", "InstrumentDefMsg"):
                    continue
                # MBP1Msg has price field
                if hasattr(rec, "price") and rec.price > 0:
                    price = rec.price * 1e-9
                    client.stop()
                    return f"CURRENT PRICE: {clean} = {price:.2f} (Databento Live)"
                # Some schemas have bid_px array
                if hasattr(rec, "bid_px"):
                    try:
                        bid = rec.bid_px[0] * 1e-9
                        ask = rec.ask_px[0] * 1e-9
                        mid = (bid + ask) / 2
                        client.stop()
                        return f"CURRENT PRICE: {clean} = {mid:.2f} (Databento Live, bid={bid:.2f} ask={ask:.2f})"
                    except (IndexError, TypeError):
                        pass
                break  # Unknown record type — fall through
            client.stop()
        except Exception as exc:
            logger.warning("Databento Live failed for %s: %s", clean, exc)

        # Historical fallback
        try:
            import databento as dbn
            from datetime import timezone
            client2 = dbn.Historical(key=api_key)
            end = datetime.now(timezone.utc) - timedelta(minutes=20)
            start = end - timedelta(minutes=10)
            records = list(client2.timeseries.get_range(
                dataset="GLBX.MDP3", schema="ohlcv-1m",
                symbols=[f"{clean}.c.0"], stype_in="continuous",
                start=start.strftime("%Y-%m-%dT%H:%M"),
                end=end.strftime("%Y-%m-%dT%H:%M"), limit=5,
            ))
            if records:
                price = records[-1].close / 1e9
                return f"CURRENT PRICE: {clean} = {price:.2f} (Databento, ~15min delayed)"
        except Exception:
            pass

    # Method 3: yfinance fallback
    try:
        import yfinance as yf
        futures = {"NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K"}
        ticker_str = f"{clean}=F" if clean in futures else clean
        hist = yf.Ticker(ticker_str).history(period="1d", interval="1m")
        if not hist.empty:
            return f"CURRENT PRICE: {clean} = {float(hist.iloc[-1]['Close']):.2f} (yfinance, delayed)"
    except Exception:
        pass

    return f"CURRENT PRICE: {clean} = unavailable"
