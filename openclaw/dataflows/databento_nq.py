"""Databento data vendor implementation for futures (NQ, ES, etc.).

Uses the Databento Historical API to fetch OHLCV data and compute
technical indicators via stockstats.
"""

import os
import logging
import warnings
from datetime import datetime, timedelta

import pandas as pd
import pytz

# Suppress Databento degraded data quality warnings
warnings.filterwarnings("ignore", module="databento")
warnings.filterwarnings("ignore", message=".*reduced quality.*")
warnings.filterwarnings("ignore", message=".*degraded.*")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    # Check trading-config.json first
    try:
        from openclaw.dataflows.config import get_config
        key = get_config().get("api_keys", {}).get("databento", "")
        if key:
            return key
    except Exception:
        pass
    # Fallback to env var
    key = os.environ.get("DATABENTO_API_KEY", "")
    if not key:
        raise ValueError(
            "Databento API key not set. Add it in Trading → Data Providers → API Keys, "
            "or set DATABENTO_API_KEY environment variable."
        )
    return key


def _symbol_to_databento(symbol: str) -> str:
    """Map common ticker symbols to Databento continuous contract symbols.

    Examples:
        NQ, NQ=F  -> NQ.FUT (front-month continuous)
        ES, ES=F  -> ES.FUT
        CL, CL=F  -> CL.FUT
    """
    clean = symbol.upper().replace("=F", "").strip()
    # Databento continuous contract format: ROOT.c.RANK
    # .c = calendar-based roll, .0 = front month
    # See: https://databento.com/docs/api-reference-historical/basics/symbology
    return f"{clean}.c.0"


def _databento_dataset(symbol: str) -> str:
    """Determine the Databento dataset for a given symbol."""
    clean = symbol.upper().replace("=F", "").strip()
    # CME Group symbols
    CME_SYMBOLS = {"NQ", "ES", "YM", "RTY", "GC", "SI", "HG", "CL", "NG", "MNQ", "MES"}
    if clean in CME_SYMBOLS:
        return "GLBX.MDP3"  # CME Globex
    # Default to CME
    return "GLBX.MDP3"


# Timeframe to Databento schema mapping
# Databento supports: ohlcv-1m, ohlcv-1h, ohlcv-1d ONLY (no 5m/15m/30m)
# Use native where available, aggregate from 1m for sub-hour timeframes
TIMEFRAME_SCHEMAS = {
    "1m":  "ohlcv-1m",     # native
    "5m":  "ohlcv-1m",     # aggregate 5x from 1m
    "15m": "ohlcv-1m",     # aggregate 15x from 1m
    "30m": "ohlcv-1m",     # aggregate 30x from 1m
    "1H":  "ohlcv-1h",     # native
    "4H":  "ohlcv-1h",     # aggregate 4x from native 1H
    "1D":  "ohlcv-1d",     # native
    "1W":  "ohlcv-1d",     # aggregate 7x from native 1D
}

# Fallback schema when native is unavailable (e.g., today's incomplete bar)
FALLBACK_SCHEMA = "ohlcv-1m"

# How many source bars to aggregate into one target bar
AGGREGATE_FACTOR = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1H": 1, "4H": 4, "1D": 1, "1W": 7,
}

# Fallback aggregation factors when falling back to ohlcv-1m
FALLBACK_AGG_FACTOR = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1H": 60, "4H": 240, "1D": 1440, "1W": 10080,
}


def _aggregate_ohlcv(df: pd.DataFrame, factor: int) -> pd.DataFrame:
    """Aggregate OHLCV bars by time-based resampling (same as backtest._agg).

    Uses pandas resample on actual timestamps — never row-based grouping,
    which misaligns candles across session gaps (e.g., 5-6 PM maintenance).
    """
    if factor <= 1:
        return df

    # Convert Date column to DatetimeIndex for proper time-based resampling
    if "Date" in df.columns:
        df = df.copy()
        df["_ts"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.set_index("_ts").sort_index()

    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }

    # Time-based resampling — same approach as backtest._agg
    rule = f"{factor}min"
    result = df.resample(rule).agg(agg).dropna(subset=["Close"])

    # Mark incomplete last candle — if it has fewer source bars than expected,
    # the OHLC values are partial. Keep it but flag it so the system knows.
    result["_complete"] = True
    if len(result) > 1:
        last_ts = result.index[-1]
        source_bars_in_last = len(df[(df.index >= last_ts) & (df.index < last_ts + pd.Timedelta(minutes=factor))])
        if source_bars_in_last < factor:
            result.iloc[-1, result.columns.get_loc("_complete")] = False

    # Restore Date column from index
    result["Date"] = result.index.strftime("%Y-%m-%d %H:%M")
    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# OHLCV Data
# ---------------------------------------------------------------------------

def get_databento_ohlcv(symbol: str, start_date: str, end_date: str, timeframe: str = "1D") -> str:
    """Fetch OHLCV data from Databento Historical API at any timeframe.

    Args:
        symbol: Ticker symbol (e.g., "NQ", "NQ=F", "ES")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        timeframe: Candle timeframe — "1m", "5m", "15m", "30m", "1H", "4H", "1D"

    Returns:
        CSV string with OHLCV data, matching yfinance output format.
    """
    import databento as db

    api_key = _get_api_key()
    client = db.Historical(api_key)

    db_symbol = _symbol_to_databento(symbol)
    dataset = _databento_dataset(symbol)
    schema = TIMEFRAME_SCHEMAS.get(timeframe, "ohlcv-1d")
    agg_factor = AGGREGATE_FACTOR.get(timeframe, 1)

    try:
        try:
            # Try native schema first (e.g., ohlcv-5m, ohlcv-15m, ohlcv-1h)
            data = client.timeseries.get_range(
                dataset=dataset,
                symbols=[db_symbol],
                schema=schema,
                start=start_date,
                end=end_date,
                stype_in="continuous",
            )
            df = data.to_df()
            logger.debug("Fetched %s natively for %s (%d bars)", schema, symbol, len(df))
        except Exception as schema_err:
            err_str = str(schema_err)
            # If native schema unavailable, fall back to ohlcv-1m + local aggregation
            if schema != FALLBACK_SCHEMA and (
                "not_fully_available" in err_str
                or "end_after_available" in err_str
                or "422" in err_str
            ):
                logger.info("Schema %s unavailable for %s, falling back to %s + aggregation", schema, symbol, FALLBACK_SCHEMA)
                data = client.timeseries.get_range(
                    dataset=dataset,
                    symbols=[db_symbol],
                    schema=FALLBACK_SCHEMA,
                    start=start_date,
                    end=end_date,
                    stype_in="continuous",
                )
                df = data.to_df()
                schema = FALLBACK_SCHEMA
                agg_factor = FALLBACK_AGG_FACTOR.get(timeframe, agg_factor)
            else:
                raise

        if df.empty:
            return f"No data found for symbol '{symbol}' (mapped to {db_symbol}) between {start_date} and {end_date}"

        # Normalize column names to match yfinance format
        df = df.reset_index()
        rename_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower == "open":
                rename_map[col] = "Open"
            elif col_lower == "high":
                rename_map[col] = "High"
            elif col_lower == "low":
                rename_map[col] = "Low"
            elif col_lower == "close":
                rename_map[col] = "Close"
            elif col_lower == "volume":
                rename_map[col] = "Volume"

        if rename_map:
            df = df.rename(columns=rename_map)

        # Ensure Date/Datetime column exists
        if "ts_event" in df.columns:
            ts = pd.to_datetime(df["ts_event"])
            # For intraday, keep full datetime; for daily, just date
            if timeframe in ("1D",):
                df["Date"] = ts.dt.strftime("%Y-%m-%d")
            else:
                df["Date"] = ts.dt.strftime("%Y-%m-%d %H:%M")
        elif df.index.name and "time" in df.index.name.lower():
            if timeframe in ("1D",):
                df["Date"] = df.index.strftime("%Y-%m-%d")
            else:
                df["Date"] = df.index.strftime("%Y-%m-%d %H:%M")

        # Select and order columns to match yfinance CSV format
        keep_cols = []
        for c in ["Date", "Open", "High", "Low", "Close", "Volume"]:
            if c in df.columns:
                keep_cols.append(c)

        if not keep_cols:
            return f"Data retrieved but could not parse columns. Available: {list(df.columns)}"

        df = df[keep_cols]

        # Aggregate if needed (e.g., 1m -> 5m, 1h -> 4h)
        if agg_factor > 1:
            df = _aggregate_ohlcv(df, agg_factor)

        # Daily resampling: group 1m bars into CME trading day bars
        # CME futures trading day: 5:00 PM ET (previous day) to 5:00 PM ET (current day)
        # Shift timestamps by 7 hours so 5PM ET aligns with midnight for .resample("D")
        if timeframe == "1D" and "Date" in df.columns:
            df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
            # Convert UTC to ET, then shift so 5PM ET = midnight
            et = pytz.timezone("US/Eastern") if "pytz" in dir() else None
            if et:
                df["_dt_et"] = df["_dt"].dt.tz_localize("UTC").dt.tz_convert(et).dt.tz_localize(None)
            else:
                df["_dt_et"] = df["_dt"] - pd.Timedelta(hours=5)  # rough UTC→ET
            # Shift by 7h so 5PM ET becomes midnight → resample("D") groups correctly
            df["_session"] = df["_dt_et"] + pd.Timedelta(hours=7)
            df = df.set_index("_session")
            daily = df.resample("D").agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }).dropna()
            daily["Date"] = daily.index.strftime("%Y-%m-%d")
            df = daily.reset_index(drop=True)

        # Weekly resampling: group daily bars into weekly bars
        if timeframe == "1W" and "Date" in df.columns:
            df["_dt"] = pd.to_datetime(df["Date"], errors="coerce")
            df = df.set_index("_dt")
            weekly = df.resample("W").agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }).dropna(subset=["Close"])
            weekly["Date"] = weekly.index.strftime("%Y-%m-%d")
            df = weekly.reset_index(drop=True)

        # Build CSV with header comment
        csv_str = df.to_csv(index=False)
        header = (
            f"# {symbol} {timeframe} (Databento {dataset}) | {start_date} to {end_date}\n"
            f"# Total bars: {len(df)} | Schema: {schema} | Aggregation: {agg_factor}x\n"
            f"# Source: Databento Historical API\n"
        )
        return header + csv_str

    except Exception as e:
        error_msg = str(e)
        if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
            return f"Databento authentication failed. Check your DATABENTO_API_KEY. Error: {error_msg}"
        elif "not found" in error_msg.lower() or "no data" in error_msg.lower():
            return f"No data found for {symbol} (mapped to {db_symbol}) on {dataset}. Error: {error_msg}"
        else:
            return f"Databento API error for {symbol}: {error_msg}"


def get_all_timeframes(symbol: str = "NQ", trade_date: str = None) -> dict:
    """Pull all JadeCap timeframes for a symbol. Returns dict of timeframe -> CSV string.

    Uses the TIMEFRAMES config from jadecap_config to determine lookback per timeframe.
    """
    from datetime import datetime, timedelta

    if trade_date is None:
        from datetime import timezone as _tz
        trade_date = datetime.now(_tz.utc).strftime("%Y-%m-%d")

    try:
        from openclaw.jadecap_config import TIMEFRAMES
    except ImportError:
        TIMEFRAMES = {
            "1m": {"lookback_bars": 400}, "5m": {"lookback_bars": 400},
            "15m": {"lookback_bars": 400}, "30m": {"lookback_bars": 400},
            "1H": {"lookback_bars": 400}, "4H": {"lookback_bars": 400},
            "1D": {"lookback_bars": 400}, "1W": {"lookback_bars": 400},
        }

    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    results = {}

    for tf, tf_config in TIMEFRAMES.items():
        lookback = tf_config.get("lookback_bars", 400)

        # Calculate start date to get `lookback` bars worth of data.
        # Multiply by calendar-to-trading ratio (~7/5 for weekdays,
        # plus buffer for holidays). Futures trade ~23h/day Sun-Fri.
        if tf == "1m":
            # 400 1m bars ≈ 6.7 trading hours ≈ 1 day, +1 buffer
            start_dt = end_dt - timedelta(days=3)
        elif tf == "5m":
            # 400 5m bars ≈ 33 trading hours ≈ ~2.5 days, +buffer
            start_dt = end_dt - timedelta(days=7)
        elif tf == "15m":
            # 400 15m bars ≈ 100 trading hours ≈ ~7 days, +buffer
            start_dt = end_dt - timedelta(days=14)
        elif tf == "30m":
            # 400 30m bars ≈ 200 trading hours ≈ ~13 days, +buffer
            start_dt = end_dt - timedelta(days=25)
        elif tf == "1H":
            # 400 1H bars ≈ 400 trading hours ≈ ~26 days, +buffer
            start_dt = end_dt - timedelta(days=45)
        elif tf == "4H":
            # 400 4H bars ≈ 1600 trading hours ≈ ~104 days, +buffer
            start_dt = end_dt - timedelta(days=180)
        elif tf == "1W":
            # 400 weekly bars ≈ 400 weeks ≈ ~7.7 years
            start_dt = end_dt - timedelta(weeks=lookback)
        else:  # 1D
            # 400 daily bars ≈ ~560 calendar days with weekends
            start_dt = end_dt - timedelta(days=int(lookback * 1.5))

        results[tf] = get_databento_ohlcv(
            symbol,
            start_dt.strftime("%Y-%m-%d"),
            end_dt.strftime("%Y-%m-%d"),
            timeframe=tf,
        )

    return results


# ---------------------------------------------------------------------------
# Technical Indicators
# ---------------------------------------------------------------------------

def get_databento_indicators(
    symbol: str, indicator: str, curr_date: str, look_back_days: int = 30
) -> str:
    """Calculate technical indicators from Databento OHLCV data using stockstats.

    Args:
        symbol: Ticker symbol
        indicator: Indicator name (e.g., "rsi", "macd", "close_50_sma")
        curr_date: Current date in YYYY-MM-DD format
        look_back_days: Number of days to look back for the indicator window

    Returns:
        Formatted string with date-value pairs.
    """
    from .stockstats_utils import _clean_dataframe
    import stockstats

    # Need extra historical data for indicators to warm up
    warmup_days = 250  # ~1 year for 200-day SMA
    end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=look_back_days + warmup_days)

    # Fetch OHLCV data from Databento
    csv_data = get_databento_ohlcv(symbol, start_dt.strftime("%Y-%m-%d"), curr_date)

    if csv_data.startswith("No data") or csv_data.startswith("Databento"):
        return csv_data  # Return error message as-is

    # Parse CSV (skip comment lines)
    lines = csv_data.split("\n")
    data_lines = [l for l in lines if not l.startswith("#")]
    csv_clean = "\n".join(data_lines)

    try:
        df = pd.read_csv(pd.io.common.StringIO(csv_clean))
    except Exception as e:
        return f"Failed to parse Databento data for indicator calculation: {e}"

    if df.empty:
        return f"No data available to calculate {indicator} for {symbol}"

    # Clean and prepare for stockstats
    df = _clean_dataframe(df)
    ss = stockstats.wrap(df)

    try:
        # Trigger indicator calculation
        _ = ss[indicator]
    except Exception as e:
        return f"Failed to calculate indicator '{indicator}' for {symbol}: {e}"

    # Extract the look_back_days window
    df["Date"] = df["Date"].astype(str) if "Date" in df.columns else df.index.astype(str)
    window_start = (end_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    result_lines = []
    for _, row in df.iterrows():
        date_str = str(row.get("Date", ""))[:10]
        if date_str >= window_start and date_str <= curr_date:
            val = row.get(indicator, None)
            if pd.isna(val):
                result_lines.append(f"{date_str}: N/A")
            else:
                result_lines.append(f"{date_str}: {val:.4f}")

    if not result_lines:
        return f"No {indicator} values found in the requested window for {symbol}"

    # Indicator descriptions
    INDICATOR_DESC = {
        "close_50_sma": "50-day Simple Moving Average of closing prices",
        "close_200_sma": "200-day Simple Moving Average of closing prices",
        "close_10_ema": "10-day Exponential Moving Average of closing prices",
        "macd": "Moving Average Convergence Divergence line",
        "macds": "MACD Signal line (9-day EMA of MACD)",
        "macdh": "MACD Histogram (MACD - Signal)",
        "rsi": "Relative Strength Index (14-period)",
        "boll": "Bollinger Bands middle band (20-day SMA)",
        "boll_ub": "Bollinger Bands upper band",
        "boll_lb": "Bollinger Bands lower band",
        "atr": "Average True Range (14-period)",
        "vwma": "Volume Weighted Moving Average",
    }
    desc = INDICATOR_DESC.get(indicator, f"Technical indicator: {indicator}")

    return "\n".join(result_lines) + f"\n\nIndicator: {desc}"


# ---------------------------------------------------------------------------
# News (delegates to yfinance — Databento doesn't provide news)
# ---------------------------------------------------------------------------

def get_databento_news(ticker: str, start_date: str, end_date: str) -> str:
    """Databento doesn't provide news — delegates to yfinance."""
    from .yfinance_news import get_news_yfinance
    return get_news_yfinance(ticker, start_date, end_date)


def get_databento_global_news(curr_date: str, look_back_days: int = 7, limit: int = 5) -> str:
    """Databento doesn't provide news — delegates to yfinance."""
    from .yfinance_news import get_global_news_yfinance
    return get_global_news_yfinance(curr_date, look_back_days, limit)


# ---------------------------------------------------------------------------
# Fundamentals (not applicable for futures — return helpful message)
# ---------------------------------------------------------------------------

def get_databento_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Futures don't have traditional fundamentals."""
    return (
        f"Fundamental data is not applicable for futures symbol {ticker}. "
        "Futures contracts are derivatives — they don't have P/E ratios, "
        "earnings, or balance sheets. For NQ futures, analyze the underlying "
        "Nasdaq-100 index components instead."
    )


def get_databento_balance_sheet(ticker: str, freq: str = "quarterly") -> str:
    return f"Balance sheet data is not applicable for futures symbol {ticker}."


def get_databento_cashflow(ticker: str, freq: str = "quarterly") -> str:
    return f"Cash flow data is not applicable for futures symbol {ticker}."


def get_databento_income_statement(ticker: str, freq: str = "quarterly") -> str:
    return f"Income statement data is not applicable for futures symbol {ticker}."


def get_databento_insider_transactions(ticker: str) -> str:
    return f"Insider transactions are not applicable for futures symbol {ticker}."
