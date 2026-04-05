"""JadeCap Backtester — simulates daily trading with entry/exit tracking.

Usage:
    python3 -m openclaw.backtest --days 20
    python3 -m openclaw.backtest --start 2025-04-03 --end 2026-04-02

Flow per day:
  1. 8:00 AM ET — fetch overnight + pre-market data, determine daily bias
  2. AM Kill Zone (9:30-11:30) — scan for valid setup, enter if found
  3. Track trade: T1 partial close (50%), stop to BE, runner to T2 (3R)
  4. If no AM trade, try PM Kill Zone (13:00-16:00)
  5. Hard close 16:00 — exit any open position
  6. Record W/L/BE and P&L

No AI calls — pure rule-based using ICT indicator data.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from io import StringIO

import pandas as pd
import numpy as np


# ── Config (aligned with jadecap_config.py RISK section) ────────────
POINT_VALUE = 2   # MNQ $2/point (Micro Nasdaq)
MAX_LOSS = 500    # $500 max loss per trade — enforced dynamically
FIXED_CONTRACTS = 5  # Base contract count (scaled by --scale)
MAX_CONTRACTS = 140  # Cap for progressive scaling (140 MNQ = 14 NQ for $150K accounts)
DAILY_LOSS_CAP = 500   # Stop trading after $500 daily loss
DAILY_PROFIT_CAP = 1000  # Lock in after $1000 daily profit
CONSEC_LOSS_HALF = 2  # Half size after 2 consecutive losses
CONSEC_LOSS_HALT = 3  # Stop trading for the day after 3 consecutive losses
T1_CLOSE_PCT = 0.5  # Close 50% at T1 (first liquidity pool)
T1_RR = 1.5        # T1 target = 1.5R
T2_RR = 3.0        # T2 target = 3R (runner)
HARD_CLOSE = "16:00"  # JCAP: hard close at 4:00 PM EST
COMMISSION_PER_CONTRACT = 0.54  # $0.54 per side per MNQ contract (round trip = $1.08)
SLIPPAGE_PTS = 1  # 1 point slippage per entry + exit (conservative estimate)

KILL_ZONES = {
    "AM":  ("09:30", "11:30"),
    "PM":  ("13:00", "16:00"),
}


def _fetch_day(ticker: str, date: str) -> Optional[pd.DataFrame]:
    """Fetch 1-minute OHLCV for a single day via Databento."""
    try:
        from openclaw.dataflows.databento_nq import get_databento_ohlcv
        dt = datetime.strptime(date, "%Y-%m-%d")
        end_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        csv_str = get_databento_ohlcv(ticker, date, end_date, "1m")
        if not csv_str or "Error" in csv_str[:100] or "error" in csv_str[:100]:
            return None
        lines = [l for l in csv_str.strip().split("\n") if not l.startswith("#")]
        if len(lines) < 2:
            return None
        df = pd.read_csv(StringIO("\n".join(lines)))
        df.columns = [c.lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        df.index = df.index.tz_localize(et)
        return df
    except Exception as exc:
        print(f"  [WARN] {ticker} {date}: {exc}", file=sys.stderr)
        return None


def _fetch_bulk(ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """Fetch ALL 1-minute OHLCV in one call. One fetch, all indicators."""
    try:
        from openclaw.dataflows.databento_nq import get_databento_ohlcv
        print(f"  Fetching {ticker} 1m data: {start_date} → {end_date} ...", flush=True)
        csv_str = get_databento_ohlcv(ticker, start_date, end_date, "1m")
        if not csv_str or "Error" in csv_str[:100] or "error" in csv_str[:100]:
            return None
        lines = [l for l in csv_str.strip().split("\n") if not l.startswith("#")]
        if len(lines) < 2:
            return None
        df = pd.read_csv(StringIO("\n".join(lines)))
        df.columns = [c.lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        if df.index.tz is None:
            df.index = df.index.tz_localize(et)
        print(f"  Loaded {len(df):,} bars ({df.index[0].date()} → {df.index[-1].date()})", flush=True)
        return df
    except Exception as exc:
        print(f"  [ERROR] Bulk fetch {ticker}: {exc}", file=sys.stderr)
        return None


def _precompute_indicators(df_all: pd.DataFrame) -> dict:
    """Pre-compute all indicators on the full dataset at once.

    Returns dict with daily, 1H, 5m, 15m aggregations and indicator values.
    """
    indicators = {}

    # Multi-timeframe aggregations
    indicators["1m"] = df_all
    indicators["5m"] = _agg(df_all, 5)
    indicators["15m"] = _agg(df_all, 15)
    indicators["1h"] = _agg(df_all, 60)
    indicators["4h"] = _agg(df_all, 240)
    indicators["1d"] = _agg(df_all, 1440)

    # Use stockstats for ALL indicators — same library as indicators.py
    import stockstats
    df_d = indicators["1d"]
    df_1h = indicators["1h"]

    def _ss(df):
        """Wrap DataFrame for stockstats — same as indicators.py does."""
        return stockstats.wrap(df.rename(columns={c: c.lower() for c in df.columns}).copy())

    # Daily indicators
    if len(df_d) >= 14:
        ss_d = _ss(df_d)
        indicators["daily_atr"] = ss_d["atr"]
        if len(df_d) >= 200:
            indicators["ema_200"] = ss_d["close_200_ema"]
        elif len(df_d) >= 50:
            indicators["ema_200"] = ss_d["close_50_ema"]

    # 1H indicators
    if len(df_1h) >= 50:
        ss_1h = _ss(df_1h)
        indicators["1h_ema_9"] = ss_1h["close_9_ema"]
        indicators["1h_ema_50"] = ss_1h["close_50_ema"]

    print(f"  Indicators: {len(indicators['1d'])} daily, {len(indicators['1h'])} 1H, "
          f"{len(indicators['5m'])} 5m bars", flush=True)

    return indicators


def _agg(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    return df.resample(f"{minutes}min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
    }).dropna()



def _detect_1h_sfp(df_1h: pd.DataFrame, direction: str) -> Optional[dict]:
    """Detect 1H Swing Failure Pattern — JadeCap's #1 signal.

    SFP: A 1H candle sweeps a prior swing high/low and CLOSES BACK INSIDE
    the prior range, trapping breakout traders.

    Long SFP: 1H candle wicks below a prior swing low but closes above it.
    Short SFP: 1H candle wicks above a prior swing high but closes below it.
    """
    if len(df_1h) < 5:
        return None

    highs = df_1h["high"].values
    lows = df_1h["low"].values

    swing_highs = []
    swing_lows = []
    for j in range(1, len(df_1h) - 1):
        if highs[j] > highs[j - 1] and highs[j] > highs[j + 1]:
            swing_highs.append((j, highs[j]))
        if lows[j] < lows[j - 1] and lows[j] < lows[j + 1]:
            swing_lows.append((j, lows[j]))

    last_idx = len(df_1h) - 1
    last_candle = df_1h.iloc[last_idx]
    last_ts = df_1h.index[last_idx]

    # Minimum penetration: wick must go at least 3 pts past the swing level
    # to confirm a real liquidity sweep (not just noise)
    MIN_SFP_PENETRATION = 3.0

    if direction == "long" and swing_lows:
        for _, sw_low in reversed(swing_lows):
            penetration = sw_low - last_candle["low"]
            if penetration >= MIN_SFP_PENETRATION and last_candle["close"] > sw_low:
                return {
                    "time": last_ts,
                    "sfp_type": "long",
                    "swing_level": sw_low,
                    "sweep_price": float(last_candle["low"]),
                    "close_price": float(last_candle["close"]),
                }
    elif direction == "short" and swing_highs:
        for _, sw_high in reversed(swing_highs):
            penetration = last_candle["high"] - sw_high
            if penetration >= MIN_SFP_PENETRATION and last_candle["close"] < sw_high:
                return {
                    "time": last_ts,
                    "sfp_type": "short",
                    "swing_level": sw_high,
                    "sweep_price": float(last_candle["high"]),
                    "close_price": float(last_candle["close"]),
                }

    return None


def _midnight_open(df: pd.DataFrame) -> Optional[float]:
    mc = df.between_time("00:00", "00:01")
    if not mc.empty:
        return float(mc.iloc[0]["open"])
    return float(df.iloc[0]["open"]) if not df.empty else None


def _daily_bias(df_daily: pd.DataFrame) -> str:
    """Determine daily bias from the daily chart — JadeCap aligned.

    Checks recent daily candles for:
    - Market Structure Shift (MSS): break of prior swing H/L
    - Liquidity sweep: wick beyond prior level + close back inside
    - Direction: where price is heading today

    Returns: "bullish", "bearish", or "unclear"
    """
    if len(df_daily) < 5:
        return "unclear"
    highs = df_daily["high"].values
    lows = df_daily["low"].values
    closes = df_daily["close"].values
    opens = df_daily["open"].values

    # Find recent swing points
    swing_highs = []
    swing_lows = []
    for j in range(1, len(df_daily) - 1):
        if highs[j] > highs[j - 1] and highs[j] > highs[j + 1]:
            swing_highs.append(highs[j])
        if lows[j] < lows[j - 1] and lows[j] < lows[j + 1]:
            swing_lows.append(lows[j])

    last = df_daily.iloc[-1]
    prev = df_daily.iloc[-2]

    # MSS check: did today break a prior swing?
    mss_bullish = False
    mss_bearish = False
    if swing_highs:
        if last["high"] > swing_highs[-1] and last["close"] > swing_highs[-1]:
            mss_bullish = True  # broke above swing high and held
    if swing_lows:
        if last["low"] < swing_lows[-1] and last["close"] < swing_lows[-1]:
            mss_bearish = True  # broke below swing low and held

    # Liquidity sweep: wick beyond level but close back inside (SFP on daily)
    sweep_bullish = False
    sweep_bearish = False
    if swing_lows:
        if last["low"] < swing_lows[-1] and last["close"] > swing_lows[-1]:
            sweep_bullish = True  # swept lows, closed back above = bullish
    if swing_highs:
        if last["high"] > swing_highs[-1] and last["close"] < swing_highs[-1]:
            sweep_bearish = True  # swept highs, closed back below = bearish

    # Candle direction: bullish or bearish close
    bullish_candle = last["close"] > last["open"]
    bearish_candle = last["close"] < last["open"]

    # Score it
    bull_score = sum([mss_bullish, sweep_bullish, bullish_candle])
    bear_score = sum([mss_bearish, sweep_bearish, bearish_candle])

    if bull_score >= 2:
        return "bullish"
    elif bear_score >= 2:
        return "bearish"
    elif bull_score == 1 and bear_score == 0:
        return "bullish"
    elif bear_score == 1 and bull_score == 0:
        return "bearish"
    return "unclear"



def _build_entry(direction: str, entry_price: float, entry_time, stop: float,
                 model: str, score: int, extra: dict) -> Optional[dict]:
    """Build standardized entry dict with stop/target/sizing.

    T2 target uses PDH/PDL from extra dict if available (JCAP aligned).
    Falls back to 3R if PDH/PDL not provided or closer than 2R.
    """
    if direction == "long":
        risk_pts = entry_price - stop
    else:
        risk_pts = stop - entry_price

    if risk_pts <= 2:  # minimum 2 pts risk
        return None

    # T2 target: use PDH (longs) or PDL (shorts) if available — JCAP aligned
    # Fall back to 3R if PDH/PDL is missing or too close (< 2R)
    fallback_target = entry_price + (risk_pts * T2_RR) if direction == "long" else entry_price - (risk_pts * T2_RR)
    pdh = extra.get("_pdh")
    pdl = extra.get("_pdl")

    if direction == "long" and pdh is not None:
        pdh_distance = pdh - entry_price
        target = pdh if pdh_distance >= risk_pts * 2 else fallback_target
    elif direction == "short" and pdl is not None:
        pdl_distance = entry_price - pdl
        target = pdl if pdl_distance >= risk_pts * 2 else fallback_target
    else:
        target = fallback_target

    risk_per_contract = risk_pts * POINT_VALUE
    if risk_per_contract <= 0:
        return None
    # Enforce $500 max loss: cap contracts so total risk <= MAX_LOSS
    max_by_risk = max(1, int(MAX_LOSS / risk_per_contract))
    contracts = min(FIXED_CONTRACTS, max_by_risk) if FIXED_CONTRACTS else max_by_risk

    result = {
        "direction": direction,
        "entry": entry_price,
        "stop": stop,
        "target": target,
        "risk_pts": risk_pts,
        "contracts": contracts,
        "score": score,
        "model": model,
        "entry_time": str(entry_time),
    }
    result.update(extra)
    return result


def _find_entry_realtime(kz_df: pd.DataFrame, direction: str, midnight_open: float,
                         pdh: float, pdl: float,
                         pre_kz_df: Optional[pd.DataFrame] = None,
                         session_high: Optional[float] = None,
                         session_low: Optional[float] = None) -> Optional[dict]:
    """Simulate real-time trading: walk forward candle-by-candle.

    5 JCAP entry models checked in priority order:
      Entry 0: Daily Sweep SFP — 1H SFP of pre-mapped swing levels + LTF FVG
      Entry 1: FVG Retrace — sweep + displacement + FVG retrace
      Entry 2: Order Block — OB retrace after displacement
      Entry 3: Liquidity Raid (Turtle Soup) — sweep of key level + displacement + FVG
      Entry 4: Breaker Block — violated OB becomes re-entry zone

    Silver Bullet rules applied in 10:00-11:00 and 14:00-15:00 windows:
      - Only FIRST FVG is valid
      - Sweep required before entry
    """
    if kz_df.empty or len(kz_df) < 10:
        return None

    df_5m = _agg(kz_df, 5)
    if len(df_5m) < 5:
        return None

    # ── Pre-map key levels for sweep detection (JCAP: map at 8 AM) ──
    key_levels_long = []   # levels to sweep for long setup (SSL targets)
    key_levels_short = []  # levels to sweep for short setup (BSL targets)

    # PDH/PDL — primary liquidity levels (None on first day)
    if pdl is not None:
        key_levels_long.append(("PDL", pdl))
    if pdh is not None:
        key_levels_short.append(("PDH", pdh))

    # Session H/L from overnight/Asia (if available)
    if session_high is not None:
        key_levels_short.append(("Session High", session_high))
    if session_low is not None:
        key_levels_long.append(("Session Low", session_low))

    # Equal highs/lows from pre-KZ data
    if pre_kz_df is not None and len(pre_kz_df) > 30:
        pre_5m = _agg(pre_kz_df, 5)
        if len(pre_5m) >= 5:
            for j in range(2, len(pre_5m) - 1):
                # Equal lows (buy-side liquidity below)
                if abs(pre_5m.iloc[j]["low"] - pre_5m.iloc[j-1]["low"]) < 2:
                    key_levels_long.append(("Equal Low", float(pre_5m.iloc[j]["low"])))
                # Equal highs (sell-side liquidity above)
                if abs(pre_5m.iloc[j]["high"] - pre_5m.iloc[j-1]["high"]) < 2:
                    key_levels_short.append(("Equal High", float(pre_5m.iloc[j]["high"])))

    # ── Pre-map 1H swing points for SFP (JCAP: map prior session swings at 8 AM) ──
    mapped_sfp_levels = []
    if pre_kz_df is not None and not pre_kz_df.empty:
        full_1m_for_1h = pd.concat([pre_kz_df, kz_df])
        # Map swings from pre-KZ 1H candles ONLY (prior session)
        pre_1h = _agg(pre_kz_df, 60) if len(pre_kz_df) >= 60 else pd.DataFrame()
        if len(pre_1h) >= 3:
            h = pre_1h["high"].values
            l = pre_1h["low"].values
            for j in range(1, len(pre_1h) - 1):
                if h[j] > h[j-1] and h[j] > h[j+1]:
                    mapped_sfp_levels.append(("swing_high", float(h[j])))
                if l[j] < l[j-1] and l[j] < l[j+1]:
                    mapped_sfp_levels.append(("swing_low", float(l[j])))
    else:
        full_1m_for_1h = kz_df

    # ── State — built up as we walk forward ──
    sweep_seen = None       # {"time", "level", "sweep_price", "level_name"}
    sfp_1h_seen = None      # {"time", "sfp_type", "swing_level", "sweep_price"}
    displacements = []      # [{"idx", "candle", "time"}]
    fvgs = []               # [{"fvg_top", "fvg_bottom", "fvg_ce", "c1_low"/"c1_high", "time"}]
    obs = []                # [{"ob_high", "ob_low", "ob_ce", "time", "violated": bool}]
    breakers = []           # [{"ob_high", "ob_low", "ob_ce", "time"}] — violated OBs
    first_fvg_used = False  # Silver Bullet: only first FVG in window

    # PDH/PDL injected into every entry's extra dict for T2 targeting
    _pdh_pdl = {"_pdh": pdh, "_pdl": pdl}

    # Helper: get structural stop from FVG
    def _fvg_stop(fvg_dict, d):
        if d == "long":
            return fvg_dict.get("c1_low", fvg_dict["fvg_bottom"]) - 2
        else:
            return fvg_dict.get("c1_high", fvg_dict["fvg_top"]) + 2

    # Helper: merge PDH/PDL into extra dict
    def _extra(d):
        return {**d, **_pdh_pdl}

    # Helper: check if current time is in Silver Bullet window
    def _in_silver_bullet(timestamp):
        t = timestamp.time()
        from datetime import time as dtime
        sb1 = (dtime(10, 0), dtime(11, 0))
        sb2 = (dtime(14, 0), dtime(15, 0))
        return (sb1[0] <= t <= sb1[1]) or (sb2[0] <= t <= sb2[1])

    # Walk forward candle by candle
    for i in range(len(df_5m)):
        candle = df_5m.iloc[i]
        ts = df_5m.index[i]

        # ── Update state: check for sweep of KEY LEVELS on 1m candles ──
        if sweep_seen is None:
            bar_1m = kz_df[(kz_df.index >= ts) & (kz_df.index < ts + pd.Timedelta(minutes=5))]
            for _, row in bar_1m.iterrows():
                if direction == "long":
                    for level_name, level_price in key_levels_long:
                        if row["low"] < level_price and row["close"] > level_price:
                            sweep_seen = {"time": ts, "level": level_price,
                                          "sweep_price": float(row["low"]),
                                          "level_name": level_name}
                            break
                else:
                    for level_name, level_price in key_levels_short:
                        if row["high"] > level_price and row["close"] < level_price:
                            sweep_seen = {"time": ts, "level": level_price,
                                          "sweep_price": float(row["high"]),
                                          "level_name": level_name}
                            break
                if sweep_seen:
                    break

        # ── Update state: check for 1H SFP on PRE-MAPPED levels only ──
        if sfp_1h_seen is None and mapped_sfp_levels:
            data_up_to_now = full_1m_for_1h[full_1m_for_1h.index <= ts + pd.Timedelta(minutes=5)]
            if len(data_up_to_now) >= 60:
                df_1h = _agg(data_up_to_now, 60)
                if len(df_1h) >= 2:
                    last_1h = df_1h.iloc[-1]
                    last_1h_ts = df_1h.index[-1]
                    MIN_SFP_PEN = 3.0
                    if direction == "long":
                        for lvl_type, lvl_price in mapped_sfp_levels:
                            if lvl_type == "swing_low":
                                pen = lvl_price - last_1h["low"]
                                if pen >= MIN_SFP_PEN and last_1h["close"] > lvl_price:
                                    sfp_1h_seen = {
                                        "time": last_1h_ts, "sfp_type": "long",
                                        "swing_level": lvl_price,
                                        "sweep_price": float(last_1h["low"]),
                                    }
                                    break
                    else:
                        for lvl_type, lvl_price in mapped_sfp_levels:
                            if lvl_type == "swing_high":
                                pen = last_1h["high"] - lvl_price
                                if pen >= MIN_SFP_PEN and last_1h["close"] < lvl_price:
                                    sfp_1h_seen = {
                                        "time": last_1h_ts, "sfp_type": "short",
                                        "swing_level": lvl_price,
                                        "sweep_price": float(last_1h["high"]),
                                    }
                                    break

        # ── Update state: check for displacement (60%+ body) ──
        body = abs(candle["close"] - candle["open"])
        rng = candle["high"] - candle["low"]
        if rng > 0 and body / rng >= 0.6:
            if direction == "long" and candle["close"] > candle["open"]:
                displacements.append({"idx": i, "candle": candle, "time": ts})
            elif direction == "short" and candle["close"] < candle["open"]:
                displacements.append({"idx": i, "candle": candle, "time": ts})

        # ── Update state: check for FVG (3-candle imbalance) ──
        if i >= 2:
            c1 = df_5m.iloc[i - 2]
            c3 = df_5m.iloc[i]
            if direction == "long" and c3["low"] > c1["high"]:
                fvgs.append({
                    "fvg_top": float(c3["low"]),
                    "fvg_bottom": float(c1["high"]),
                    "fvg_ce": (float(c3["low"]) + float(c1["high"])) / 2,
                    "c1_low": float(c1["low"]),
                    "time": ts,
                })
            elif direction == "short" and c3["high"] < c1["low"]:
                fvgs.append({
                    "fvg_top": float(c1["low"]),
                    "fvg_bottom": float(c3["high"]),
                    "fvg_ce": (float(c1["low"]) + float(c3["high"])) / 2,
                    "c1_high": float(c1["high"]),
                    "time": ts,
                })

        # ── Update state: check for OB (opposing candle before displacement) ──
        if i >= 1:
            prev = df_5m.iloc[i - 1]
            if rng > 0 and body / rng >= 0.5:
                if direction == "long" and candle["close"] > candle["open"] and prev["close"] < prev["open"]:
                    obs.append({
                        "ob_high": float(prev["high"]),
                        "ob_low": float(prev["low"]),
                        "ob_ce": (float(prev["high"]) + float(prev["low"])) / 2,
                        "time": ts, "violated": False,
                    })
                elif direction == "short" and candle["close"] < candle["open"] and prev["close"] > prev["open"]:
                    obs.append({
                        "ob_high": float(prev["high"]),
                        "ob_low": float(prev["low"]),
                        "ob_ce": (float(prev["high"]) + float(prev["low"])) / 2,
                        "time": ts, "violated": False,
                    })

        # ── Update state: check for OB violations → Breaker Blocks ──
        for ob in obs:
            if ob["violated"]:
                continue
            if direction == "long" and candle["close"] < ob["ob_low"]:
                ob["violated"] = True
                breakers.append({
                    "ob_high": ob["ob_high"], "ob_low": ob["ob_low"],
                    "ob_ce": ob["ob_ce"], "time": ts,
                })
            elif direction == "short" and candle["close"] > ob["ob_high"]:
                ob["violated"] = True
                breakers.append({
                    "ob_high": ob["ob_high"], "ob_low": ob["ob_low"],
                    "ob_ce": ob["ob_ce"], "time": ts,
                })

        # ── CHECK FOR ENTRY — requires displacement first ──
        if not displacements:
            continue

        # Silver Bullet: in SB window, only first FVG is valid
        in_sb = _in_silver_bullet(ts)

        # ════════════════════════════════════════════════════════════════
        # Entry 0: Daily Sweep SFP (priority 0, score 9)
        # JCAP #1: 1H SFP of pre-mapped swing + LTF FVG entry
        # Stop: beyond the SFP candle wick (sweep extreme)
        # ════════════════════════════════════════════════════════════════
        if sfp_1h_seen and fvgs:
            for fvg in fvgs:
                if fvg["time"] < sfp_1h_seen["time"]:
                    continue
                if in_sb and first_fvg_used:
                    continue  # Silver Bullet: first FVG only
                # SFP stop = beyond the SFP wick extreme (NOT FVG candle 1)
                sfp_sweep = sfp_1h_seen["sweep_price"]
                if direction == "long":
                    sfp_stop = sfp_sweep - 2  # below the sweep low
                else:
                    sfp_stop = sfp_sweep + 2  # above the sweep high
                if direction == "long" and candle["low"] <= fvg["fvg_ce"]:
                    first_fvg_used = True
                    return _build_entry(direction, fvg["fvg_ce"], ts, sfp_stop,
                                        "SFP_RAID", 9, _extra({
                                            "sfp_1h": True,
                                            "sfp_swing_level": sfp_1h_seen["swing_level"],
                                            "sweep": sfp_sweep,
                                        }))
                elif direction == "short" and candle["high"] >= fvg["fvg_ce"]:
                    first_fvg_used = True
                    return _build_entry(direction, fvg["fvg_ce"], ts, sfp_stop,
                                        "SFP_RAID", 9, _extra({
                                            "sfp_1h": True,
                                            "sfp_swing_level": sfp_1h_seen["swing_level"],
                                            "sweep": sfp_sweep,
                                        }))

        # ════════════════════════════════════════════════════════════════
        # Entry 1: FVG Retrace (priority 1, score 7)
        # JCAP: sweep + displacement + FVG retrace at CE
        # ════════════════════════════════════════════════════════════════
        if sweep_seen and fvgs:
            for fvg in fvgs:
                if in_sb and first_fvg_used:
                    continue
                if direction == "long" and candle["low"] <= fvg["fvg_ce"]:
                    stop = _fvg_stop(fvg, direction)
                    first_fvg_used = True
                    return _build_entry(direction, fvg["fvg_ce"], ts, stop,
                                        "FVG_RETRACE", 7, _extra({"sweep": sweep_seen["sweep_price"],
                                                            "level_name": sweep_seen.get("level_name", "")}))
                elif direction == "short" and candle["high"] >= fvg["fvg_ce"]:
                    stop = _fvg_stop(fvg, direction)
                    first_fvg_used = True
                    return _build_entry(direction, fvg["fvg_ce"], ts, stop,
                                        "FVG_RETRACE", 7, _extra({"sweep": sweep_seen["sweep_price"],
                                                            "level_name": sweep_seen.get("level_name", "")}))

        # ════════════════════════════════════════════════════════════════
        # Entry 2: Order Block (priority 2, score 6 with sweep, 4 without)
        # JCAP: OB retrace after displacement, enter at CE
        # ════════════════════════════════════════════════════════════════
        active_obs = [ob for ob in obs if not ob["violated"]]
        if active_obs:
            for ob in active_obs:
                if direction == "long" and candle["low"] <= ob["ob_ce"]:
                    stop = ob["ob_low"] - 2
                    score = 6 if sweep_seen else 4
                    return _build_entry(direction, ob["ob_ce"], ts, stop,
                                        "ORDER_BLOCK", score, _extra({}))
                elif direction == "short" and candle["high"] >= ob["ob_ce"]:
                    stop = ob["ob_high"] + 2
                    score = 6 if sweep_seen else 4
                    return _build_entry(direction, ob["ob_ce"], ts, stop,
                                        "ORDER_BLOCK", score, _extra({}))

        # ════════════════════════════════════════════════════════════════
        # Entry 3: Liquidity Raid / Turtle Soup (priority 2, score 7)
        # JCAP: sweep of equal H/L or session level + displacement + FVG
        # Sequence must be: sweep → displacement → FVG (time-ordered)
        # ════════════════════════════════════════════════════════════════
        if sweep_seen and sweep_seen.get("level_name", "").startswith("Equal"):
            # Verify displacement happened AFTER the sweep
            post_sweep_disp = [d for d in displacements if d["time"] >= sweep_seen["time"]]
            if post_sweep_disp and fvgs:
                for fvg in fvgs:
                    if in_sb and first_fvg_used:
                        continue  # Silver Bullet: first FVG only
                    if fvg["time"] < sweep_seen["time"]:
                        continue  # FVG predates sweep
                    if direction == "long" and candle["low"] <= fvg["fvg_ce"]:
                        stop = _fvg_stop(fvg, direction)
                        first_fvg_used = True
                        return _build_entry(direction, fvg["fvg_ce"], ts, stop,
                                            "LIQ_RAID", 7, _extra({"sweep": sweep_seen["sweep_price"],
                                                             "level_name": sweep_seen["level_name"]}))
                    elif direction == "short" and candle["high"] >= fvg["fvg_ce"]:
                        stop = _fvg_stop(fvg, direction)
                        first_fvg_used = True
                        return _build_entry(direction, fvg["fvg_ce"], ts, stop,
                                            "LIQ_RAID", 7, _extra({"sweep": sweep_seen["sweep_price"],
                                                             "level_name": sweep_seen["level_name"]}))

        # ════════════════════════════════════════════════════════════════
        # Entry 4: Breaker Block (priority 3, score 5)
        # JCAP: violated OB becomes re-entry zone on retrace
        # Best when paired with FVG at same level
        # ════════════════════════════════════════════════════════════════
        if breakers:
            for brk in breakers:
                if direction == "long" and candle["low"] <= brk["ob_ce"]:
                    stop = brk["ob_low"] - 2
                    # Check if a FVG overlaps with the breaker (highest confluence)
                    has_fvg = any(f["fvg_bottom"] <= brk["ob_ce"] <= f["fvg_top"] for f in fvgs)
                    score = 6 if has_fvg else 5
                    return _build_entry(direction, brk["ob_ce"], ts, stop,
                                        "BREAKER", score, _extra({"has_fvg": has_fvg}))
                elif direction == "short" and candle["high"] >= brk["ob_ce"]:
                    stop = brk["ob_high"] + 2
                    has_fvg = any(f["fvg_bottom"] <= brk["ob_ce"] <= f["fvg_top"] for f in fvgs)
                    score = 6 if has_fvg else 5
                    return _build_entry(direction, brk["ob_ce"], ts, stop,
                                        "BREAKER", score, _extra({"has_fvg": has_fvg}))

    return None


def _simulate_trade(df_after_entry: pd.DataFrame, trade: dict) -> dict:
    """Walk forward from entry simulating JCAP T1/T2 exit structure.

    Phase 1: Full position — wait for T1 (1.5R) or stop.
      - If stop hit → full loss on all contracts.
      - If T1 hit → close 50% at T1, move stop to breakeven.

    Phase 2: Runner (50% position) — wait for T2 (3R), stop is at breakeven.
      - If BE hit → runner exits flat, keep T1 profit.
      - If T2 hit → runner profit added to T1 profit.

    Hard close: exit remaining position at last candle close.
    """
    direction = trade["direction"]
    entry = trade["entry"]
    stop = trade["stop"]
    risk_pts = trade.get("risk_pts", abs(entry - stop))
    contracts = trade["contracts"]

    # T1 = 1.5R, T2 = PDH/PDL (from trade["target"]) or fallback 3R
    if direction == "long":
        t1_price = entry + (risk_pts * T1_RR)
        t2_price = trade.get("target", entry + (risk_pts * T2_RR))
    else:
        t1_price = entry - (risk_pts * T1_RR)
        t2_price = trade.get("target", entry - (risk_pts * T2_RR))

    t1_contracts = max(1, int(contracts * T1_CLOSE_PCT))
    t2_contracts = contracts - t1_contracts

    # Phase 1: Full position — T1 or stop
    t1_hit = False
    t1_pnl = 0.0
    for ts, row in df_after_entry.iterrows():
        if direction == "long":
            if row["low"] <= stop:
                pnl = (stop - entry) * POINT_VALUE * contracts
                return {"result": "LOSS", "exit": stop, "exit_time": str(ts), "pnl": pnl,
                        "t1_hit": False, "contracts": contracts}
            if row["high"] >= t1_price:
                t1_pnl = (t1_price - entry) * POINT_VALUE * t1_contracts
                t1_hit = True
                t1_time = ts
                break
        else:
            if row["high"] >= stop:
                pnl = (entry - stop) * POINT_VALUE * contracts
                return {"result": "LOSS", "exit": stop, "exit_time": str(ts), "pnl": pnl,
                        "t1_hit": False, "contracts": contracts}
            if row["low"] <= t1_price:
                t1_pnl = (entry - t1_price) * POINT_VALUE * t1_contracts
                t1_hit = True
                t1_time = ts
                break

    if not t1_hit:
        # Hard close — never hit T1 or stop
        last_close = float(df_after_entry.iloc[-1]["close"])
        if direction == "long":
            pnl = (last_close - entry) * POINT_VALUE * contracts
        else:
            pnl = (entry - last_close) * POINT_VALUE * contracts
        return {"result": "CLOSE", "exit": last_close, "exit_time": str(df_after_entry.index[-1]),
                "pnl": pnl, "t1_hit": False, "contracts": contracts}

    # Phase 2: Runner — stop moved to breakeven, target is T2
    if t2_contracts <= 0:
        return {"result": "T1_WIN", "exit": t1_price, "exit_time": str(t1_time),
                "pnl": t1_pnl, "t1_hit": True, "contracts": contracts}

    be_stop = entry  # Stop moved to breakeven
    runner_df = df_after_entry[df_after_entry.index > t1_time]

    # Runner: only exit on BE stop or hard close at 4:00 PM
    # JCAP: "set and forget — let it run until end of day"
    for ts, row in runner_df.iterrows():
        if direction == "long":
            if row["low"] <= be_stop:
                return {"result": "T1_WIN", "exit": t1_price, "exit_time": str(ts),
                        "pnl": t1_pnl, "t1_hit": True, "runner": "BE", "contracts": contracts}
        else:
            if row["high"] >= be_stop:
                return {"result": "T1_WIN", "exit": t1_price, "exit_time": str(ts),
                        "pnl": t1_pnl, "t1_hit": True, "runner": "BE", "contracts": contracts}

    # Hard close runner at 4:00 PM — capture whatever R the day gave
    last_close = float(runner_df.iloc[-1]["close"]) if not runner_df.empty else entry
    if direction == "long":
        runner_pnl = (last_close - entry) * POINT_VALUE * t2_contracts
    else:
        runner_pnl = (entry - last_close) * POINT_VALUE * t2_contracts
    total_pnl = t1_pnl + runner_pnl
    result_type = "WIN" if runner_pnl > 0 else "T1_WIN"
    return {"result": result_type, "exit": last_close,
            "exit_time": str(runner_df.index[-1]) if not runner_df.empty else str(t1_time),
            "pnl": total_pnl, "t1_hit": True, "runner": "EOD", "contracts": contracts}


def backtest_day(ticker: str, date: str, prev_df: Optional[pd.DataFrame] = None,
                  consecutive_losses: int = 0,
                  daily_history: Optional[list] = None,
                  indicators: Optional[dict] = None,
                  df_all: Optional[pd.DataFrame] = None,
                  prev_session_df: Optional[pd.DataFrame] = None,
                  full_send_mode: bool = False) -> dict:
    """Simulate one trading day.

    Args:
        daily_history: List of prior day DataFrames (up to 10) for daily bias calculation.
        indicators: Pre-computed indicators from _precompute_indicators (bulk mode).
        df_all: Full 1m dataset (bulk mode) — slice today's data from this.
    """
    # Bulk mode: slice today's data from pre-fetched dataset
    if df_all is not None:
        day_mask = df_all.index.date == datetime.strptime(date, "%Y-%m-%d").date()
        df = df_all[day_mask]
        if df.empty:
            return {"date": date, "status": "no_data", "trade": None}
    else:
        df = _fetch_day(ticker, date)
        if df is None or df.empty:
            return {"date": date, "status": "no_data", "trade": None}

    mo = _midnight_open(df)
    if mo is None:
        return {"date": date, "status": "no_midnight", "trade": None}

    # PDH/PDL from previous day (None on first day — no look-ahead bias)
    if prev_df is not None and not prev_df.empty:
        prev_session = prev_df.between_time("09:30", "16:00")
        if prev_session.empty:
            prev_session = prev_df
        pdh = float(prev_session["high"].max())
        pdl = float(prev_session["low"].min())
    else:
        pdh = None
        pdl = None

    # Daily bias — use pre-computed daily candles if available (bulk mode)
    if indicators and "1d" in indicators:
        df_daily = indicators["1d"]
        # Get daily candles up to today
        today = datetime.strptime(date, "%Y-%m-%d").date()
        df_daily_to_today = df_daily[df_daily.index.date <= today]
        bias = _daily_bias(df_daily_to_today) if len(df_daily_to_today) >= 5 else "unclear"
    elif daily_history:
        combined = pd.concat(daily_history + [df])
        df_daily_agg = _agg(combined, 1440) if len(combined) > 10 else pd.DataFrame()
        bias = _daily_bias(df_daily_agg) if len(df_daily_agg) >= 5 else "unclear"
    else:
        bias = "unclear"

    day_result = {
        "date": date,
        "status": "ok",
        "midnight_open": mo,
        "pdh": pdh,
        "pdl": pdl,
        "daily_bias": bias,
        "day_high": float(df["high"].max()),
        "day_low": float(df["low"].min()),
        "trade": None,
        "_df": df,  # Return for next day's PDH/PDL (avoid double fetch)
    }

    # ── Rule: Need PDH/PDL from prior session (skip first day) ──
    if pdh is None or pdl is None:
        day_result["skip_reason"] = "no_prior_session"
        return day_result

    # ── Pre-market EMA 200 check at 8:29 AM on all timeframes ──
    pre_829 = df.between_time("08:28", "08:30")
    if indicators and not pre_829.empty:
        price_829 = float(pre_829.iloc[-1]["close"])
        day_result["price_829"] = price_829
        today = datetime.strptime(date, "%Y-%m-%d").date()

        ema_check = {}
        import stockstats
        cutoff = pre_829.index[-1]

        # Compute EMA 200 on each timeframe via stockstats (same as indicators.py)
        for tf_key in ["1d", "4h", "1h", "15m", "5m", "1m"]:
            tf_label = {"1d": "daily", "4h": "4h", "1h": "1h", "15m": "15m", "5m": "5m", "1m": "1m"}[tf_key]
            df_tf = indicators.get(tf_key)
            if df_tf is None or len(df_tf) < 200:
                continue
            ss = stockstats.wrap(df_tf.rename(columns={c: c.lower() for c in df_tf.columns}).copy())
            ema_series = ss["close_200_ema"]
            ema_to = ema_series[ema_series.index <= cutoff]
            if len(ema_to) > 0:
                val = float(ema_to.iloc[-1])
                ema_check[tf_label] = {"ema200": val, "above": price_829 > val, "dist": round(price_829 - val, 2)}

        day_result["ema200_check"] = ema_check
        # All timeframes agree = strong bias confirmation
        above_counts = sum(1 for tf in ema_check.values() if tf["above"])
        below_counts = sum(1 for tf in ema_check.values() if not tf["above"])
        total_tf = len(ema_check)
        if total_tf > 0:
            day_result["ema200_alignment"] = "ALL_ABOVE" if above_counts == total_tf else \
                                              "ALL_BELOW" if below_counts == total_tf else \
                                              f"MIXED_{above_counts}above_{below_counts}below"

    # ── Post-open tracking: where price runs after 9:30 vs EMA 200 ──
    post_open = df.between_time("09:30", "09:35")
    if not post_open.empty and "ema200_check" in day_result:
        open_price = float(post_open.iloc[0]["open"])
        first_30 = df.between_time("09:30", "10:00")
        if not first_30.empty:
            first_30_high = float(first_30["high"].max())
            first_30_low = float(first_30["low"].min())
            day_result["open_price"] = open_price
            day_result["first_30_high"] = first_30_high
            day_result["first_30_low"] = first_30_low
            # Check if daily EMA 200 held
            daily_ema = day_result["ema200_check"].get("daily", {})
            if daily_ema:
                ema_val = daily_ema["ema200"]
                day_result["open_vs_ema200"] = "above" if open_price > ema_val else "below"
                if daily_ema["above"]:
                    day_result["held_above_ema"] = first_30_low > ema_val
                else:
                    day_result["held_below_ema"] = first_30_high < ema_val

    # ── Rule: ONE direction per day — commit to daily bias ──
    if bias == "bullish":
        direction = "long"
    elif bias == "bearish":
        direction = "short"
    else:
        # Unclear daily bias = NO TRADE (JadeCap: "if daily bias unclear → NO TRADE")
        day_result["skip_reason"] = "unclear_daily_bias"
        return day_result

    # Try each kill zone — ONE trade per KZ, up to 2 per day (AM + PM)
    # PM gets fresh pre-KZ analysis from the AM session (like running pipeline at 12:30)
    # If AM trade failed → PM reviews, enters half size (cautious after loss)
    day_result["trades"] = []
    day_result["daily_pnl"] = 0
    am_failed = False
    am_loss_review = None  # "bias_wrong" / "stop_hunted_then_reversed" / "stop_hunted_then_target_hit"

    for kz_name, (kz_start, kz_end) in KILL_ZONES.items():
        kz_df = df.between_time(kz_start, kz_end)
        if kz_df.empty or len(kz_df) < 10:
            continue

        # ── Rule: If already hit daily loss/profit cap, skip ──
        if day_result["daily_pnl"] <= -DAILY_LOSS_CAP:
            day_result["skip_reason"] = "daily_loss_cap"
            break
        if day_result["daily_pnl"] >= DAILY_PROFIT_CAP:
            day_result["skip_reason"] = "daily_profit_cap"
            break

        is_pm = kz_start >= "12:00"

        # ── Rule: Can't take PM trade if AM runner is still holding ──
        if is_pm and day_result["trades"]:
            last_trade = day_result["trades"][-1]
            last_exit_time = last_trade.get("exit_time", "")
            last_runner = last_trade.get("runner", "")
            # Runner held to EOD = trade is STILL OPEN through PM, can't enter PM
            if last_runner == "EOD":
                day_result.setdefault("pm_review", []).append("am_runner_still_holding_to_eod")
                continue
            # Runner exited (BE or LOSS) — check if it exited BEFORE PM KZ starts
            if last_exit_time:
                exit_ts = pd.Timestamp(last_exit_time)
                pm_start_ts = pd.Timestamp(f"{date} {kz_start}")
                # Match timezone: strip tz from exit_ts for comparison
                if exit_ts.tzinfo is not None:
                    exit_ts = exit_ts.tz_localize(None)
                if exit_ts >= pm_start_ts:
                    # AM trade exited DURING PM KZ — no time to review + enter fresh
                    day_result.setdefault("pm_review", []).append(
                        f"am_trade_exited_during_pm_kz_at_{last_exit_time}")
                    continue

        # Pre-KZ analysis context differs by session:
        # AM: use prior day session (mapped at 8 AM)
        # PM: use today's AM session (fresh analysis at 12:30 — review after AM result)
        if is_pm:
            # ── 12:30 PM REVIEW: analyze AM session before deciding PM trade ──
            am_data = df.between_time("09:30", "11:30")
            if am_data.empty:
                am_data = df.between_time("08:00", "11:30")

            if am_failed and not am_data.empty:
                # ── TWO-STEP REVIEW after AM loss ──
                # Review 1 (immediate): already done — am_loss_review tells us what happened
                # Review 2 (12:30 PM): check full AM session + daily DD budget

                am_close = float(am_data.iloc[-1]["close"])
                am_open = float(am_data.iloc[0]["open"])
                am_high = float(am_data["high"].max())
                am_low = float(am_data["low"].min())
                am_range = am_high - am_low if am_high > am_low else 1

                session_bearish = (am_open - am_close) > am_range * 0.6
                session_bullish = (am_close - am_open) > am_range * 0.6

                # ── DD budget check: how much daily loss can PM afford? ──
                am_loss_amount = abs(day_result["daily_pnl"])
                dd_remaining = DAILY_LOSS_CAP - am_loss_amount
                if dd_remaining <= 0:
                    # Already hit daily loss cap — NO PM TRADE
                    day_result.setdefault("pm_review", []).append(
                        f"daily_dd_exhausted: lost ${am_loss_amount:.0f}, cap=${DAILY_LOSS_CAP}")
                    continue
                # If AM loss used >60% of daily DD budget → skip PM (not enough room)
                if dd_remaining < DAILY_LOSS_CAP * 0.4:
                    day_result.setdefault("pm_review", []).append(
                        f"dd_budget_tight: lost ${am_loss_amount:.0f}, only ${dd_remaining:.0f} left, skip")
                    continue

                skip_pm = False

                # ── Bias review: was the direction wrong? ──
                if am_loss_review == "bias_wrong":
                    # Immediate review said bias was wrong — check if AM session confirms
                    if direction == "long" and session_bearish:
                        skip_pm = True  # Both reviews agree: bias wrong
                    elif direction == "short" and session_bullish:
                        skip_pm = True
                    day_result.setdefault("pm_review", []).append(
                        f"immediate=bias_wrong, session={'confirms_skip' if skip_pm else 'mixed_allow_half'}, "
                        f"am_loss=${am_loss_amount:.0f}, dd_left=${dd_remaining:.0f}")
                elif am_loss_review in ("stop_hunted_then_reversed", "stop_hunted_then_target_hit"):
                    # Stop was hunted but bias was RIGHT — PM OK at half size
                    day_result.setdefault("pm_review", []).append(
                        f"immediate={am_loss_review}, bias_valid=true, pm=half_size, "
                        f"am_loss=${am_loss_amount:.0f}, dd_left=${dd_remaining:.0f}")
                else:
                    # Unknown cause — check session direction
                    if (direction == "long" and session_bearish) or (direction == "short" and session_bullish):
                        skip_pm = True
                    day_result.setdefault("pm_review", []).append(
                        f"immediate={am_loss_review}, session={'against_skip' if skip_pm else 'ok_half'}, "
                        f"am_loss=${am_loss_amount:.0f}, dd_left=${dd_remaining:.0f}")

                if skip_pm:
                    day_result.setdefault("pm_review", []).append("DECISION: skip_pm")
                    continue

            # PM prep: use today's full morning session as pre-KZ data
            # This simulates running a fresh pipeline analysis at 12:30
            pre_kz = am_data if not am_data.empty else df.between_time("08:00", kz_start)
            # Session H/L = today's AM range (fresh levels, not overnight)
            s_high = float(am_data["high"].max()) if not am_data.empty else None
            s_low = float(am_data["low"].min()) if not am_data.empty else None
        else:
            # AM prep: use prior day session (mapped at 8 AM)
            if prev_session_df is not None and not prev_session_df.empty:
                pre_kz = prev_session_df
            else:
                pre_kz = df.between_time("00:00", kz_start)
            # Asia/London session H/L (overnight levels)
            asia_london = df.between_time("00:00", "09:29")
            s_high = float(asia_london["high"].max()) if not asia_london.empty else None
            s_low = float(asia_london["low"].min()) if not asia_london.empty else None

        entry = _find_entry_realtime(kz_df, direction, mo, pdh, pdl,
                                     pre_kz_df=pre_kz,
                                     session_high=s_high, session_low=s_low)
        if entry and entry["score"] >= 3:
            # ── Rule: Half size after AM loss or consecutive losses (disabled in full send) ──
            # AM loss but bias still valid = trade PM at half size (cautious)
            if not full_send_mode and (consecutive_losses >= 2 or (is_pm and am_failed)):
                entry["contracts"] = max(1, entry["contracts"] // 2)
                entry["half_size"] = True
                entry["pm_after_am_loss"] = True

            # Simulate the trade — start AFTER entry bar (no look-inside-bar bias)
            entry_time = pd.Timestamp(entry["entry_time"])
            after_entry = df[df.index > entry_time + pd.Timedelta(minutes=4)]
            hard_close_df = after_entry.between_time(kz_start, HARD_CLOSE)
            if hard_close_df.empty:
                hard_close_df = after_entry

            outcome = _simulate_trade(hard_close_df, entry)
            entry.update(outcome)

            # Deduct fees: commission + slippage
            ct = entry["contracts"]
            commission = COMMISSION_PER_CONTRACT * ct * 2  # 2 sides (entry + exit)
            slippage_cost = SLIPPAGE_PTS * POINT_VALUE * ct * 2  # 1 pt slippage × 2 sides (entry + exit)
            total_fees = commission + slippage_cost
            entry["fees"] = round(total_fees, 2)
            entry["pnl"] = entry["pnl"] - total_fees  # net of fees

            entry["kz"] = kz_name
            day_result["trades"].append(entry)
            day_result["daily_pnl"] += entry["pnl"]

            # ── IMMEDIATE POST-LOSS REVIEW ──
            # Only review REAL losses — BE (T1 hit, runner stopped at entry) is NOT a failure
            # BE result = "T1_WIN" with small pnl (possibly negative after fees)
            is_real_loss = entry["result"] == "LOSS"  # full stop-out, no T1 hit

            if is_real_loss:
                loss_entry = entry["entry"]
                loss_dir = entry["direction"]

                # Check: after stop-out, what did price do for the NEXT 60 MINUTES?
                # This is what a trader sees right after getting stopped — did it go my way?
                exit_time = pd.Timestamp(entry.get("exit_time", entry["entry_time"]))
                review_end = exit_time + pd.Timedelta(minutes=60)
                after_loss = df[(df.index > exit_time) & (df.index <= review_end)]
                if after_loss.empty:
                    after_loss = df[df.index > exit_time].between_time(kz_start, kz_end)
                if not after_loss.empty:
                    target = entry.get("target", 0)
                    if loss_dir == "long":
                        post_high = float(after_loss["high"].max())
                        if target and post_high >= target:
                            entry["loss_review"] = "stop_hunted_then_target_hit"
                        elif post_high > loss_entry:
                            entry["loss_review"] = "stop_hunted_then_reversed"
                        else:
                            entry["loss_review"] = "bias_wrong"
                    else:
                        post_low = float(after_loss["low"].min())
                        if target and post_low <= target:
                            entry["loss_review"] = "stop_hunted_then_target_hit"
                        elif post_low < loss_entry:
                            entry["loss_review"] = "stop_hunted_then_reversed"
                        else:
                            entry["loss_review"] = "bias_wrong"
                else:
                    entry["loss_review"] = "no_data_after"

                if not is_pm:
                    am_failed = True
                    am_loss_review = entry.get("loss_review", "unknown")

    # Backward compat: set "trade" to first trade (or None)
    day_result["trade"] = day_result["trades"][0] if day_result["trades"] else None

    return day_result


def _save_trades_to_memory(trades: list, ticker: str, dates: list):
    """Convert backtest trades to BM25 memories and persist to SQLite."""
    import uuid
    from openclaw.memory import FinancialSituationMemory
    from openclaw.memory_persistence import persist_memories

    mem = FinancialSituationMemory(name="backtest")
    pairs = []

    for t in trades:
        model = t.get("model", "unknown")
        direction = t.get("direction", "?")
        result = t.get("result", "?")
        pnl = t.get("pnl", 0)
        kz = t.get("kz", "?")
        score = t.get("score", 0)
        entry = t.get("entry", 0)
        stop = t.get("stop", 0)
        target = t.get("target", 0)
        risk_pts = t.get("risk_pts", 0)
        sfp_flag = " with 1H SFP confirmation" if t.get("sfp_1h") else ""

        situation = (
            f"{ticker} {direction} setup in {kz} Kill Zone. "
            f"Entry model: {model} (score {score}){sfp_flag}. "
            f"Entry {entry:.0f}, stop {stop:.0f}, target {target:.0f}, "
            f"risk {risk_pts:.0f} pts."
        )

        if result == "WIN":
            recommendation = (
                f"WINNING trade: {model} {direction} in {kz} KZ yielded ${pnl:+,.0f}. "
                f"Score {score} setups with this model are reliable. "
                f"Continue taking {model} entries when score >= {score}."
            )
        elif result == "LOSS":
            recommendation = (
                f"LOSING trade: {model} {direction} in {kz} KZ lost ${pnl:+,.0f}. "
                f"Risk was {risk_pts:.0f} pts. "
                f"Consider tighter stops or higher score threshold for {model}."
            )
        else:
            recommendation = (
                f"HARD CLOSE: {model} {direction} in {kz} KZ closed at ${pnl:+,.0f}. "
                f"Trade did not reach target or stop before session end. "
                f"Consider earlier entries in {kz} KZ for {model}."
            )

        pairs.append((situation, recommendation))

    if not pairs:
        print("  No trades to save to memory.")
        return

    mem.add_situations(pairs)

    workspace = os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace")
    db_path = os.path.join(workspace, "trading.db")
    run_id = f"backtest-{dates[0]}-to-{dates[-1]}-{uuid.uuid4().hex[:8]}"

    inserted = persist_memories({"backtest": mem}, db_path, run_id)
    print(f"  Saved {inserted} trade memories to BM25 (run: {run_id})")


class ApexSimulator:
    """Apex Trader Funding $50K PA account simulation (2026 rules).

    Rules:
    - $50K starting balance, $2,000 trailing drawdown
    - Safety net: $52,100 ($50K + $2K + $100)
    - Before safety net: max 2 contracts
    - After safety net: max 4 contracts, trailing DD locks
    - Payout ladder: 1st=$1,500, 2nd-5th progressive, 6th=$3,000, 7th+ uncapped
    - After cashout: reset to 2ct, rebuild
    - 50% consistency rule: no single day > 50% of total profit
    - At $20K profit: leave $10K, cash out rest
    - Back to $20K again: cash out $5K
    - Sizing scales by $1,500 steps
    """

    def __init__(self, firm_config=None):
        if firm_config is None:
            from openclaw.jadecap_config import PROP_FIRMS
            firm_config = PROP_FIRMS.get("apex", {})
        self.firm_config = firm_config
        self.firm_name = firm_config.get("name", "Apex Trader Funding")
        self.starting_balance = firm_config.get("account_size", 50000)
        self.balance = self.starting_balance
        self.trailing_dd = firm_config.get("trailing_drawdown", 2000)
        self.safety_net = firm_config.get("safety_net", 52100)
        self.liquidation = self.balance - self.trailing_dd
        self.peak_balance = self.balance
        self.past_safety_net = False
        self.max_contracts_mnq = firm_config.get("max_contracts_mnq", 40)
        self.base_contracts = firm_config.get("base_contracts_mnq", 5)
        self.scaling_step = firm_config.get("scaling_step", 2500)
        self.scaling_increment = firm_config.get("scaling_increment", 5)
        self.max_contracts = 2  # before safety net
        self.payout_ladder = firm_config.get("payout_ladder", [1500, 1875, 2250, 2625, 3000, 3000])
        self.consistency_rule = firm_config.get("consistency_rule", 0.50)
        self.post_ladder_floor = firm_config.get("post_ladder_floor", 20000)
        self.payout_count = 0
        self.total_cashed_out = 0
        self.cashouts = []  # [{"payout_num", "amount", "balance_after", "date"}]
        self.daily_pnls = []  # for consistency rule
        self.busted = False
        self.full_send = False  # After 2nd $20K cashout: max contracts till bust
        self._times_hit_20k = 0  # Track how many times profit reached $20K

    def get_contracts(self) -> int:
        """Get current contracts based on firm config scaling rules.

        After 2nd time reaching $20K profit and cashing out:
        full_send = True → max contracts until account busts.
        """
        if self.busted:
            return 0
        if self.full_send:
            return self.max_contracts_mnq  # 40 MNQ every trade, no scaling down, till bust
        profit = max(0, self.balance - self.starting_balance)
        steps = int(profit / self.scaling_step)
        contracts = self.base_contracts + (steps * self.scaling_increment)
        return min(contracts, self.max_contracts_mnq)

    def update(self, pnl: float, date: str):
        """Update account after a trade."""
        if self.busted:
            return

        self.balance += pnl
        self.daily_pnls.append({"date": date, "pnl": pnl})

        # Update peak and trailing DD
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
            # Trailing DD follows peak until safety net
            if not self.past_safety_net:
                self.liquidation = self.peak_balance - self.trailing_dd

        # Check safety net
        if not self.past_safety_net and self.peak_balance >= self.safety_net:
            self.past_safety_net = True
            self.max_contracts = self.firm_config.get("max_contracts_nq", 4)
            self.liquidation = self.starting_balance  # DD locks at starting balance

        # Check liquidation (bust)
        if self.balance <= self.liquidation:
            self.busted = True

    def check_cashout(self, date: str) -> float:
        """Check if a cashout should happen. Returns amount to cash out."""
        if self.busted:
            return 0

        profit = self.balance - self.starting_balance
        if profit <= 0:
            return 0

        # Must be past safety net to cash out
        if not self.past_safety_net:
            return 0

        # Consistency check (configurable threshold)
        if self.daily_pnls:
            max_day = max(d["pnl"] for d in self.daily_pnls)
            total_profit = sum(d["pnl"] for d in self.daily_pnls if d["pnl"] > 0)
            if total_profit > 0 and max_day / total_profit >= self.consistency_rule:
                return 0  # Fails consistency

        # Payout ladder (from firm config)
        self.payout_count += 1
        ladder = self.payout_ladder

        if self.payout_count <= len(ladder):
            max_payout = ladder[self.payout_count - 1]
        else:
            max_payout = float("inf")  # uncapped after ladder

        profit = self.balance - self.starting_balance

        # Phase 1 (ladder payouts): firm-specific ladder
        ladder_len = len(self.payout_ladder)
        floor = self.post_ladder_floor
        if self.payout_count <= ladder_len:
            available = self.balance - self.safety_net
            if available <= 500:
                return 0
            cashout_amount = min(available, max_payout)
        # Phase 2: first time profit hits 75% of floor → cash $5K
        elif not hasattr(self, '_phase2_done') or not self._phase2_done:
            phase2_target = int(floor * 0.75)
            if profit < phase2_target:
                return 0
            cashout_amount = 5000
            self._phase2_done = True
        # Phase 3: build back to $20K profit → cash $5K → FULL SEND
        elif not hasattr(self, '_phase3_done') or not self._phase3_done:
            if profit < floor:
                return 0
            cashout_amount = 5000
            self._phase3_done = True
            self.full_send = True  # 2nd time at $20K → max contracts till bust
        # Phase 4 (full send): max contracts, cash everything above $70K
        else:
            keep_balance = self.starting_balance + floor
            if self.balance <= keep_balance + 500:
                return 0
            cashout_amount = self.balance - keep_balance

        cashout_amount = max(0, min(cashout_amount, profit))
        if cashout_amount < 500:  # Apex minimum
            return 0

        # Execute cashout
        self.balance -= cashout_amount
        self.total_cashed_out += cashout_amount
        self.peak_balance = self.balance  # reset peak after cashout
        self.daily_pnls = []  # reset consistency tracking

        # Only reset contracts if cashout dropped below safety net
        if self.balance < self.safety_net:
            self.past_safety_net = False
            self.max_contracts = 2  # dropped below — rebuild
        # else: stay at 4ct (cashed $2K but still above safety net)
        self.cashouts.append({
            "payout_num": self.payout_count,
            "amount": cashout_amount,
            "balance_after": self.balance,
            "date": date,
        })
        return cashout_amount

    def summary(self) -> dict:
        return {
            "firm_name": self.firm_name,
            "starting_balance": self.starting_balance,
            "final_balance": self.balance,
            "profit_in_account": self.balance - self.starting_balance,
            "total_cashed_out": self.total_cashed_out,
            "total_earned": (self.balance - self.starting_balance) + self.total_cashed_out,
            "payout_count": self.payout_count,
            "cashouts": self.cashouts,
            "busted": self.busted,
            "past_safety_net": self.past_safety_net,
            "max_contracts": self.max_contracts,
        }


def _compound_contracts(base_contracts: int, starting_equity: float,
                        total_pnl: float, peak_pnl: float = 0) -> int:
    """True compounding: size proportional to current equity.

    Starting equity $10,000 with 5 MNQ base:
      $10,000 → 5ct
      $20,000 → 10ct
      $30,000 → 15ct
      $50,000 → 25ct

    Scales down naturally as equity drops. Cap at MAX_CONTRACTS.
    50% drawdown from peak = reset to base.
    """
    current_equity = starting_equity + total_pnl
    if current_equity <= 0:
        return base_contracts

    # 50% DD protection
    peak_equity = starting_equity + peak_pnl
    if peak_equity > starting_equity:
        dd_pct = (peak_equity - current_equity) / peak_equity
        if dd_pct >= 0.50:
            return base_contracts

    # Proportional sizing: contracts scale linearly with equity
    ratio = current_equity / starting_equity
    scaled = max(base_contracts, int(base_contracts * ratio))
    return min(scaled, MAX_CONTRACTS)


def _scale_contracts(base_contracts: int, total_pnl: float, scale_step: float,
                     peak_pnl: float = 0) -> int:
    """Double contracts for every scale_step of profit.

    $0-$2499: base (5)
    $2500-$4999: 2x (10)
    $5000-$9999: 4x (20)
    $10000+: capped at MAX_CONTRACTS (40)

    Safety: if drawdown from peak > 50%, reset to base contracts.
    """
    if total_pnl <= 0 or scale_step <= 0:
        return base_contracts

    # Drawdown protection: if equity dropped 50%+ from peak, reset to base
    if peak_pnl > 0:
        drawdown_pct = (peak_pnl - total_pnl) / peak_pnl
        if drawdown_pct >= 0.50:
            return base_contracts

    doublings = int(total_pnl / scale_step)
    scaled = base_contracts * (2 ** min(doublings, 4))  # max 4 doublings
    return min(scaled, MAX_CONTRACTS)


def _run_backtest(ticker: str, dates: list, point_value: float, contracts: int,
                  quiet: bool = False, scale_step: float = 0,
                  compound: bool = False, starting_equity: float = 10000,
                  apex: str = None) -> dict:
    """Run a full backtest and return results dict.

    Args:
        scale_step: If > 0, double contracts every scale_step dollars of profit.
                    E.g., scale_step=2500 means double at $2500, $5000, $10000, etc.
        apex: Prop firm name (e.g., "apex", "mff", "lucid"). None = disabled.
              Loads config from PROP_FIRMS in jadecap_config.py.
    """
    global POINT_VALUE, FIXED_CONTRACTS
    orig_pv, orig_fc = POINT_VALUE, FIXED_CONTRACTS
    POINT_VALUE = point_value
    FIXED_CONTRACTS = contracts

    try:
        # Bulk fetch: one call for the entire period + 10 days lookback for indicators
        # 500 days lookback for indicator warmup (EMA200 needs 200+ trading days = ~300 calendar days)
        lookback_start = (datetime.strptime(dates[0], "%Y-%m-%d") - timedelta(days=500)).strftime("%Y-%m-%d")
        bulk_end = (datetime.strptime(dates[-1], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        df_all = _fetch_bulk(ticker, lookback_start, bulk_end)
        if df_all is None or df_all.empty:
            print("  ERROR: Bulk fetch returned no data")
            return {"ticker": ticker, "total_trades": 0, "wins": 0, "losses": 0,
                    "closes": 0, "no_trade_days": len(dates), "win_rate": 0,
                    "avg_win": 0, "avg_loss": 0, "profit_factor": 0,
                    "total_pnl": 0, "max_drawdown": 0, "trades": [],
                    "label": f"{contracts} ct", "period": f"{dates[0]} to {dates[-1]}",
                    "days_scanned": len(dates), "point_value": point_value,
                    "contracts": contracts}

        # Pre-compute ALL indicators on full dataset
        indicators = _precompute_indicators(df_all)

        trades = []
        total_pnl = 0.0
        peak_pnl = 0.0
        wins = 0
        losses = 0
        closes = 0
        no_trade_days = 0
        prev_df = None
        prev_session_df = None  # Prior day's session bars for SFP mapping
        consecutive_losses = 0

        # Prop firm simulation
        if apex:
            from openclaw.jadecap_config import PROP_FIRMS
            firm_config = PROP_FIRMS.get(apex, PROP_FIRMS.get("apex", {}))
            apex_sim = ApexSimulator(firm_config=firm_config)
        else:
            apex_sim = None
        cashout_log = []
        trade_day_count = 0  # for Apex cashout timing (every 8 trading days)

        for date in dates:
            # Apex mode: check if busted
            if apex_sim and apex_sim.busted:
                if not quiet:
                    print(f"  {date}  ACCOUNT BUSTED — liquidation hit")
                break

            # Progressive scaling: adjust FIXED_CONTRACTS before each day
            if apex_sim:
                FIXED_CONTRACTS = apex_sim.get_contracts()
            elif compound:
                FIXED_CONTRACTS = _compound_contracts(contracts, starting_equity, total_pnl, peak_pnl)
            elif scale_step > 0:
                FIXED_CONTRACTS = _scale_contracts(contracts, total_pnl, scale_step, peak_pnl)

            result = backtest_day(ticker, date, prev_df, consecutive_losses,
                                  indicators=indicators, df_all=df_all,
                                  prev_session_df=prev_session_df,
                                  full_send_mode=apex_sim.full_send if apex_sim else False)
            if result.get("_df") is not None:
                prev_df = result["_df"]
                # Save today's session bars as prev_session for tomorrow's SFP mapping
                today_session = result["_df"].between_time("09:30", "16:00")
                if not today_session.empty:
                    prev_session_df = today_session
            if result["status"] != "ok":
                continue

            day_trades = result.get("trades", [])
            if not day_trades:
                no_trade_days += 1
                continue

            day_had_trade = False
            for trade in day_trades:
                pnl = trade["pnl"]
                total_pnl += pnl
                peak_pnl = max(peak_pnl, total_pnl)
                result_str = trade["result"]
                day_had_trade = True

                # Apex: update account and check cashout
                if apex_sim:
                    apex_sim.update(pnl, date)
                    trade["apex_balance"] = apex_sim.balance
                    trade["apex_contracts"] = apex_sim.max_contracts

                if result_str in ("WIN", "T1_WIN"):
                    wins += 1
                    consecutive_losses = 0
                elif result_str == "LOSS":
                    losses += 1
                    consecutive_losses += 1
                else:
                    closes += 1
                    if pnl < 0:
                        consecutive_losses += 1
                    else:
                        consecutive_losses = 0

                # Attach EMA 200 data to trade for tracking
                trade["ema200_alignment"] = result.get("ema200_alignment", "unknown")
                trade["open_vs_ema200"] = result.get("open_vs_ema200", "unknown")
                trade["held_ema200"] = result.get("held_above_ema", result.get("held_below_ema", None))

                trades.append(trade)
                if not quiet:
                    half = " (HALF)" if trade.get("half_size") else ""
                    model = trade.get("model", "?")
                    icon = {"WIN": "+", "LOSS": "-"}.get(result_str, "=")
                    ct_str = f" [{trade['contracts']}ct]" if scale_step > 0 else ""
                    print(f"  {date}  {icon} {trade['direction']:5s} {trade['kz']:3s} "
                          f"[{model:12s}] "
                          f"entry:{trade['entry']:.0f} stop:{trade['stop']:.0f} "
                          f"target:{trade['target']:.0f} exit:{trade['exit']:.0f} "
                          f"{result_str:5s}{half}{ct_str} ${pnl:+.0f}  (total: ${total_pnl:+.0f})")

            # Apex cashout check once per day (after all trades)
            if day_had_trade and apex_sim:
                trade_day_count += 1
                if trade_day_count >= 8 and apex_sim.past_safety_net:
                    cashout = apex_sim.check_cashout(date)
                    if cashout > 0:
                        trade_day_count = 0
                        if not quiet:
                            print(f"  {date}  CASHOUT #{apex_sim.payout_count}: "
                                  f"${cashout:+,.0f} | Balance: ${apex_sim.balance:,.0f} | "
                                  f"Total cashed: ${apex_sim.total_cashed_out:,.0f}")

        total_trades = wins + losses + closes
        win_rate = wins / total_trades * 100 if total_trades > 0 else 0
        avg_win = np.mean([t["pnl"] for t in trades if t["result"] in ("WIN", "T1_WIN")]) if wins > 0 else 0
        avg_loss = np.mean([t["pnl"] for t in trades if t["result"] == "LOSS"]) if losses > 0 else 0
        profit_factor = abs(avg_win * wins / (avg_loss * losses)) if (losses > 0 and avg_loss != 0) else float("inf")

        peak = 0
        max_dd = 0
        running = 0
        for t in trades:
            running += t["pnl"]
            peak = max(peak, running)
            max_dd = max(max_dd, peak - running)

        # EMA 200 alignment stats
        from collections import Counter
        ema_alignments = Counter(t.get("ema200_alignment", "unknown") for t in trades)
        ema_wins = Counter(t.get("ema200_alignment", "unknown")
                          for t in trades if t["result"] in ("WIN", "T1_WIN"))
        ema_stats = {}
        for alignment, count in ema_alignments.items():
            w = ema_wins.get(alignment, 0)
            ema_stats[alignment] = {"trades": count, "wins": w,
                                     "wr": round(w / count * 100, 1) if count > 0 else 0}

        # Apex summary
        apex_summary = apex_sim.summary() if apex_sim else None

        return {
            "ticker": ticker,
            "point_value": point_value,
            "contracts": contracts,
            "label": f"{apex_sim.firm_name} ${apex_sim.starting_balance:,.0f}" if apex_sim else f"{contracts} {'MNQ' if point_value == 2 else 'NQ'} (${point_value}/pt)",
            "apex": apex_summary,
            "period": f"{dates[0]} to {dates[-1]}",
            "days_scanned": len(dates),
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "closes": closes,
            "no_trade_days": no_trade_days,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "max_drawdown": max_dd,
            "ema200_stats": ema_stats,
            "trades": trades,
        }
    finally:
        POINT_VALUE = orig_pv
        FIXED_CONTRACTS = orig_fc


def _print_comparison(results: list):
    """Print side-by-side comparison of multiple backtest configs."""
    print(f"\n{'='*90}")
    print(f"  MULTI-CONTRACT COMPARISON")
    print(f"{'='*90}")

    headers = ["Metric"] + [r["label"] for r in results]
    rows = [
        ("Trades", [str(r["total_trades"]) for r in results]),
        ("Win Rate", [f"{r['win_rate']:.0f}%" for r in results]),
        ("Avg Win", [f"${r['avg_win']:+,.0f}" for r in results]),
        ("Avg Loss", [f"${r['avg_loss']:+,.0f}" for r in results]),
        ("Profit Factor", [f"{r['profit_factor']:.2f}" for r in results]),
        ("Total P&L", [f"${r['total_pnl']:+,.0f}" for r in results]),
        ("Max Drawdown", [f"${r['max_drawdown']:,.0f}" for r in results]),
    ]

    col_widths = [max(len(h), 15) for h in headers]
    for label, vals in rows:
        col_widths[0] = max(col_widths[0], len(label))
        for j, v in enumerate(vals):
            col_widths[j + 1] = max(col_widths[j + 1], len(v))

    header_line = "  " + "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("  " + "  ".join("-" * w for w in col_widths))
    for label, vals in rows:
        line = "  " + label.ljust(col_widths[0])
        for j, v in enumerate(vals):
            line += "  " + v.ljust(col_widths[j + 1])
        print(line)
    print()


def main():
    parser = argparse.ArgumentParser(description="JadeCap Backtester")
    parser.add_argument("--ticker", default="NQ", help="Instrument (default: NQ)")
    parser.add_argument("--days", type=int, default=20, help="Number of trading days")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--point-value", type=float, default=None,
                        help="Dollar per point (2=MNQ, 20=NQ). Default: 2")
    parser.add_argument("--contracts", type=int, default=None,
                        help="Number of contracts. Default: 5")
    parser.add_argument("--compare", action="store_true",
                        help="Run 3 configs (5 MNQ, 10 MNQ, 1 NQ) and compare")
    parser.add_argument("--scale", type=float, default=0,
                        help="Double contracts every N dollars of profit (e.g., 2500)")
    parser.add_argument("--compound", action="store_true",
                        help="True compounding: size based on total equity, not fixed steps")
    parser.add_argument("--apex", nargs="?", const="apex", default=None,
                        help="Simulate prop firm account rules (default: apex). "
                             "Options: apex, mff, lucid")
    parser.add_argument("--save-memory", action="store_true",
                        help="Save trade outcomes to BM25 agent memory")
    parser.add_argument("--kz", default=None,
                        help="Kill zone preset: '930' (9:30-11:30), '830' (8:30-11:30), "
                             "'full' (6:00-16:00). Default: use KILL_ZONES constant")
    args = parser.parse_args()

    # Override kill zones if --kz specified
    global KILL_ZONES
    if args.kz == "930":
        KILL_ZONES = {"AM": ("09:30", "11:30"), "PM": ("13:00", "16:00")}
    elif args.kz == "830":
        KILL_ZONES = {"AM": ("08:30", "11:30"), "PM": ("13:00", "16:00")}
    elif args.kz == "full":
        KILL_ZONES = {"FULL": ("06:00", "16:00")}

    ticker = args.ticker

    if args.start and args.end:
        start = datetime.strptime(args.start, "%Y-%m-%d")
        end = datetime.strptime(args.end, "%Y-%m-%d")
        dates = []
        d = start
        while d <= end:
            if d.weekday() < 5:
                dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
    else:
        end = datetime.now()
        dates = []
        d = end
        while len(dates) < args.days:
            if d.weekday() < 5:
                dates.append(d.strftime("%Y-%m-%d"))
            d -= timedelta(days=1)
        dates.reverse()

    if args.compare:
        configs = [
            (2, 5, "5 MNQ"),
            (2, 10, "10 MNQ"),
            (20, 1, "1 NQ"),
        ]
        print(f"\n  JadeCap Multi-Contract Backtest — {ticker}")
        print(f"   {len(dates)} trading days: {dates[0]} → {dates[-1]}")
        print()

        all_results = []
        for pv, ct, label in configs:
            print(f"\n  --- Running: {label} (${pv}/pt x {ct} contracts) ---")
            result = _run_backtest(ticker, dates, pv, ct, quiet=True, scale_step=args.scale,
                                  compound=args.compound, apex=args.apex)
            all_results.append(result)
            print(f"      P&L: ${result['total_pnl']:+,.0f} | "
                  f"WR: {result['win_rate']:.0f}% | "
                  f"PF: {result['profit_factor']:.2f} | "
                  f"MaxDD: ${result['max_drawdown']:,.0f}")

        _print_comparison(all_results)
        trades_for_memory = all_results[0]["trades"]
        result_for_save = all_results[0]
    else:
        point_value = args.point_value if args.point_value else POINT_VALUE
        contracts = args.contracts if args.contracts else FIXED_CONTRACTS

        print(f"\n  JadeCap Backtest — {ticker}")
        print(f"   {len(dates)} trading days: {dates[0]} → {dates[-1]}")
        print(f"   Point value: ${point_value} | Contracts: {contracts}")
        print()

        result_for_save = _run_backtest(ticker, dates, point_value, contracts,
                                        scale_step=args.scale, compound=args.compound,
                                        apex=args.apex)
        trades_for_memory = result_for_save["trades"]

        r = result_for_save
        print(f"\n{'='*70}")
        print(f"  BACKTEST RESULTS — {ticker} | {dates[0]} → {dates[-1]}")
        print(f"{'='*70}")
        print(f"  Days scanned:     {r['days_scanned']}")
        print(f"  Trading days:     {r['total_trades']} ({r['total_trades']/r['days_scanned']*100:.0f}%)")
        print(f"  No-trade days:    {r['no_trade_days']}")
        print(f"  Wins:             {r['wins']} ({r['win_rate']:.0f}%)")
        print(f"  Losses:           {r['losses']}")
        print(f"  Hard closes:      {r['closes']}")
        print(f"  Avg win:          ${r['avg_win']:+,.0f}")
        print(f"  Avg loss:         ${r['avg_loss']:+,.0f}")
        print(f"  Profit factor:    {r['profit_factor']:.2f}")
        print(f"  Total P&L:        ${r['total_pnl']:+,.0f}")
        print(f"  Max drawdown:     ${r['max_drawdown']:,.0f}")

        # Apex summary
        if r.get("apex"):
            a = r["apex"]
            firm_label = a.get("firm_name", "APEX $50K PA")
            print(f"\n  {'='*50}")
            print(f"  {firm_label.upper()} ACCOUNT SIMULATION")
            print(f"  {'='*50}")
            print(f"  Starting balance: ${a['starting_balance']:,.0f}")
            print(f"  Final balance:    ${a['final_balance']:,.0f}")
            print(f"  Profit in acct:   ${a['profit_in_account']:+,.0f}")
            print(f"  Total cashed out: ${a['total_cashed_out']:+,.0f}")
            print(f"  TOTAL EARNED:     ${a['total_earned']:+,.0f}")
            print(f"  Payouts:          {a['payout_count']}")
            print(f"  Busted:           {'YES' if a['busted'] else 'NO'}")
            if a["cashouts"]:
                print(f"\n  Cashout History:")
                for c in a["cashouts"]:
                    print(f"    #{c['payout_num']:2d}  {c['date']}  ${c['amount']:+,.0f}  "
                          f"(balance after: ${c['balance_after']:,.0f})")

        from collections import Counter
        # KZ session breakdown (AM vs PM)
        kz_counts = Counter(t.get("kz", "?") for t in trades_for_memory)
        kz_wins = Counter(t.get("kz", "?") for t in trades_for_memory if t["result"] in ("WIN", "T1_WIN"))
        kz_pnl = {}
        for t in trades_for_memory:
            kz = t.get("kz", "?")
            kz_pnl[kz] = kz_pnl.get(kz, 0) + t["pnl"]
        print(f"\n  Kill Zone Breakdown:")
        for kz in sorted(kz_counts.keys()):
            count = kz_counts[kz]
            w = kz_wins.get(kz, 0)
            wr = w / count * 100 if count > 0 else 0
            print(f"    {kz:5s}: {count:3d} trades, {w:2d} wins ({wr:.0f}%), P&L: ${kz_pnl.get(kz, 0):+,.0f}")

        model_counts = Counter(t.get("model", "?") for t in trades_for_memory)
        model_wins = Counter(t.get("model", "?") for t in trades_for_memory if t["result"] in ("WIN", "T1_WIN"))
        print(f"\n  Entry Models:")
        for model, count in model_counts.most_common():
            w = model_wins.get(model, 0)
            wr = w / count * 100 if count > 0 else 0
            print(f"    {model:15s}: {count:3d} trades, {w:2d} wins ({wr:.0f}%)")

        # Loss review breakdown
        loss_trades = [t for t in trades_for_memory if t.get("loss_review")]
        if loss_trades:
            review_counts = Counter(t["loss_review"] for t in loss_trades)
            print(f"\n  Loss Review (post-trade analysis):")
            for review, count in review_counts.most_common():
                print(f"    {review:35s}: {count:3d}")
            pm_after_loss = [t for t in trades_for_memory if t.get("pm_after_am_loss")]
            if pm_after_loss:
                pm_wins = sum(1 for t in pm_after_loss if t["result"] in ("WIN", "T1_WIN"))
                print(f"    PM trades after AM loss:          {len(pm_after_loss)} ({pm_wins} wins)")

        # EMA 200 alignment stats
        ema_stats = result_for_save.get("ema200_stats", {})
        if ema_stats:
            print(f"\n  EMA 200 Alignment (8:29 AM, all timeframes):")
            for alignment in ["ALL_ABOVE", "ALL_BELOW"]:
                if alignment in ema_stats:
                    s = ema_stats[alignment]
                    print(f"    {alignment:15s}: {s['trades']:3d} trades, {s['wins']:2d} wins ({s['wr']:.0f}%)")
            for alignment, s in sorted(ema_stats.items()):
                if alignment not in ("ALL_ABOVE", "ALL_BELOW", "unknown"):
                    print(f"    {alignment:15s}: {s['trades']:3d} trades, {s['wins']:2d} wins ({s['wr']:.0f}%)")
        print()

    # Save results JSON
    workspace = os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace")
    out_path = os.path.join(workspace, "backtest-results.json")
    with open(out_path, "w") as f:
        json.dump(result_for_save, f, indent=2, default=str)
    print(f"  Saved to: {out_path}")

    # Save to memory (if --save-memory)
    if args.save_memory and trades_for_memory:
        _save_trades_to_memory(trades_for_memory, ticker, dates)


if __name__ == "__main__":
    main()
