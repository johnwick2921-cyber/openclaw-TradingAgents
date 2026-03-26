"""
JadeCap ICT LangChain Tool Wrappers
Wraps ict_indicators.py functions as @tools so the LLM can call them.

Save to: tradingagents/agents/utils/ict_tools.py
"""

import json
import logging
from typing import Annotated

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Lazy imports to avoid circular imports at module level
# ─────────────────────────────────────────────────────────────────────────────

def _get_config():
    from tradingagents.jadecap_config import JADECAP_CONFIG, INSTRUMENTS
    return JADECAP_CONFIG, INSTRUMENTS


def _get_configured_vendor():
    """Read data vendor from config singleton. Returns 'databento', 'yfinance', or 'alpha_vantage'."""
    try:
        from tradingagents.dataflows.config import get_config
        cfg = get_config()
        return cfg.get("data_vendors", {}).get("core_stock_apis", "yfinance")
    except Exception:
        return "yfinance"


def _get_ohlcv(symbol: str, start_date: str, end_date: str, timeframe: str = "1D"):
    vendor = _get_configured_vendor()
    if vendor == "databento":
        from tradingagents.dataflows.databento_nq import get_databento_ohlcv
        return get_databento_ohlcv(symbol, start_date, end_date, timeframe=timeframe)
    else:
        # Fall back to route_to_vendor for yfinance/alpha_vantage
        from tradingagents.dataflows.interface import route_to_vendor
        return route_to_vendor("get_stock_data", symbol, start_date, end_date)


def _get_ohlcv_df(symbol: str, timeframe: str, trade_date: str):
    """Fetch OHLCV and return as DataFrame."""
    vendor = _get_configured_vendor()
    from datetime import datetime, timedelta
    import pandas as pd
    from io import StringIO

    # Calculate lookback based on timeframe
    try:
        from tradingagents.jadecap_config import TIMEFRAMES
        lookback_bars = TIMEFRAMES.get(timeframe, {}).get("lookback_bars", 100)
    except ImportError:
        lookback_bars = 100

    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    # Timeframe-to-lookback-days mapping (mirrors TIMEFRAMES config in jadecap_config)
    if timeframe == "1m":
        start_dt = end_dt - timedelta(days=2)
    elif timeframe in ("5m", "15m"):
        start_dt = end_dt - timedelta(days=5)
    elif timeframe == "30m":
        start_dt = end_dt - timedelta(days=10)
    elif timeframe == "1H":
        start_dt = end_dt - timedelta(days=15)
    elif timeframe == "4H":
        start_dt = end_dt - timedelta(days=60)
    elif timeframe == "1W":
        start_dt = end_dt - timedelta(days=365)
    else:
        start_dt = end_dt - timedelta(days=lookback_bars)

    if vendor == "databento":
        from tradingagents.dataflows.databento_nq import get_databento_ohlcv
        csv_data = get_databento_ohlcv(
            symbol, start_dt.strftime("%Y-%m-%d"), trade_date, timeframe=timeframe
        )
    else:
        from tradingagents.dataflows.interface import route_to_vendor
        csv_data = route_to_vendor(
            "get_stock_data", symbol, start_dt.strftime("%Y-%m-%d"), trade_date
        )

    if not csv_data or csv_data.startswith("No data") or csv_data.startswith("Databento"):
        return None

    # Parse CSV, skip comment lines
    lines = csv_data.split("\n")
    data_lines = [l for l in lines if not l.startswith("#")]
    csv_clean = "\n".join(data_lines)

    df = pd.read_csv(StringIO(csv_clean))
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


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — get_ict_levels (per-timeframe analysis)
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_ict_levels(
    symbol: Annotated[str, "Ticker symbol e.g. NQ or NQ=F"],
    timeframe: Annotated[str, "Timeframe: 1m, 5m, 15m, 30m, 1H, 4H, 1D"],
    trade_date: Annotated[str, "Trade date YYYY-MM-DD"],
) -> str:
    """Get all ICT levels for a specific timeframe.

    Returns FVG, Order Blocks, Market Structure, Math indicators,
    Fibonacci OTE, Session levels, Liquidity pools, Previous Day H/L
    based on what's configured for this timeframe.

    Call sequence: 4H -> 1D -> 1H -> 15m -> 5m
    """
    try:
        from tradingagents.dataflows.ict_indicators import (
            get_fvg, get_order_blocks, get_session_levels,
            get_equal_highs_lows, get_market_structure,
            get_prev_day_levels, get_fib_ote, get_math_indicators,
        )
        from tradingagents.jadecap_config import TIMEFRAMES, ICT_INDICATORS, INSTRUMENTS

        config, instruments = _get_config()
        active = config["active_instrument"]
        instrument = instruments[active]

        df = _get_ohlcv_df(symbol, timeframe, trade_date)
        if df is None or df.empty:
            return f"No data for {symbol} on {timeframe} for {trade_date}"

        tf_config = TIMEFRAMES.get(timeframe, {})
        indicators = tf_config.get("indicators", [])

        sections = [
            f"\n{'='*55}",
            f"  ICT LEVELS — {symbol} {timeframe} | {trade_date}",
            f"  {active} | Point Value: ${instrument['point_value']}",
            f"{'='*55}",
        ]

        if "fvg" in indicators:
            sections.append(get_fvg(df, timeframe))
        if "order_blocks" in indicators:
            sections.append(get_order_blocks(df, timeframe))
        if "mss_choch" in indicators:
            sections.append(get_market_structure(df, timeframe))
        if "session_levels" in indicators:
            sections.append(get_session_levels(df))
        if "equal_highs_lows" in indicators:
            sections.append(get_equal_highs_lows(df, timeframe))
        if "prev_day_hl" in indicators:
            sections.append(get_prev_day_levels(df))
        if "fib_ote" in indicators:
            sections.append(get_fib_ote(df, timeframe))

        # Math indicators always
        sections.append(get_math_indicators(df, timeframe))

        # --- New JadeCap indicators ---
        try:
            from tradingagents.dataflows.ict_indicators import (
                calc_ndog, calc_nwog, calc_sfp_detection,
                calc_displacement_candle, calc_liquidity_sweep,
                calc_breaker_block, calc_amd_phase,
            )

            # NDOG
            ndog = calc_ndog(df, trade_date)
            if ndog and ndog.get("ce_50"):
                sections.append(f"\n--- NDOG (New Day Opening Gap) ---\n"
                              f"5PM Close: {ndog.get('close_5pm', 'N/A')}\n"
                              f"6PM Open: {ndog.get('open_6pm', 'N/A')}\n"
                              f"50% CE Level: {ndog.get('ce_50', 'N/A')}\n"
                              f"Gap Direction: {ndog.get('direction', 'N/A')}\n"
                              f"Gap Size: {ndog.get('gap_size_points', 'N/A')} points")

            # NWOG
            nwog = calc_nwog(df, trade_date)
            if nwog and nwog.get("ce_50"):
                sections.append(f"\n--- NWOG (New Week Opening Gap) ---\n"
                              f"Friday Close: {nwog.get('friday_close', 'N/A')}\n"
                              f"Sunday Open: {nwog.get('sunday_open', 'N/A')}\n"
                              f"50% CE Level: {nwog.get('ce_50', 'N/A')}\n"
                              f"Gap Direction: {nwog.get('direction', 'N/A')}\n"
                              f"Filled: {nwog.get('filled', 'N/A')}")

            # SFP Detection
            sfp = calc_sfp_detection(df)
            if sfp and sfp.get("status") != "no_sfp":
                sections.append(f"\n--- SFP Detection (Swing Failure Pattern) ---\n"
                              f"Status: {sfp.get('status', 'unknown')}\n"
                              f"Swing Highs: {len(sfp.get('swing_highs', []))}\n"
                              f"Swing Lows: {len(sfp.get('swing_lows', []))}\n"
                              f"Bullish SFPs: {len(sfp.get('bullish_sfps', []))}\n"
                              f"Bearish SFPs: {len(sfp.get('bearish_sfps', []))}")
                if sfp.get("latest_sfp"):
                    latest = sfp["latest_sfp"]
                    sections.append(f"Latest SFP: {latest}")

            # Displacement Candle
            disp = calc_displacement_candle(df)
            if disp and disp.get("latest"):
                d = disp["latest"]
                sections.append(f"\n--- Displacement Candle ---\n"
                              f"Direction: {d.get('direction', 'N/A')}\n"
                              f"Body %: {d.get('body_pct', 'N/A')}%\n"
                              f"Range: {d.get('range_points', 'N/A')} points\n"
                              f"Close: {d.get('close', 'N/A')}")

            # Liquidity Sweep
            sweep = calc_liquidity_sweep(df)
            if sweep and sweep.get("latest"):
                s = sweep["latest"]
                sections.append(f"\n--- Liquidity Sweep ---\n"
                              f"Type: {s.get('type', 'N/A').upper()}\n"
                              f"Swing Price: {s.get('swing_price', 'N/A')}\n"
                              f"Points Beyond: {s.get('points_beyond', 'N/A')}\n"
                              f"Close: {s.get('close', 'N/A')}")

            # Breaker Block
            bb = calc_breaker_block(df)
            if bb and bb.get("latest"):
                b = bb["latest"]
                sections.append(f"\n--- Breaker Block ---\n"
                              f"Type: {b.get('type', 'N/A')}\n"
                              f"OB High: {b.get('ob_high', 'N/A')}\n"
                              f"OB Low: {b.get('ob_low', 'N/A')}")

            # AMD Phase
            amd = calc_amd_phase()
            sections.append(f"\n--- AMD Phase ---\n"
                          f"Phase: {amd.get('phase', 'unknown').upper()}\n"
                          f"Session: {amd.get('session', 'unknown')}\n"
                          f"Action: {amd.get('action', '')}")
        except Exception as e:
            sections.append(f"\n[New indicators error: {e}]")

        return "\n".join(sections)

    except Exception as e:
        return f"Error getting ICT levels for {symbol} {timeframe}: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — get_killzone_status_tool
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_killzone_status_tool() -> str:
    """Check if current EST time is inside a JadeCap Kill Zone.

    Kill Zones (EST):
    - AM Kill Zone: 9:30-11:30
    - Silver Bullet 1: 10:00-11:00 (highest probability)
    - PM Kill Zone: 1:00-4:00
    - Silver Bullet 2: 2:00-3:00

    Returns active zone, AMD phase, and whether trading is allowed.
    HARD RULE: never enter outside a Kill Zone.
    """
    try:
        from tradingagents.dataflows.ict_indicators import get_killzone_status
        return get_killzone_status()
    except Exception as e:
        return f"Kill Zone check error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — get_midnight_open_tool
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_midnight_open_tool(
    symbol: Annotated[str, "Ticker symbol e.g. NQ or NQ=F"],
    trade_date: Annotated[str, "Trade date YYYY-MM-DD"],
) -> str:
    """Get the NY Midnight Open price (12:00 AM EST).

    Most important reference price for the trading day.
    Above = PREMIUM (shorts favored). Below = DISCOUNT (longs favored).
    RULE: Never buy in premium. Never sell in discount.
    """
    try:
        from tradingagents.dataflows.ict_indicators import get_midnight_open

        df = _get_ohlcv_df(symbol, "1m", trade_date)
        if df is None or df.empty:
            return f"No 1m data for midnight open on {trade_date}"

        return get_midnight_open(df, trade_date)

    except Exception as e:
        return f"Midnight Open error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 — get_multi_tf_levels (all timeframes at once)
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_multi_tf_levels(
    symbol: Annotated[str, "Ticker symbol e.g. NQ or NQ=F"],
    trade_date: Annotated[str, "Trade date YYYY-MM-DD"],
) -> str:
    """Get complete ICT analysis across ALL timeframes at once.

    Pulls 1m, 5m, 15m, 30m, 1H, 4H, 1D and runs full ICT report:
    Kill Zone, Midnight Open, Previous Day H/L, Session levels,
    HTF bias, Structure, Entry setup, Contract calculation.

    Use this for a complete one-shot analysis.
    Use get_ict_levels() for specific timeframe deep-dive.
    """
    try:
        from tradingagents.dataflows.ict_indicators import get_full_ict_report

        timeframes = ["1m", "5m", "15m", "30m", "1H", "4H", "1D"]
        dataframes = {}

        for tf in timeframes:
            try:
                df = _get_ohlcv_df(symbol, tf, trade_date)
                if df is not None and not df.empty:
                    dataframes[tf] = df
            except Exception:
                continue

        if not dataframes:
            return f"No data available for {symbol} on {trade_date}"

        return get_full_ict_report(dataframes, trade_date)

    except Exception as e:
        return f"Multi-timeframe analysis error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5 — get_contract_size
# ─────────────────────────────────────────────────────────────────────────────

@tool
def get_contract_size(
    stop_points: Annotated[float, "Stop loss distance in points"],
) -> str:
    """Calculate max contracts based on $500 max loss rule.

    NQ:  contracts = 500 / (stop_points x 20)
    MNQ: contracts = 500 / (stop_points x 2)

    Always use this before placing any trade.
    """
    try:
        from tradingagents.dataflows.ict_indicators import get_contract_calc
        return get_contract_calc(stop_points)
    except Exception as e:
        return f"Contract calculation error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 6 — get_live_price
# ─────────────────────────────────────────────────────────────────────────────


def fetch_live_price(symbol: str) -> str:
    """Fetch current price as a plain Python function (no @tool decorator).

    Use this from agent node functions to embed price into prompt text.
    Same logic as the @tool get_live_price but callable without LLM tool-calling.
    """
    import os
    import requests

    clean = symbol.upper().replace("=F", "").strip()

    # Method 1: WebUI live price endpoint (uses whatever data provider is in Settings)
    try:
        resp = requests.get(f"http://127.0.0.1:8000/api/prices/{clean}", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("price"):
                return (
                    f"CURRENT PRICE: {clean} = {data['price']:.2f} "
                    f"(source: {data.get('source', 'unknown')}, "
                    f"updated: {data.get('updated', 'N/A')})"
                )
    except Exception:
        pass

    # Method 2: Databento Historical
    api_key = os.environ.get("DATABENTO_API_KEY", "")
    if api_key:
        try:
            import databento as dbn
            from datetime import datetime, timedelta, timezone
            client = dbn.Historical(key=api_key)
            end = datetime.now(timezone.utc) - timedelta(minutes=15)
            start = end - timedelta(minutes=10)
            db_sym = f"{clean}.c.0"
            records = list(client.timeseries.get_range(
                dataset="GLBX.MDP3", schema="ohlcv-1m",
                symbols=[db_sym], stype_in="continuous",
                start=start.strftime("%Y-%m-%dT%H:%M"),
                end=end.strftime("%Y-%m-%dT%H:%M"), limit=5,
            ))
            if records:
                price = records[-1].close / 1e9
                return f"CURRENT PRICE: {clean} = {price:.2f} (Databento, 15min delayed)"
        except Exception:
            pass

    # Method 3: yfinance fallback
    try:
        import yfinance as yf
        ticker_str = f"{clean}=F" if clean in ("NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K") else clean
        hist = yf.Ticker(ticker_str).history(period="1d", interval="1m")
        if not hist.empty:
            return f"CURRENT PRICE: {clean} = {float(hist.iloc[-1]['Close']):.2f} (yfinance, delayed)"
    except Exception:
        pass

    return f"CURRENT PRICE: {clean} = unavailable"


@tool
def get_live_price(
    symbol: Annotated[str, "Ticker symbol — use the exact ticker from your analysis (e.g. NQ, MNQ, ES, AAPL, NVDA)"],
) -> str:
    """Get the CURRENT live price for any instrument.

    Returns the most recent price from live data stream or latest available data.
    Works for futures (NQ, ES, MNQ), stocks (AAPL, NVDA), or any supported ticker.
    Use this to determine where price is RIGHT NOW relative to your entry zones,
    targets, and stop levels.
    """
    try:
        import os
        import requests
        clean = symbol.upper().replace("=F", "").strip()

        # Method 1: Read from our own WebUI live price endpoint (same as dashboard ticker)
        try:
            resp = requests.get(f"http://127.0.0.1:8000/api/prices/{clean}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("price"):
                    source = data.get("source", "unknown")
                    return (
                        f"\n## CURRENT PRICE — {clean} (LIVE)\n"
                        f"  Price NOW: {data['price']:.2f}\n"
                        f"  Open: {data.get('open', 'N/A')}\n"
                        f"  High: {data.get('high', 'N/A')}\n"
                        f"  Low: {data.get('low', 'N/A')}\n"
                        f"  Change: {data.get('change', 0):+.2f} ({data.get('change_pct', 0):+.2f}%)\n"
                        f"  Volume: {data.get('volume', 'N/A')}\n"
                        f"  Source: {source}\n"
                        f"  Updated: {data.get('updated', 'N/A')}"
                    )
        except Exception as e:
            logger.debug("WebUI price server unavailable: %s", e)

        # Method 2: Direct Databento if server not available
        api_key = os.environ.get("DATABENTO_API_KEY", "")
        if api_key:
            try:
                import databento as dbn
                from datetime import datetime, timedelta, timezone
                client = dbn.Historical(key=api_key)
                end = datetime.now(timezone.utc) - timedelta(minutes=15)
                start = end - timedelta(minutes=10)
                db_sym = f"{clean}.c.0"
                data = client.timeseries.get_range(
                    dataset="GLBX.MDP3",
                    schema="ohlcv-1m",
                    symbols=[db_sym],
                    stype_in="continuous",
                    start=start.strftime("%Y-%m-%dT%H:%M"),
                    end=end.strftime("%Y-%m-%dT%H:%M"),
                    limit=10,
                )
                records = list(data)
                if records:
                    latest = records[-1]
                    price = latest.close / 1e9
                    return (
                        f"\n## CURRENT PRICE — {clean} (Databento)\n"
                        f"  Price NOW: {price:.2f}\n"
                        f"  Source: Databento Historical (15 min delayed)"
                    )
            except Exception as e:
                logger.debug("Databento historical price failed: %s", e)

        # Method 3: yfinance fallback
        try:
            import yfinance as yf
            ticker = f"{clean}=F" if clean in ("NQ", "MNQ", "ES", "MES", "YM", "MYM", "RTY", "M2K") else clean
            t = yf.Ticker(ticker)
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                last = hist.iloc[-1]
                return (
                    f"\n## CURRENT PRICE — {clean} (yfinance delayed)\n"
                    f"  Price NOW: {float(last['Close']):.2f}\n"
                    f"  Source: yfinance (15-20 min delayed)"
                )
        except Exception as e:
            logger.debug("yfinance price fallback failed: %s", e)

        return f"No price data available for {symbol}"
    except Exception as e:
        return f"Live price error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# TOOL LIST — import this in market_analyst_jadecap.py and trading_graph.py
# ─────────────────────────────────────────────────────────────────────────────

ICT_TOOLS = [
    get_ict_levels,
    get_killzone_status_tool,
    get_midnight_open_tool,
    get_multi_tf_levels,
    get_contract_size,
    get_live_price,
]
