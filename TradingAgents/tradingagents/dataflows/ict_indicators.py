"""
JadeCap ICT Indicator Suite

Computes all ICT indicators defined in jadecap_config using:
  - smartmoneyconcepts (smc)  — FVG, OB, BOS/CHoCH, liquidity, sessions, prev H/L
  - stockstats                — EMA, ATR, ADX, RSI, Supertrend
  - manual calculations       — Midnight Open, Kill Zone timer, Fibonacci OTE, contract sizing

Every public function returns a formatted string ready for LLM consumption.
"""

import logging
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import pytz
from smartmoneyconcepts.smc import smc
from stockstats import wrap

from tradingagents.jadecap_config import (
    AMD,
    INSTRUMENTS,
    ICT_INDICATORS,
    KILL_ZONES,
    HARD_RULES,
    RISK,
    SESSIONS,
    TIMEFRAMES,
    calculate_contracts,
)

logger = logging.getLogger(__name__)

EST = pytz.timezone("US/Eastern")


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _to_est(dt: datetime) -> datetime:
    """Convert a datetime to US/Eastern, or localise a naive datetime."""
    if dt.tzinfo is None:
        return EST.localize(dt)
    return dt.astimezone(EST)


def _to_smc_format(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has lowercase OHLCV columns and a DatetimeIndex."""
    df = df.copy()
    rename = {}
    for c in df.columns:
        cl = c.strip().lower()
        if cl in ("open", "high", "low", "close", "volume"):
            rename[c] = cl
    df = df.rename(columns=rename)

    # Ensure DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        for col in ("Date", "date", "datetime", "Datetime", "ts_event"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df = df.set_index(col)
                break

    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["close"])
    return df


def _fmt(value, decimals: int = 2) -> str:
    """Format a numeric value, returning 'N/A' for NaN / None."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    return f"{value:.{decimals}f}"


def _get_instrument(name: str = "NQ") -> dict:
    """Return instrument config from jadecap_config."""
    return INSTRUMENTS.get(name, INSTRUMENTS["NQ"])


def _calc_contracts(stop_points: float, instrument: str = "NQ") -> int:
    """Wrapper around jadecap_config.calculate_contracts."""
    return calculate_contracts(stop_points, instrument)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Fair Value Gaps
# ═══════════════════════════════════════════════════════════════════════════════

def get_fvg(df: pd.DataFrame, timeframe: str) -> str:
    """Fair Value Gaps — 3-candle imbalance zones via smc.fvg()."""
    df = _to_smc_format(df)
    if df.empty:
        return f"\n## Fair Value Gaps [{timeframe}]\n  No data."

    join = ICT_INDICATORS.get("fvg", {}).get("join_consecutive", True)
    result = smc.fvg(df, join_consecutive=join)

    fvgs = []
    for i in range(len(result)):
        if not np.isnan(result["FVG"].iloc[i]):
            fvgs.append({
                "direction": "bullish" if result["FVG"].iloc[i] == 1 else "bearish",
                "top": float(result["Top"].iloc[i]),
                "bottom": float(result["Bottom"].iloc[i]),
                "mitigated": (
                    not np.isnan(result["MitigatedIndex"].iloc[i])
                    and result["MitigatedIndex"].iloc[i] != 0
                ),
                "date": str(df.index[i]),
            })

    unmitigated = [f for f in fvgs if not f["mitigated"]]
    mitigated = [f for f in fvgs if f["mitigated"]]

    lines = [
        f"\n## Fair Value Gaps [{timeframe}]",
        f"  Total: {len(fvgs)} | Unmitigated: {len(unmitigated)} | Mitigated: {len(mitigated)}",
    ]
    if not unmitigated:
        lines.append("  No unmitigated FVGs.")
    else:
        for f in unmitigated[-10:]:
            tag = "BULL" if f["direction"] == "bullish" else "BEAR"
            lines.append(
                f"  {tag} FVG @ {_fmt(f['bottom'])} – {_fmt(f['top'])} | {f['date']}"
            )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Order Blocks
# ═══════════════════════════════════════════════════════════════════════════════

def get_order_blocks(df: pd.DataFrame, timeframe: str) -> str:
    """Order Blocks — last opposing candle before displacement via smc.ob()."""
    df = _to_smc_format(df)
    if df.empty:
        return f"\n## Order Blocks [{timeframe}]\n  No data."

    swing_len = ICT_INDICATORS.get("order_blocks", {}).get("swing_length", 5)
    swing_hl = smc.swing_highs_lows(df, swing_length=swing_len)
    result = smc.ob(df, swing_hl)

    obs = []
    for i in range(len(result)):
        if not np.isnan(result["OB"].iloc[i]):
            mitigated = (
                not np.isnan(result["MitigatedIndex"].iloc[i])
                and result["MitigatedIndex"].iloc[i] != 0
            )
            obs.append({
                "direction": "bullish" if result["OB"].iloc[i] == 1 else "bearish",
                "top": float(result["Top"].iloc[i]),
                "bottom": float(result["Bottom"].iloc[i]),
                "volume": float(result["OBVolume"].iloc[i]),
                "pct": float(result["Percentage"].iloc[i]),
                "mitigated": mitigated,
                "date": str(df.index[i]),
            })

    active = [o for o in obs if not o["mitigated"]]
    lines = [
        f"\n## Order Blocks [{timeframe}]",
        f"  Total: {len(obs)} | Active: {len(active)}",
    ]
    if not obs:
        lines.append("  No Order Blocks found.")
    else:
        for o in obs[-10:]:
            tag = "BULL" if o["direction"] == "bullish" else "BEAR"
            status = "MITIGATED" if o["mitigated"] else "ACTIVE"
            lines.append(
                f"  {tag} OB @ {_fmt(o['bottom'])} – {_fmt(o['top'])} | "
                f"vol: {o['volume']:.0f} | str: {o['pct']:.1f}% | {status}"
            )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Session Levels (Asia / London / NY)
# ═══════════════════════════════════════════════════════════════════════════════

def get_session_levels(df: pd.DataFrame) -> str:
    """Session High/Low for Asia, London, NY via smc.sessions()."""
    df = _to_smc_format(df)
    lines = ["\n## Session Levels"]
    if df.empty:
        lines.append("  No data.")
        return "\n".join(lines)

    for key, sess in SESSIONS.items():
        try:
            result = smc.sessions(
                df, "Custom",
                start_time=sess["start"],
                end_time=sess["end"],
                time_zone="UTC-5",
            )
            active_mask = result["Active"] == 1
            if active_mask.any():
                high = float(result.loc[active_mask, "High"].max())
                low = float(result.loc[active_mask, "Low"].min())
                lines.append(
                    f"  {sess['name']}: High={_fmt(high)} | Low={_fmt(low)} | "
                    f"Bars={int(active_mask.sum())}"
                )
            else:
                lines.append(f"  {sess['name']}: No active bars")
        except Exception as e:
            lines.append(f"  {sess['name']}: Error — {e}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Equal Highs / Lows (BSL / SSL)
# ═══════════════════════════════════════════════════════════════════════════════

def get_equal_highs_lows(df: pd.DataFrame, timeframe: str) -> str:
    """Buy-Side / Sell-Side Liquidity via smc.liquidity()."""
    df = _to_smc_format(df)
    if df.empty:
        return f"\n## Liquidity Pools [{timeframe}]\n  No data."

    swing_len = ICT_INDICATORS.get("equal_highs_lows", {}).get("swing_length", 5)
    swing_hl = smc.swing_highs_lows(df, swing_length=swing_len)
    result = smc.liquidity(df, swing_hl)

    pools = []
    for i in range(len(result)):
        if not np.isnan(result["Liquidity"].iloc[i]):
            pools.append({
                "type": "BSL" if result["Liquidity"].iloc[i] == 1 else "SSL",
                "level": float(result["Level"].iloc[i]),
                "swept": (
                    int(result["Swept"].iloc[i])
                    if not np.isnan(result["Swept"].iloc[i]) else None
                ),
                "date": str(df.index[i]),
            })

    bsl = [p for p in pools if p["type"] == "BSL"]
    ssl = [p for p in pools if p["type"] == "SSL"]
    lines = [
        f"\n## Liquidity Pools [{timeframe}]",
        f"  Total: {len(pools)} | BSL: {len(bsl)} | SSL: {len(ssl)}",
    ]
    if not pools:
        lines.append("  No equal highs/lows found.")
    else:
        for p in pools[-10:]:
            swept = f"SWEPT at idx {p['swept']}" if p["swept"] else "NOT SWEPT"
            lines.append(f"  {p['type']} @ {_fmt(p['level'])} | {swept}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Market Structure (MSS / CHoCH)
# ═══════════════════════════════════════════════════════════════════════════════

def get_market_structure(df: pd.DataFrame, timeframe: str) -> str:
    """Market Structure Shift / Change of Character via smc.bos_choch()."""
    df = _to_smc_format(df)
    if df.empty:
        return f"\n## Market Structure [{timeframe}]\n  No data."

    cfg = ICT_INDICATORS.get("mss_choch", {})
    swing_len = cfg.get("swing_length", 5)
    close_break = cfg.get("close_break", True)
    swing_hl = smc.swing_highs_lows(df, swing_length=swing_len)
    result = smc.bos_choch(df, swing_hl, close_break=close_break)

    structures = []
    for i in range(len(result)):
        bos_val = result["BOS"].iloc[i]
        choch_val = result["CHOCH"].iloc[i]
        if not np.isnan(bos_val):
            structures.append({
                "type": "BOS",
                "direction": "bullish" if bos_val == 1 else "bearish",
                "level": float(result["Level"].iloc[i]),
                "date": str(df.index[i]),
            })
        if not np.isnan(choch_val):
            structures.append({
                "type": "CHoCH",
                "direction": "bullish" if choch_val == 1 else "bearish",
                "level": float(result["Level"].iloc[i]),
                "date": str(df.index[i]),
            })

    lines = [
        f"\n## Market Structure [{timeframe}]",
        f"  Total signals: {len(structures)}",
    ]
    if not structures:
        lines.append("  No BOS or CHoCH detected.")
    else:
        for s in structures[-10:]:
            tag = "BULL" if s["direction"] == "bullish" else "BEAR"
            lines.append(
                f"  {s['type']} {tag} @ {_fmt(s['level'])} | {s['date']}"
            )
        latest = structures[-1]
        lines.append(
            f"  >>> CURRENT ORDER FLOW: {latest['direction'].upper()} ({latest['type']})"
        )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Previous Day High / Low
# ═══════════════════════════════════════════════════════════════════════════════

def get_prev_day_levels(df: pd.DataFrame) -> str:
    """Previous Day High and Low via smc.previous_high_low()."""
    df = _to_smc_format(df)
    lines = ["\n## Previous Day Levels"]
    if df.empty:
        lines.append("  No data.")
        return "\n".join(lines)

    try:
        result = smc.previous_high_low(df, time_frame="1D")
        last_valid = result.dropna()
        if last_valid.empty:
            lines.append("  No previous day levels available.")
            return "\n".join(lines)

        last = last_valid.iloc[-1]
        pdh = float(last["PreviousHigh"])
        pdl = float(last["PreviousLow"])
        broken_h = bool(last["BrokenHigh"])
        broken_l = bool(last["BrokenLow"])

        lines.append(
            f"  PDH (Previous Day High): {_fmt(pdh)} | Broken: {'YES' if broken_h else 'NO'}"
        )
        lines.append(
            f"  PDL (Previous Day Low):  {_fmt(pdl)} | Broken: {'YES' if broken_l else 'NO'}"
        )
        if broken_h:
            lines.append(
                "  WARNING: PDH already taken today — NO TRADE for longs targeting PDH"
            )
        if broken_l:
            lines.append(
                "  WARNING: PDL already taken today — NO TRADE for shorts targeting PDL"
            )
    except Exception as e:
        lines.append(f"  Error: {e}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Midnight Open
# ═══════════════════════════════════════════════════════════════════════════════

def get_midnight_open(df_1m: pd.DataFrame, trade_date: str) -> str:
    """NY Midnight Open — price at 12:00 AM EST from 1-minute data."""
    df = _to_smc_format(df_1m)
    lines = ["\n## Midnight Open (12:00 AM EST)"]
    if df.empty:
        lines.append("  No 1m data available.")
        return "\n".join(lines)

    try:
        # Try to find the bar closest to midnight EST
        target_date = pd.Timestamp(trade_date)
        midnight_est = EST.localize(
            datetime.combine(target_date.date(), time(0, 0))
        )

        if df.index.tz is None:
            idx = df.index.tz_localize("UTC").tz_convert(EST)
        else:
            idx = df.index.tz_convert(EST)

        # Find bars within the first 5 minutes of midnight
        mask = (idx >= midnight_est) & (idx < midnight_est + timedelta(minutes=5))
        midnight_bars = df.loc[mask]

        if not midnight_bars.empty:
            mo = float(midnight_bars.iloc[0]["open"])
        else:
            # Fallback: first bar of trade_date (not first bar of entire lookback)
            trade_dt = pd.Timestamp(trade_date).date()
            day_bars = df.loc[df.index.map(lambda t: t.date() if hasattr(t, 'date') else pd.Timestamp(t).date()) == trade_dt]
            if not day_bars.empty:
                mo = float(day_bars.iloc[0]["open"])
            else:
                mo = float(df.iloc[-1]["close"])  # last known price as final fallback
            lines.append("  (Approximated from first available bar of trade date)")

        current = float(df.iloc[-1]["close"])
        zone = "PREMIUM" if current > mo else "DISCOUNT"
        diff = current - mo

        lines.append(f"  Midnight Open Price: {_fmt(mo)}")
        lines.append(f"  Current Price:       {_fmt(current)}")
        lines.append(f"  Zone: {zone} ({diff:+.2f} from midnight)")
        if zone == "PREMIUM":
            lines.append("  RULE: In PREMIUM — only SHORT setups valid")
        else:
            lines.append("  RULE: In DISCOUNT — only LONG setups valid")
    except Exception as e:
        lines.append(f"  Error: {e}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Kill Zone + AMD Status
# ═══════════════════════════════════════════════════════════════════════════════

def get_killzone_status(current_time: datetime = None) -> str:
    """Kill Zone timer and AMD phase check."""
    now_est = _to_est(current_time) if current_time else datetime.now(EST)
    current_hm = now_est.strftime("%H:%M")
    weekday = now_est.weekday()  # 0=Mon, 5=Sat, 6=Sun
    t_min = now_est.hour * 60 + now_est.minute

    # Weekend: Sat all day, Sun before 6PM, Fri after 5PM
    is_weekend = (
        weekday == 5
        or (weekday == 6 and t_min < 18 * 60)
        or (weekday == 4 and t_min >= 17 * 60)
    )
    if is_weekend:
        open_day = "today at 6PM EST" if weekday == 6 else "Sunday 6PM EST"
        return (
            f"\n## Kill Zone Status\n"
            f"  Current Time (EST): {current_hm} ({now_est.strftime('%A')})\n"
            f"  FUTURES CLOSED (weekend). Opens {open_day}.\n"
            f"  Can Trade: NO\n"
        )

    # ── Kill Zone ──
    active_kz = None
    for _key, kz in KILL_ZONES.items():
        if not kz.get("active", True):
            continue
        if kz["start"] <= current_hm <= kz["end"]:
            active_kz = kz["name"]
            break

    lines = [
        "\n## Kill Zone Status",
        f"  Current Time (EST): {current_hm} ({now_est.strftime('%A')})",
        f"  Futures Market: OPEN (futures trade 23h, Sun 6PM - Fri 5PM EST)",
        f"  Inside Kill Zone: {'YES' if active_kz else 'NO'}",
    ]
    if active_kz:
        lines.append(f"  Active Zone: {active_kz}")
    else:
        lines.append("  Outside Kill Zone — no JadeCap entries until next KZ window")
        lines.append("  Next windows: AM 9:30-11:30 | Silver Bullet 10:00-11:00 | PM 1:00-4:00 EST")

    # ── AMD Phase ──
    current_phase = "unknown"
    current_session = None
    for _key, sess in SESSIONS.items():
        start, end = sess["start"], sess["end"]
        if start > end:  # overnight
            if current_hm >= start or current_hm <= end:
                current_phase = sess.get("amd_phase", "unknown")
                current_session = sess["name"]
                break
        else:
            if start <= current_hm <= end:
                current_phase = sess.get("amd_phase", "unknown")
                current_session = sess["name"]
                break

    phase_info = AMD.get(current_phase, {})
    # Can Trade = inside a Kill Zone AND in distribution phase
    # Kill Zone check is the primary gate; AMD phase is informational
    can_trade = active_kz is not None

    lines.append(f"\n## AMD Phase")
    lines.append(f"  Phase: {current_phase.upper()}")
    lines.append(f"  Session: {current_session or 'Between sessions'}")
    lines.append(f"  Can Trade: {'YES — inside Kill Zone' if can_trade else 'NO — market is OPEN but outside Kill Zone window. Wait for next KZ.'}")
    if phase_info.get("action"):
        lines.append(f"  Action: {phase_info['action']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Fibonacci OTE (62-79%)
# ═══════════════════════════════════════════════════════════════════════════════

def get_fib_ote(df: pd.DataFrame, timeframe: str) -> str:
    """Fibonacci OTE zone — 62%-79% retracement of recent swing."""
    df = _to_smc_format(df)
    if df.empty:
        return f"\n## Fibonacci OTE [{timeframe}]\n  No data."

    cfg = ICT_INDICATORS.get("fib_ote", {})
    ote_low = cfg.get("ote_low", 0.62)
    ote_high = cfg.get("ote_high", 0.79)
    levels = cfg.get("levels", [0.236, 0.382, 0.50, 0.618, 0.705, 0.79])
    lookback = 20

    recent = df.tail(lookback)
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())
    current_price = float(df.iloc[-1]["close"])
    fib_range = swing_high - swing_low

    lines = [f"\n## Fibonacci OTE [{timeframe}]"]
    if fib_range <= 0:
        lines.append("  No swing range to calculate Fibonacci.")
        return "\n".join(lines)

    midpoint = swing_low + fib_range * 0.5
    zone = "premium" if current_price > midpoint else "discount"
    ote_top = swing_high - fib_range * ote_low
    ote_bottom = swing_high - fib_range * ote_high
    in_ote = ote_bottom <= current_price <= ote_top

    lines.append(f"  Swing High: {_fmt(swing_high)}")
    lines.append(f"  Swing Low:  {_fmt(swing_low)}")
    lines.append(f"  Current:    {_fmt(current_price)}")
    lines.append(f"  50% Level:  {_fmt(midpoint)}")
    lines.append(f"  Zone: {zone.upper()}")
    lines.append(f"  OTE Zone:   {_fmt(ote_bottom)} – {_fmt(ote_top)}")
    lines.append(f"  In OTE:     {'YES' if in_ote else 'NO'}")

    lines.append("  Fib Levels:")
    for lvl in levels:
        price = swing_high - fib_range * lvl
        lines.append(f"    {lvl:.1%}: {_fmt(price)}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Math Indicators (stockstats)
# ═══════════════════════════════════════════════════════════════════════════════

def get_math_indicators(df: pd.DataFrame, timeframe: str) -> str:
    """EMA / ATR / ADX / RSI / Supertrend via stockstats.wrap()."""
    df = _to_smc_format(df)
    if df.empty:
        return f"\n## Math Indicators [{timeframe}]\n  No data."

    tf_config = TIMEFRAMES.get(timeframe, {})
    indicator_list = tf_config.get("indicators", [])

    # Collect stockstats keys configured for this timeframe
    ss_keys = []
    for ind_name in indicator_list:
        ind_cfg = ICT_INDICATORS.get(ind_name, {})
        if ind_cfg.get("library") == "stockstats":
            ss_keys.append((ind_name, ind_cfg["key"], ind_cfg.get("description", "")))

    lines = [f"\n## Math Indicators [{timeframe}]"]
    if not ss_keys:
        lines.append("  No math indicators configured for this timeframe.")
        return "\n".join(lines)

    try:
        ss = wrap(df.copy())
    except Exception as e:
        lines.append(f"  Error wrapping DataFrame: {e}")
        return "\n".join(lines)

    for name, key, desc in ss_keys:
        try:
            values = ss[key]
            last_valid = values.dropna().tail(1)
            if len(last_valid) > 0:
                current = float(last_valid.iloc[-1])
                lines.append(f"  {name} ({key}): {_fmt(current, 4)} — {desc}")
            else:
                lines.append(f"  {name} ({key}): N/A — {desc}")
        except Exception as e:
            lines.append(f"  {name} ({key}): Error — {e}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Contract Sizing
# ═══════════════════════════════════════════════════════════════════════════════

def get_contract_calc(stop_points: float) -> str:
    """Contract sizing for NQ and MNQ based on stop distance and max risk."""
    max_loss = RISK["max_loss_per_trade"]
    nq_contracts = _calc_contracts(stop_points, "NQ")
    mnq_contracts = _calc_contracts(stop_points, "MNQ")
    nq_pv = _get_instrument("NQ")["point_value"]
    mnq_pv = _get_instrument("MNQ")["point_value"]
    nq_risk = nq_contracts * stop_points * nq_pv
    mnq_risk = mnq_contracts * stop_points * mnq_pv

    return (
        f"\n## Contract Calculation\n"
        f"  Stop Distance: {stop_points:.1f} points\n"
        f"  Max Loss: ${max_loss}\n"
        f"  NQ:  {nq_contracts} contracts "
        f"(${nq_risk:.0f} risk = {nq_contracts} x {stop_points:.1f} x ${nq_pv})\n"
        f"  MNQ: {mnq_contracts} contracts "
        f"(${mnq_risk:.0f} risk = {mnq_contracts} x {stop_points:.1f} x ${mnq_pv})"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 12. NDOG — New Day Opening Gap
# ═══════════════════════════════════════════════════════════════════════════════

def calc_ndog(df: pd.DataFrame, trade_date: str) -> dict:
    """
    NDOG = New Day Opening Gap.
    Gap between prior day 5:00 PM EST close and 6:00 PM EST open.
    The 50% level (consequent encroachment) is the strongest reaction zone.

    Returns dict with:
    - close_5pm: price at 5PM close
    - open_6pm: price at 6PM open
    - gap_high: max of the two
    - gap_low: min of the two
    - ce_50: 50% consequent encroachment level (the KEY level)
    - gap_size_points: absolute gap size
    - direction: "gap_up" or "gap_down"
    """
    df = _to_smc_format(df)
    if df.empty:
        return {"status": "no_data"}

    # Require intraday data — daily bars cannot resolve 5PM/6PM
    if len(df) < 2:
        return {"status": "requires_intraday_data"}

    avg_gap = (df.index[-1] - df.index[-2]).total_seconds() if len(df) >= 2 else 0
    if avg_gap >= 86400:  # bars are >= 1 day apart
        return {"status": "requires_intraday_data"}

    try:
        target_date = pd.Timestamp(trade_date).date()

        if df.index.tz is None:
            idx_est = df.index.tz_localize("UTC").tz_convert(EST)
        else:
            idx_est = df.index.tz_convert(EST)

        df_est = df.copy()
        df_est.index = idx_est

        # 5PM close: look on the prior calendar day (or same day for overnight)
        close_5pm_target = EST.localize(
            datetime.combine(target_date - timedelta(days=1), time(17, 0))
        )
        # Also try same-day 5PM for cases where trade_date IS the prior session end
        close_5pm_same = EST.localize(
            datetime.combine(target_date, time(17, 0))
        )

        # 6PM open on trade_date (or prior day if session starts evening before)
        open_6pm_target = EST.localize(
            datetime.combine(target_date - timedelta(days=1), time(18, 0))
        )
        open_6pm_same = EST.localize(
            datetime.combine(target_date, time(18, 0))
        )

        # Find candle closest to 5PM
        best_5pm = None
        best_5pm_dist = timedelta(hours=999)
        for candidate in [close_5pm_target, close_5pm_same]:
            diffs = abs(df_est.index - candidate)
            min_idx = diffs.argmin()
            dist = diffs[min_idx]
            if dist < best_5pm_dist and dist < timedelta(minutes=30):
                best_5pm_dist = dist
                best_5pm = min_idx

        # Find candle closest to 6PM (must be AFTER the 5PM candle)
        best_6pm = None
        best_6pm_dist = timedelta(hours=999)
        for candidate in [open_6pm_target, open_6pm_same]:
            diffs = abs(df_est.index - candidate)
            min_idx = diffs.argmin()
            dist = diffs[min_idx]
            if dist < best_6pm_dist and dist < timedelta(minutes=30):
                best_6pm_dist = dist
                best_6pm = min_idx

        if best_5pm is None or best_6pm is None:
            return {"status": "requires_intraday_data"}

        close_5pm = float(df_est.iloc[best_5pm]["close"])
        open_6pm = float(df_est.iloc[best_6pm]["open"])

        gap_high = max(close_5pm, open_6pm)
        gap_low = min(close_5pm, open_6pm)
        ce_50 = (close_5pm + open_6pm) / 2.0
        gap_size = abs(open_6pm - close_5pm)
        direction = "gap_up" if open_6pm > close_5pm else "gap_down"

        return {
            "close_5pm": close_5pm,
            "open_6pm": open_6pm,
            "gap_high": gap_high,
            "gap_low": gap_low,
            "ce_50": ce_50,
            "gap_size_points": gap_size,
            "direction": direction,
        }

    except Exception as e:
        logger.warning("calc_ndog error: %s", e)
        return {"status": "requires_intraday_data"}


# ═══════════════════════════════════════════════════════════════════════════════
# 13. NWOG — New Week Opening Gap
# ═══════════════════════════════════════════════════════════════════════════════

def calc_nwog(df: pd.DataFrame, trade_date: str) -> dict:
    """
    NWOG = New Week Opening Gap.
    Gap from Friday 5:00 PM EST close to Sunday 6:00 PM EST open.
    The 50% CE level is the weekly bias reference.
    Only meaningful on Mondays or when the gap hasn't been filled yet.

    Returns dict with:
    - friday_close: price at Friday 5PM
    - sunday_open: price at Sunday 6PM
    - gap_high: max of the two
    - gap_low: min of the two
    - ce_50: 50% consequent encroachment level
    - gap_size_points: absolute gap size
    - direction: "gap_up" or "gap_down"
    - filled: True if current price has crossed the CE level
    """
    df = _to_smc_format(df)
    if df.empty:
        return {"status": "insufficient_data"}

    try:
        target_date = pd.Timestamp(trade_date).date()

        if df.index.tz is None:
            idx_est = df.index.tz_localize("UTC").tz_convert(EST)
        else:
            idx_est = df.index.tz_convert(EST)

        df_est = df.copy()
        df_est.index = idx_est

        # Walk backward from trade_date to find most recent Friday
        d = target_date
        while d.weekday() != 4:  # 4 = Friday
            d -= timedelta(days=1)
        friday_date = d

        # Sunday is 2 days after Friday
        sunday_date = friday_date + timedelta(days=2)

        # Friday 5PM EST
        friday_5pm = EST.localize(datetime.combine(friday_date, time(17, 0)))
        # Sunday 6PM EST
        sunday_6pm = EST.localize(datetime.combine(sunday_date, time(18, 0)))

        # Find candle closest to Friday 5PM (within 30 min)
        diffs_fri = abs(df_est.index - friday_5pm)
        min_fri_idx = diffs_fri.argmin()
        if diffs_fri[min_fri_idx] > timedelta(minutes=30):
            # Fallback: last candle on Friday
            friday_mask = df_est.index.map(lambda t: t.date()) == friday_date
            friday_bars = df_est.loc[friday_mask]
            if friday_bars.empty:
                return {"status": "insufficient_data"}
            friday_close = float(friday_bars.iloc[-1]["close"])
        else:
            friday_close = float(df_est.iloc[min_fri_idx]["close"])

        # Find candle closest to Sunday 6PM (within 30 min)
        diffs_sun = abs(df_est.index - sunday_6pm)
        min_sun_idx = diffs_sun.argmin()
        if diffs_sun[min_sun_idx] > timedelta(minutes=30):
            # Fallback: first candle on Sunday
            sunday_mask = df_est.index.map(lambda t: t.date()) == sunday_date
            sunday_bars = df_est.loc[sunday_mask]
            if sunday_bars.empty:
                return {"status": "insufficient_data"}
            sunday_open = float(sunday_bars.iloc[0]["open"])
        else:
            sunday_open = float(df_est.iloc[min_sun_idx]["open"])

        gap_high = max(friday_close, sunday_open)
        gap_low = min(friday_close, sunday_open)
        ce_50 = (friday_close + sunday_open) / 2.0
        gap_size = abs(sunday_open - friday_close)
        direction = "gap_up" if sunday_open > friday_close else "gap_down"

        # Check if current price has filled past the CE level
        current_price = float(df_est.iloc[-1]["close"])
        if direction == "gap_up":
            filled = current_price <= ce_50
        else:
            filled = current_price >= ce_50

        return {
            "friday_close": friday_close,
            "sunday_open": sunday_open,
            "gap_high": gap_high,
            "gap_low": gap_low,
            "ce_50": ce_50,
            "gap_size_points": gap_size,
            "direction": direction,
            "filled": filled,
        }

    except Exception as e:
        logger.warning("calc_nwog error: %s", e)
        return {"status": "insufficient_data"}


# ═══════════════════════════════════════════════════════════════════════════════
# 14. SFP — Swing Failure Pattern Detection
# ═══════════════════════════════════════════════════════════════════════════════

def calc_sfp_detection(df: pd.DataFrame) -> dict:
    """
    SFP = Swing Failure Pattern.
    JadeCap's primary strategy engine.

    Detection logic:
    1. Find swing points: swing low = candle where Low is lower than
       both the previous candle's Low AND the next candle's Low (3-candle pattern).
       Swing high = candle where High is higher than both neighbors.
    2. Check if any swing point has been BREACHED (price went beyond it)
       but the candle CLOSED BACK INSIDE the range.
    3. A bearish SFP: price sweeps above a swing high but closes below it.
       A bullish SFP: price sweeps below a swing low but closes above it.

    Returns dict with:
    - swing_highs: list of {index, price, timestamp}
    - swing_lows: list of {index, price, timestamp}
    - bearish_sfps: list of {swept_level, sweep_price, close_price, timestamp, points_beyond}
    - bullish_sfps: list of {swept_level, sweep_price, close_price, timestamp, points_beyond}
    - latest_sfp: the most recent SFP or None
    - status: "sfp_confirmed" / "no_sfp" / "watching"
    """
    df = _to_smc_format(df)
    if df.empty or len(df) < 5:
        return {
            "swing_highs": [],
            "swing_lows": [],
            "bearish_sfps": [],
            "bullish_sfps": [],
            "latest_sfp": None,
            "status": "no_sfp",
        }

    swing_lookback = min(20, len(df) - 2)
    sfp_check_window = 10

    # --- Detect 3-candle swing highs and swing lows ---
    swing_highs = []
    swing_lows = []

    start_idx = max(1, len(df) - swing_lookback - 1)
    for i in range(start_idx, len(df) - 1):
        h_prev = float(df.iloc[i - 1]["high"])
        h_curr = float(df.iloc[i]["high"])
        h_next = float(df.iloc[i + 1]["high"])
        if h_curr > h_prev and h_curr > h_next:
            swing_highs.append({
                "index": i,
                "price": h_curr,
                "timestamp": str(df.index[i]),
            })

        l_prev = float(df.iloc[i - 1]["low"])
        l_curr = float(df.iloc[i]["low"])
        l_next = float(df.iloc[i + 1]["low"])
        if l_curr < l_prev and l_curr < l_next:
            swing_lows.append({
                "index": i,
                "price": l_curr,
                "timestamp": str(df.index[i]),
            })

    # --- Detect SFPs ---
    bearish_sfps = []
    bullish_sfps = []

    for sh in swing_highs:
        sh_idx = sh["index"]
        sh_price = sh["price"]
        # Check subsequent candles (up to sfp_check_window) for a sweep + failure
        end_check = min(sh_idx + sfp_check_window + 1, len(df))
        for j in range(sh_idx + 1, end_check):
            candle_high = float(df.iloc[j]["high"])
            candle_close = float(df.iloc[j]["close"])
            # Bearish SFP: high sweeps above swing high but close stays below
            if candle_high > sh_price and candle_close < sh_price:
                bearish_sfps.append({
                    "swept_level": sh_price,
                    "sweep_price": candle_high,
                    "close_price": candle_close,
                    "timestamp": str(df.index[j]),
                    "points_beyond": candle_high - sh_price,
                })
                break  # only record first SFP per swing point

    for sl in swing_lows:
        sl_idx = sl["index"]
        sl_price = sl["price"]
        end_check = min(sl_idx + sfp_check_window + 1, len(df))
        for j in range(sl_idx + 1, end_check):
            candle_low = float(df.iloc[j]["low"])
            candle_close = float(df.iloc[j]["close"])
            # Bullish SFP: low sweeps below swing low but close stays above
            if candle_low < sl_price and candle_close > sl_price:
                bullish_sfps.append({
                    "swept_level": sl_price,
                    "sweep_price": candle_low,
                    "close_price": candle_close,
                    "timestamp": str(df.index[j]),
                    "points_beyond": sl_price - candle_low,
                })
                break

    # Determine latest SFP
    all_sfps = []
    for s in bearish_sfps:
        all_sfps.append({"type": "bearish", **s})
    for s in bullish_sfps:
        all_sfps.append({"type": "bullish", **s})

    # Sort by timestamp descending
    all_sfps.sort(key=lambda x: x["timestamp"], reverse=True)
    latest_sfp = all_sfps[0] if all_sfps else None

    if latest_sfp:
        status = "sfp_confirmed"
    elif swing_highs or swing_lows:
        status = "watching"
    else:
        status = "no_sfp"

    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "bearish_sfps": bearish_sfps,
        "bullish_sfps": bullish_sfps,
        "latest_sfp": latest_sfp,
        "status": status,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 15a. Displacement Candle
# ═══════════════════════════════════════════════════════════════════════════════

def calc_displacement_candle(df, min_body_pct=0.6):
    """Detect strong displacement candles — body is 60%+ of total range.
    These confirm institutional intent after a liquidity sweep."""
    results = {"bullish": [], "bearish": [], "latest": None}
    if df is None or df.empty or len(df) < 3:
        return results
    for i in range(2, len(df)):
        row = df.iloc[i]
        o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
        total_range = h - l
        if total_range <= 0:
            continue
        body = abs(c - o)
        body_pct = body / total_range
        if body_pct >= min_body_pct:
            entry = {
                "index": i,
                "timestamp": str(df.index[i]) if hasattr(df.index[i], '__str__') else str(i),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "body_pct": round(body_pct * 100, 1),
                "range_points": round(total_range, 2),
            }
            if c > o:
                results["bullish"].append(entry)
            else:
                results["bearish"].append(entry)
    if results["bullish"]:
        results["latest"] = {"direction": "bullish", **results["bullish"][-1]}
    elif results["bearish"]:
        results["latest"] = {"direction": "bearish", **results["bearish"][-1]}
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 15b. Liquidity Sweep
# ═══════════════════════════════════════════════════════════════════════════════

def calc_liquidity_sweep(df):
    """Detect if any recent swing high/low was breached (swept) by a candle
    that then closed back inside — confirming a liquidity raid."""
    results = {"bsl_sweeps": [], "ssl_sweeps": [], "latest": None}
    if df is None or df.empty or len(df) < 10:
        return results
    # Find swing highs and lows (3-candle pattern)
    for i in range(1, len(df) - 1):
        prev_h = float(df.iloc[i-1]["High"])
        curr_h = float(df.iloc[i]["High"])
        next_h = float(df.iloc[i+1]["High"])
        prev_l = float(df.iloc[i-1]["Low"])
        curr_l = float(df.iloc[i]["Low"])
        next_l = float(df.iloc[i+1]["Low"])
        # Swing high
        if curr_h > prev_h and curr_h > next_h:
            # Check if any subsequent candle swept this high
            for j in range(i+2, min(i+12, len(df))):
                bar = df.iloc[j]
                if float(bar["High"]) > curr_h and float(bar["Close"]) < curr_h:
                    results["bsl_sweeps"].append({
                        "swing_price": round(curr_h, 2),
                        "sweep_high": round(float(bar["High"]), 2),
                        "close": round(float(bar["Close"]), 2),
                        "points_beyond": round(float(bar["High"]) - curr_h, 2),
                        "timestamp": str(df.index[j]),
                    })
                    break
        # Swing low
        if curr_l < prev_l and curr_l < next_l:
            for j in range(i+2, min(i+12, len(df))):
                bar = df.iloc[j]
                if float(bar["Low"]) < curr_l and float(bar["Close"]) > curr_l:
                    results["ssl_sweeps"].append({
                        "swing_price": round(curr_l, 2),
                        "sweep_low": round(float(bar["Low"]), 2),
                        "close": round(float(bar["Close"]), 2),
                        "points_beyond": round(curr_l - float(bar["Low"]), 2),
                        "timestamp": str(df.index[j]),
                    })
                    break
    if results["bsl_sweeps"]:
        results["latest"] = {"type": "bsl", **results["bsl_sweeps"][-1]}
    elif results["ssl_sweeps"]:
        results["latest"] = {"type": "ssl", **results["ssl_sweeps"][-1]}
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 15c. Breaker Block
# ═══════════════════════════════════════════════════════════════════════════════

def calc_breaker_block(df):
    """Detect breaker blocks — failed order blocks that got violated.
    When price breaks through an OB, it flips to opposite S/R."""
    results = {"bullish_breakers": [], "bearish_breakers": [], "latest": None}
    if df is None or df.empty or len(df) < 10:
        return results
    # Find potential OBs then check if they get violated
    for i in range(2, len(df) - 3):
        # Bearish OB candidate: bullish candle before bearish displacement
        o1, c1 = float(df.iloc[i]["Open"]), float(df.iloc[i]["Close"])
        o2, c2 = float(df.iloc[i+1]["Open"]), float(df.iloc[i+1]["Close"])
        # Bullish candle followed by bearish displacement
        if c1 > o1 and c2 < o2 and (o2 - c2) > (c1 - o1) * 1.5:
            ob_high = float(df.iloc[i]["High"])
            ob_low = float(df.iloc[i]["Low"])
            # Check if OB gets violated later (price breaks below OB low)
            for j in range(i+2, min(i+15, len(df))):
                if float(df.iloc[j]["Close"]) < ob_low:
                    # OB violated — now it's a bearish breaker (resistance)
                    results["bearish_breakers"].append({
                        "ob_high": round(ob_high, 2),
                        "ob_low": round(ob_low, 2),
                        "violated_at": str(df.index[j]),
                        "type": "bearish_breaker",
                    })
                    break
        # Bearish candle followed by bullish displacement
        if c1 < o1 and c2 > o2 and (c2 - o2) > (o1 - c1) * 1.5:
            ob_high = float(df.iloc[i]["High"])
            ob_low = float(df.iloc[i]["Low"])
            for j in range(i+2, min(i+15, len(df))):
                if float(df.iloc[j]["Close"]) > ob_high:
                    results["bullish_breakers"].append({
                        "ob_high": round(ob_high, 2),
                        "ob_low": round(ob_low, 2),
                        "violated_at": str(df.index[j]),
                        "type": "bullish_breaker",
                    })
                    break
    if results["bullish_breakers"]:
        results["latest"] = results["bullish_breakers"][-1]
    elif results["bearish_breakers"]:
        results["latest"] = results["bearish_breakers"][-1]
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 15d. AMD Phase
# ═══════════════════════════════════════════════════════════════════════════════

def calc_amd_phase():
    """Determine current AMD phase based on EST time.

    NQ/ES futures trade Sun 6PM - Fri 5PM EST.
    Closed: Friday 5PM through Sunday 6PM (weekend).
    Closed: Daily 5-6PM EST (1-hour maintenance, Mon-Thu only).

    Accumulation = Asia (6PM-2AM), Manipulation = London (2-8AM),
    Distribution = NY (8AM-5PM).
    """
    from datetime import datetime, timezone, timedelta
    est = timezone(timedelta(hours=-5))
    now = datetime.now(est)
    weekday = now.weekday()  # 0=Mon, 5=Sat, 6=Sun
    hour, minute = now.hour, now.minute
    t = hour * 60 + minute

    # Weekend check: closed all Saturday, closed Sunday until 6PM
    if weekday == 5:  # Saturday — fully closed
        return {"phase": "closed", "session": "weekend", "action": "Futures closed (weekend). Opens Sunday 6PM EST."}
    if weekday == 6 and t < 18*60:  # Sunday before 6PM — still closed
        return {"phase": "closed", "session": "weekend", "action": "Futures closed (weekend). Opens today at 6PM EST."}
    # Friday after 5PM — closed for weekend
    if weekday == 4 and t >= 17*60:
        return {"phase": "closed", "session": "weekend", "action": "Futures closed (weekend). Opens Sunday 6PM EST."}

    # Daily maintenance: 5-6PM Mon-Thu
    if 17*60 <= t < 18*60:
        return {"phase": "closed", "session": "maintenance", "action": "Futures closed (daily maintenance 5-6PM EST). Review and prepare."}
    elif t >= 18*60 or t < 0:  # 6PM-midnight
        return {"phase": "accumulation", "session": "asia", "action": "DO NOT TRADE. Mark Asia range H/L."}
    elif 0 <= t < 2*60:  # midnight-2AM
        return {"phase": "accumulation", "session": "asia_late", "action": "Mark overnight levels. Range building."}
    elif 2*60 <= t < 5*60:  # 2-5AM
        return {"phase": "manipulation", "session": "london", "action": "Note London sweep direction. Confirms NY bias."}
    elif 5*60 <= t < 8*60:  # 5-8AM
        return {"phase": "manipulation", "session": "london_late", "action": "London continuation. Map any FVGs left for NY draw targets."}
    elif 8*60 <= t < 17*60:  # 8AM-5PM
        return {"phase": "distribution", "session": "ny", "action": "EXECUTE. JadeCap primary session. Use Kill Zones for entry."}
    return {"phase": "unknown", "session": "unknown", "action": "Check time."}


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Timeframe Indicator Dispatcher
# ═══════════════════════════════════════════════════════════════════════════════

def compute_timeframe_indicators(
    df: pd.DataFrame,
    indicator_list: list,
    timeframe: str,
    trade_date: str = "",
) -> dict:
    """Dispatch indicator calculations by name.

    Args:
        df: OHLCV DataFrame for the given timeframe.
        indicator_list: list of indicator name strings to compute.
        timeframe: e.g. "1H", "15m".
        trade_date: YYYY-MM-DD string (needed by some indicators).

    Returns:
        dict mapping indicator name -> result (str or dict).
    """
    results = {}
    for ind_name in indicator_list:
        if ind_name == "fvg":
            results[ind_name] = get_fvg(df, timeframe)
        elif ind_name == "order_blocks":
            results[ind_name] = get_order_blocks(df, timeframe)
        elif ind_name == "mss_choch":
            results[ind_name] = get_market_structure(df, timeframe)
        elif ind_name == "equal_highs_lows":
            results[ind_name] = get_equal_highs_lows(df, timeframe)
        elif ind_name == "fib_ote":
            results[ind_name] = get_fib_ote(df, timeframe)
        elif ind_name == "session_levels":
            results[ind_name] = get_session_levels(df)
        elif ind_name == "prev_day_levels":
            results[ind_name] = get_prev_day_levels(df)
        elif ind_name == "midnight_open":
            results[ind_name] = get_midnight_open(df, trade_date)
        elif ind_name == "math":
            results[ind_name] = get_math_indicators(df, timeframe)
        elif ind_name == "ndog":
            results[ind_name] = calc_ndog(df, trade_date)
        elif ind_name == "nwog":
            results[ind_name] = calc_nwog(df, trade_date)
        elif ind_name == "sfp_detection":
            results[ind_name] = calc_sfp_detection(df)
        elif ind_name == "displacement_candle":
            results[ind_name] = calc_displacement_candle(df)
        elif ind_name == "liquidity_sweep":
            results[ind_name] = calc_liquidity_sweep(df)
        elif ind_name == "breaker_block":
            results[ind_name] = calc_breaker_block(df)
        elif ind_name == "amd_phase":
            results[ind_name] = calc_amd_phase()
        else:
            logger.debug("Unknown indicator '%s' — skipping.", ind_name)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Master Report
# ═══════════════════════════════════════════════════════════════════════════════

def get_full_ict_report(dataframes: dict, trade_date: str) -> str:
    """Build the complete multi-timeframe ICT report from pre-fetched DataFrames.

    Args:
        dataframes: dict of timeframe str -> pd.DataFrame (e.g. {"1m": df, "15m": df, ...})
        trade_date: YYYY-MM-DD string for the trading day

    Returns:
        Single formatted string containing every ICT indicator section.
    """
    sections = [
        f"\n{'='*60}",
        f"  FULL ICT REPORT | {trade_date}",
        f"{'='*60}",
    ]

    # Kill Zone + AMD — always first
    sections.append(get_killzone_status())

    # Midnight Open from 1-minute data
    if "1m" in dataframes:
        sections.append(get_midnight_open(dataframes["1m"], trade_date))

    # Previous Day Levels from 1H or 1D
    for tf in ("1H", "1D"):
        if tf in dataframes:
            sections.append(get_prev_day_levels(dataframes[tf]))
            break

    # Session Levels from 15m
    if "15m" in dataframes:
        sections.append(get_session_levels(dataframes["15m"]))

    # Per-timeframe analysis — HTF to LTF
    for tf in ("1D", "4H", "1H", "30m", "15m", "5m"):
        if tf not in dataframes:
            continue
        df = dataframes[tf]
        tf_cfg = TIMEFRAMES.get(tf, {})
        indicators = tf_cfg.get("indicators", [])

        sections.append(f"\n{'─'*40}")
        sections.append(f"  TIMEFRAME: {tf} — {tf_cfg.get('purpose', '')}")
        sections.append(f"{'─'*40}")

        if "fvg" in indicators:
            sections.append(get_fvg(df, tf))
        if "order_blocks" in indicators:
            sections.append(get_order_blocks(df, tf))
        if "mss_choch" in indicators:
            sections.append(get_market_structure(df, tf))
        if "equal_highs_lows" in indicators:
            sections.append(get_equal_highs_lows(df, tf))
        if "fib_ote" in indicators:
            sections.append(get_fib_ote(df, tf))

        # Math indicators for this timeframe
        sections.append(get_math_indicators(df, tf))

    # Hard Rules reminder
    sections.append(f"\n{'='*60}")
    sections.append("  HARD RULES — NON-NEGOTIABLE")
    sections.append(f"{'='*60}")
    for i, rule in enumerate(HARD_RULES, 1):
        sections.append(f"  {i}. {rule}")

    return "\n".join(sections)
