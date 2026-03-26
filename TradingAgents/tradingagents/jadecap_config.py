"""
jadecap_config.py
===================================================================
JadeCap Strategy Configuration — Full ICT Methodology v2
Based on: Kyle Ng JadeCap Playbook
Instruments: NQ / MNQ Futures
Firms: Apex Trader Funding / My Funded Futures / Lucid Trading

This module contains ALL configuration for the JadeCap ICT trading
strategy, organized into 27 sections:

  1. INSTRUMENTS          — NQ and MNQ futures specs
  2. PROP_FIRMS           — Risk rules per prop firm
  3. LIVE_PRICE           — Databento real-time feed config
  4. SESSIONS             — Asia / London / NY with NDOG/NWOG notes
  5. KILL_ZONES           — 4 active windows with Silver Bullet rules
  6. SILVER_BULLET        — Highest probability execution windows
  7. MIDDAY_AVOIDANCE     — 11:30-1:00 chop zone
  8. TIMEFRAMES           — Bar lookbacks and indicator assignments
  9. ICT_INDICATORS       — 23 indicators with full playbook notes
 10. AMD                  — Power of Three framework
 11. DAILY_SWEEP          — #1 priority SFP strategy
 12. DRAW_ON_LIQUIDITY    — 5-question pre-trade framework
 13. NDOG                 — New Day Opening Gap definition
 14. NWOG                 — New Week Opening Gap definition
 15. IPDA                 — Interbank Price Delivery Algorithm
 16. ENTRY_MODELS         — 6 entry models (0-5) with full rules
 17. RISK                 — Risk management parameters
 18. A_PLUS_SCORING       — Weighted 1-10 setup quality scoring
 19. HARD_RULES           — 21 non-negotiable rules for all agents
 20. BULL_SETUP           — Bullish long setup criteria
 21. BEAR_SETUP           — Bearish short setup criteria
 22. CHECKLIST            — 14-item pre-trade checklist
 23. HOLIDAY_RULES        — Low-volume day avoidance
 24. TRADE_OUTPUT_FORMAT  — Required output from Trader agent
 25. calculate_contracts  — Contract sizing function
 26. apply_settings       — Runtime override from UI settings
 27. JADECAP_CONFIG       — Master dict aggregating all sections

Every section exported at module level. Agents import what they need.
===================================================================
"""


# =====================================================================
# 1. INSTRUMENTS
# =====================================================================
# NQ (E-mini) and MNQ (Micro) Nasdaq 100 futures specifications.
# Point value determines dollar risk per point per contract.
# tick_size and tick_value define the minimum price increment.
# databento_sym is the continuous front-month symbol for the feed.
# =====================================================================

INSTRUMENTS = {
    "NQ": {
        "ticker":        "NQ=F",
        "databento_sym": "NQ.c.0",
        "point_value":   20,
        "tick_size":     0.25,
        "tick_value":    5.00,
        "description":   "E-mini Nasdaq 100 Futures",
    },
    "MNQ": {
        "ticker":        "MNQ=F",
        "databento_sym": "MNQ.c.0",
        "point_value":   2,
        "tick_size":     0.25,
        "tick_value":    0.50,
        "description":   "Micro E-mini Nasdaq 100 Futures",
        "note":          "Same chart as NQ — contracts adjust automatically by stop size",
    },
    "ES": {
        "ticker":        "ES=F",
        "databento_sym": "ES.c.0",
        "point_value":   50,
        "tick_size":     0.25,
        "tick_value":    12.50,
        "description":   "E-mini S&P 500 Futures",
    },
    "MES": {
        "ticker":        "MES=F",
        "databento_sym": "MES.c.0",
        "point_value":   5,
        "tick_size":     0.25,
        "tick_value":    1.25,
        "description":   "Micro E-mini S&P 500 Futures",
    },
    "YM": {
        "ticker":        "YM=F",
        "databento_sym": "YM.c.0",
        "point_value":   5,
        "tick_size":     1.0,
        "tick_value":    5.00,
        "description":   "E-mini Dow Jones Futures",
    },
    "RTY": {
        "ticker":        "RTY=F",
        "databento_sym": "RTY.c.0",
        "point_value":   50,
        "tick_size":     0.10,
        "tick_value":    5.00,
        "description":   "E-mini Russell 2000 Futures",
    },
    "CL": {
        "ticker":        "CL=F",
        "databento_sym": "CL.c.0",
        "point_value":   1000,
        "tick_size":     0.01,
        "tick_value":    10.00,
        "description":   "Crude Oil Futures",
    },
    "GC": {
        "ticker":        "GC=F",
        "databento_sym": "GC.c.0",
        "point_value":   100,
        "tick_size":     0.10,
        "tick_value":    10.00,
        "description":   "Gold Futures",
    },
}


# =====================================================================
# 2. PROP FIRMS — risk rules per firm
# =====================================================================
# Each prop firm has different contract limits, drawdown rules, and
# profit targets. base_risk_pct is the standard per-trade risk (0.25%
# of account). a_plus_risk_pct is used only when the A+ scoring system
# gives a perfect 8-10/10 score. trailing_drawdown is the dollar amount
# of the trailing drawdown threshold for the evaluation account.
# =====================================================================

PROP_FIRMS = {
    "apex": {
        "name":              "Apex Trader Funding",
        "base_risk_pct":     0.25,
        "a_plus_risk_pct":   0.50,
        "max_contracts_nq":  20,
        "max_contracts_mnq": 200,
        "trailing_drawdown": 2500,
        "profit_target":     3000,
        "note": "World record $2.55M single payout by JadeCap in 56 sessions",
    },
    "mff": {
        "name":              "My Funded Futures",
        "base_risk_pct":     0.25,
        "a_plus_risk_pct":   0.50,
        "max_contracts_nq":  15,
        "max_contracts_mnq": 150,
        "trailing_drawdown": 2000,
        "profit_target":     2500,
    },
    "lucid": {
        "name":              "Lucid Trading",
        "base_risk_pct":     0.25,
        "a_plus_risk_pct":   0.50,
        "max_contracts_nq":  10,
        "max_contracts_mnq": 100,
        "trailing_drawdown": 2000,
        "profit_target":     2000,
    },
}


# =====================================================================
# 3. LIVE PRICE — Databento real-time feed configuration
# =====================================================================
# Databento provides sub-millisecond CME futures data via GLBX.MDP3.
# update_every controls how often (in seconds) the price snapshot
# refreshes during live trading. symbols maps our instrument keys
# to Databento continuous contract symbols.
# =====================================================================

LIVE_PRICE = {
    "enabled":      True,
    "provider":     "databento",
    "mode":         "live",
    "dataset":      "GLBX.MDP3",
    "schema":       "trades",
    "update_every": 5,
    "symbols": {"NQ": "NQ.c.0", "MNQ": "MNQ.c.0"},
}


# =====================================================================
# 4. SESSIONS — EST times
# =====================================================================
# Three sessions define the ICT Power of Three (AMD) framework.
# Asia = Accumulation, London = Manipulation, NY = Distribution.
#
# Updates in v2:
#   - ny_am now includes pre_market_start at 08:00 for mapping
#     swing points before the NY open.
#   - NDOG (New Day Opening Gap) and NWOG (New Week Opening Gap)
#     marking notes added to ny_am so agents know to mark these
#     reference levels before any trading begins.
# =====================================================================

SESSIONS = {
    # NQ/ES futures trade 23 hours: Sun 6PM - Fri 5PM EST.
    # Only CLOSED 5:00 PM - 6:00 PM EST daily (1-hour maintenance).
    # Sessions below are ICT analysis windows, NOT market hours.
    "closed": {
        "name":      "Market Closed (Daily Maintenance)",
        "start":     "17:00",
        "end":       "18:00",
        "amd_phase": "closed",
        "note":      "Futures closed for 1-hour daily maintenance. No trading.",
    },
    "asia": {
        "name":      "Asia Session",
        "start":     "18:00",
        "end":       "00:00",
        "amd_phase": "accumulation",
        "note": (
            "Sets overnight range H/L. "
            "Liquidity builds on both sides. "
            "JadeCap does NOT trade this session. "
            "Asian range H/L used as NY liquidity raid reference."
        ),
    },
    "asia_late": {
        "name":      "Late Asia / Pre-London",
        "start":     "00:00",
        "end":       "02:00",
        "amd_phase": "accumulation",
        "note":      "Continuation of Asia accumulation. Range consolidation.",
    },
    "london": {
        "name":      "London Session",
        "start":     "02:00",
        "end":       "05:00",
        "amd_phase": "manipulation",
        "note": (
            "Often sets the manipulation — raids Asian range H or L. "
            "London sweep = confirms intraday bias direction for NY. "
            "Note London H/L — NY often revisits it. "
            "JadeCap uses London to confirm or deny daily bias."
        ),
    },
    "london_late": {
        "name":      "Late London / Pre-NY",
        "start":     "05:00",
        "end":       "08:00",
        "amd_phase": "manipulation",
        "note": (
            "London continuation. Consolidation before NY open. "
            "Mark any London FVGs left on chart as potential NY draw targets."
        ),
    },
    "ny": {
        "name":             "New York Session",
        "start":            "08:00",
        "end":              "17:00",
        "pre_market_start": "08:00",
        "amd_phase":        "distribution",
        "note": (
            "True directional move begins. Primary JadeCap trading session. "
            "At 8:00 AM EST, begin mapping 1H swing points for SFP detection. "
            "Futures remain open until 5:00 PM — no forced close at 4:00 PM. "
            "Hard rule: close day-trade positions by 4:00 PM (JadeCap rule, not market close)."
        ),
        "ndog_note": (
            "Mark NDOG (5PM-6PM gap) 50% level before session. "
            "The consequent encroachment of the NDOG is a high-probability "
            "reaction zone. Always mark it on the chart before 9:30."
        ),
        "nwog_note": (
            "On Mondays, mark NWOG (Friday 5PM - Sunday 6PM gap). "
            "The 50% CE of the NWOG provides the weekly directional bias "
            "reference. Mark it before the Monday session opens."
        ),
    },
}


# =====================================================================
# 5. KILL ZONES — EST (all 4 active)
# =====================================================================
# Kill Zones define the ONLY windows in which entries are allowed.
# Trading outside these windows violates Hard Rule #2.
#
# Silver Bullet kill zones now include silver_bullet_rules that
# codify the strict entry protocol for the Silver Bullet model:
#   - Only the FIRST FVG forming during the window qualifies.
#   - A liquidity level must be swept before entry is considered.
#   - Unfilled limit orders are canceled when the window closes.
#   - One trade per window — no exceptions.
# =====================================================================

KILL_ZONES = {
    "am": {
        "name":     "AM Kill Zone",
        "start":    "09:30",
        "end":      "11:30",
        "active":   True,
        "priority": 1,
        "note":     "Primary window — highest volume and institutional activity",
    },
    "silver_bullet_1": {
        "name":     "Silver Bullet 1",
        "start":    "10:00",
        "end":      "11:00",
        "active":   True,
        "priority": 1,
        "note":     "HIGHEST PROBABILITY — best FVG setup of the entire day",
        "silver_bullet_rules": {
            "first_fvg_only":                True,
            "sweep_required_before_entry":   True,
            "bearish_fvg_requires_high_sweep": True,
            "bullish_fvg_requires_low_sweep":  True,
            "entry_type":                    "limit_order_at_fvg_boundary",
            "cancel_unfilled_at_window_close": True,
            "one_trade_per_window":          True,
        },
    },
    "pm": {
        "name":     "PM Kill Zone",
        "start":    "13:00",
        "end":      "16:00",
        "active":   True,
        "priority": 2,
        "note":     "Secondary window — afternoon continuation or reversal",
    },
    "silver_bullet_2": {
        "name":     "Silver Bullet 2",
        "start":    "14:00",
        "end":      "15:00",
        "active":   True,
        "priority": 2,
        "note":     "Second highest probability FVG setup",
        "silver_bullet_rules": {
            "first_fvg_only":                True,
            "sweep_required_before_entry":   True,
            "bearish_fvg_requires_high_sweep": True,
            "bullish_fvg_requires_low_sweep":  True,
            "entry_type":                    "limit_order_at_fvg_boundary",
            "cancel_unfilled_at_window_close": True,
            "one_trade_per_window":          True,
        },
    },
}


# =====================================================================
# 6. SILVER BULLET — Highest probability execution windows
# =====================================================================
# The Silver Bullet is a specific ICT execution model that operates
# within defined Kill Zone windows. It targets the FIRST valid FVG
# forming after a liquidity sweep. The AM window (10:00-11:00) is
# the primary and highest-probability window. The PM window
# (14:00-15:00) is secondary.
#
# JadeCap recommends mastering the AM window before adding PM.
# The AM window provides the clearest directional bias because
# it aligns with the Distribution phase of the AMD framework.
# =====================================================================

SILVER_BULLET = {
    "description": "Highest probability execution windows within Kill Zones",
    "primary_window": {
        "start": "10:00",
        "end":   "11:00",
        "name":  "Silver Bullet AM",
    },
    "secondary_window": {
        "start": "14:00",
        "end":   "15:00",
        "name":  "Silver Bullet PM",
    },
    "rules": {
        "first_fvg_only": (
            "Only the FIRST valid FVG forming during window qualifies"
        ),
        "sweep_prerequisite": (
            "At least one liquidity level must be swept before entry "
            "(Asian H/L, London H/L, or 9AM NY reference)"
        ),
        "bearish_requires_high_sweep": (
            "Bearish FVG requires a prior HIGH to be swept"
        ),
        "bullish_requires_low_sweep": (
            "Bullish FVG requires a prior LOW to be swept"
        ),
        "entry": "Limit order at FVG boundary",
        "stop": "Behind Candle 1 of FVG",
        "target": "Minimum 2R",
        "cancel_rule": (
            "Unfilled limit orders CANCELED when window closes"
        ),
        "one_trade": "One trade per window — no exceptions",
    },
    "jadecap_note": (
        "Master the AM window first before adding PM. "
        "AM provides clearest directional bias."
    ),
}


# =====================================================================
# 7. MIDDAY AVOIDANCE — 11:30 AM to 1:00 PM EST
# =====================================================================
# The midday period is characterized by low institutional participation,
# choppy price action, and frequent stop hunts without follow-through.
# No new entries should be initiated during this window. If an existing
# trade stalls near midday without reaching its target, exit the
# position rather than waiting — the afternoon session may not
# continue the move.
# =====================================================================

MIDDAY_AVOIDANCE = {
    "enabled":     True,
    "start":       "11:30",
    "end":         "13:00",
    "description": "Chop zone — avoid new entries",
    "action": (
        "No new entries. If trade stalls near midday, "
        "exit even before target."
    ),
    "jadecap_quote": "Afternoon chop is the enemy.",
}


# =====================================================================
# 8. TIMEFRAMES — what to pull and why (400 bars each)
# =====================================================================
# Each timeframe has a specific purpose in the JadeCap workflow.
# lookback_bars is set to 400 for all timeframes to ensure sufficient
# history for indicator calculations (especially for 200 EMA on
# higher timeframes).
#
# Updates in v2:
#   - 15m: added "ndog" to indicators
#   - 1H: added "ndog", "nwog", "sfp_detection" to indicators
#   - 1D: added "nwog" to indicators
# =====================================================================

TIMEFRAMES = {
    "1m": {
        "lookback_bars": 400,
        "purpose":       "Midnight Open exact price — 12:00 AM EST reference",
        "indicators":    ["midnight_open", "killzone_timer"],
    },
    "5m": {
        "lookback_bars": 400,
        "purpose":       "LTF entry trigger — displacement candle confirmation",
        "indicators":    [
            "fvg", "order_blocks", "killzone_timer",
            "displacement_candle", "liquidity_sweep",
        ],
    },
    "15m": {
        "lookback_bars": 400,
        "purpose":       "PRIMARY ENTRY TIMEFRAME — all entry models run here",
        "indicators":    [
            "fvg", "order_blocks", "equal_highs_lows", "session_levels",
            "mss_choch", "atr", "rsi", "close_9_ema",
            "breaker_block", "displacement_candle", "liquidity_sweep",
            "ndog",
        ],
    },
    "30m": {
        "lookback_bars": 400,
        "purpose":       "Intermediate structure — confirms 15m setups",
        "indicators":    [
            "fvg", "order_blocks", "mss_choch",
            "close_9_ema", "close_50_ema",
        ],
    },
    "1H": {
        "lookback_bars": 400,
        "purpose":       "HTF structure, order flow bias, and SFP detection",
        "indicators":    [
            "fvg", "order_blocks", "mss_choch", "equal_highs_lows",
            "close_50_ema", "adx", "supertrend",
            "prev_day_hl", "fib_ote", "breaker_block",
            "ndog", "nwog", "sfp_detection",
        ],
    },
    "4H": {
        "lookback_bars": 400,
        "purpose":       "HTF bias confirmation — master direction",
        "indicators":    [
            "fvg", "order_blocks", "mss_choch", "adx",
            "close_200_ema", "supertrend", "fib_ote",
        ],
    },
    "1D": {
        "lookback_bars": 400,
        "purpose":       "Daily HTF bias — structure and key levels",
        "indicators":    [
            "close_200_ema", "mss_choch", "prev_day_hl",
            "fib_ote", "nwog",
        ],
    },
    "1W": {
        "lookback_bars": 400,
        "purpose":       "Master HTF bias — weekly structure, FVGs, and swing points",
        "indicators":    ["fvg", "mss_choch", "close_200_ema", "fib_ote"],
    },
}


# =====================================================================
# 9. ICT INDICATORS — 23 indicators with full playbook notes
# =====================================================================
# Complete indicator catalog used across all agent prompts.
# Each indicator specifies:
#   - library: source library ("smartmoneyconcepts", "stockstats", "manual")
#   - function: the Python function name that computes it
#   - timeframes: which bars it applies to
#   - description: what it measures
#   - jadecap_note: Kyle Ng's specific guidance on usage
#   - bull_signal / bear_signal: directional interpretation
#
# 3 new indicators in v2: ndog, nwog, sfp_detection (total 23)
# =====================================================================

ICT_INDICATORS = {

    # ── smartmoneyconcepts ────────────────────────────────────────────

    "fvg": {
        "library":          "smartmoneyconcepts",
        "function":         "get_fvg",
        "smc_call":         "smc.fvg()",
        "timeframes":       ["5m", "15m", "30m", "1H", "4H", "1W"],
        "join_consecutive": True,
        "description":      "Fair Value Gap — 3-candle imbalance",
        "jadecap_note": (
            "Most important tool in the system. "
            "FVGs at HTF POI = highest confluence. "
            "FVG inversion = order flow has shifted. "
            "Entry 1 in JadeCap playbook."
        ),
        "bull_signal": "Price retraces INTO bullish FVG — enter long",
        "bear_signal": "Price retraces INTO bearish FVG — enter short",
    },

    "order_blocks": {
        "library":          "smartmoneyconcepts",
        "function":         "get_order_blocks",
        "smc_call":         "smc.ob()",
        "timeframes":       ["5m", "15m", "30m", "1H", "4H"],
        "swing_length":     5,
        "description":      "Order Block — last opposing candle before displacement",
        "jadecap_note": (
            "Must form at valid S/R or after a liquidity run. "
            "High probability OBs form WITH an FVG attached. "
            "Enter on retracement back into the OB body. "
            "Entry 2 in JadeCap playbook."
        ),
        "bull_signal": "Price returns to bullish OB — enter long",
        "bear_signal": "Price returns to bearish OB — enter short",
    },

    "session_levels": {
        "library":      "smartmoneyconcepts",
        "function":     "get_session_levels",
        "smc_call":     "smc.sessions()",
        "timeframes":   ["15m"],
        "sessions":     ["asia", "london", "ny_am"],
        "description":  "Session High/Low — Asia, London, NY",
        "jadecap_note": (
            "Primary liquidity pools for the day. "
            "London often raids Asian range H or L. "
            "NY AM often revisits London H/L. "
            "Mark all 3 sessions before NY open."
        ),
    },

    "equal_highs_lows": {
        "library":      "smartmoneyconcepts",
        "function":     "get_equal_highs_lows",
        "smc_call":     "smc.liquidity()",
        "timeframes":   ["15m", "1H"],
        "swing_length": 5,
        "description":  "Equal Highs / Equal Lows — BSL and SSL",
        "jadecap_note": (
            "Double tops / double bottoms = retail stop accumulation. "
            "Equal Highs = Buy Side Liquidity (BSL) — target for shorts. "
            "Equal Lows = Sell Side Liquidity (SSL) — target for longs. "
            "Price WILL sweep these before true move."
        ),
        "bsl_note": "Equal Highs above = shorts target / longs must clear",
        "ssl_note": "Equal Lows below = longs target / shorts must clear",
    },

    "mss_choch": {
        "library":      "smartmoneyconcepts",
        "function":     "get_market_structure",
        "smc_call":     "smc.bos_choch()",
        "timeframes":   ["15m", "30m", "1H", "4H", "1D", "1W"],
        "swing_length": 5,
        "close_break":  True,
        "description":  "Market Structure Shift (MSS) and Change of Character (CHoCH)",
        "jadecap_note": (
            "MSS = institutional order flow has changed direction. "
            "CHoCH = early warning that direction is shifting. "
            "Must see MSS/CHoCH to confirm entry direction. "
            "BOS on 1H/4H = HTF order flow confirmed. "
            "Weekly BOS = master bias change — overrides everything."
        ),
        "bull_signal": "Bullish CHoCH/BOS on 15m after SSL sweep = long setup",
        "bear_signal": "Bearish CHoCH/BOS on 15m after BSL sweep = short setup",
    },

    "prev_day_hl": {
        "library":      "smartmoneyconcepts",
        "function":     "get_prev_day_levels",
        "smc_call":     "smc.previous_high_low()",
        "timeframes":   ["1H", "1D"],
        "description":  "Previous Day High / Low",
        "jadecap_note": (
            "PRIMARY draw targets for the trading day. "
            "If PDH already taken before Kill Zone — NO TRADE. "
            "If PDL already taken before Kill Zone — NO TRADE. "
            "NY session targets PDH or PDL every day."
        ),
        "bull_target": "PDH = buy side target for long trades",
        "bear_target": "PDL = sell side target for short trades",
    },

    # ── stockstats ────────────────────────────────────────────────────

    "close_200_ema": {
        "library":      "stockstats",
        "key":          "close_200_ema",
        "function":     "get_math_indicators",
        "timeframes":   ["4H", "1D", "1W"],
        "description":  "200 EMA — HTF bias master filter",
        "jadecap_note": (
            "Above 200 EMA = BULLISH bias only take longs. "
            "Below 200 EMA = BEARISH bias only take shorts. "
            "This is non-negotiable — never fight the 200 EMA. "
            "Weekly 200 EMA = ultimate trend direction."
        ),
        "bull_signal": "Price above 200 EMA — longs only",
        "bear_signal": "Price below 200 EMA — shorts only",
    },

    "close_50_ema": {
        "library":      "stockstats",
        "key":          "close_50_ema",
        "function":     "get_math_indicators",
        "timeframes":   ["1H", "30m"],
        "description":  "50 EMA — intermediate trend",
        "jadecap_note": (
            "Confirms intermediate bias. "
            "Price above = bullish, below = bearish."
        ),
    },

    "close_9_ema": {
        "library":      "stockstats",
        "key":          "close_9_ema",
        "function":     "get_math_indicators",
        "timeframes":   ["15m", "30m"],
        "description":  "9 EMA — short term momentum for entry timing",
        "jadecap_note": (
            "Price riding above 9 EMA = momentum long. "
            "Below = momentum short."
        ),
    },

    "atr": {
        "library":      "stockstats",
        "key":          "atr",
        "function":     "get_math_indicators",
        "timeframes":   ["15m", "1H"],
        "description":  "Average True Range — stop loss sizing and contract calculation",
        "jadecap_note": (
            "CRITICAL for contract sizing. "
            "Stop = 1x ATR beyond OB or candle 1 of FVG. "
            "Contracts = $500 / (ATR x point_value). "
            "Wide ATR = fewer contracts. Tight ATR = more contracts."
        ),
        "formula": "contracts = 500 / (atr_value x point_value)",
    },

    "adx": {
        "library":      "stockstats",
        "key":          "adx",
        "function":     "get_math_indicators",
        "timeframes":   ["1H", "4H"],
        "description":  "ADX — trend strength confirmation",
        "jadecap_note": (
            "ADX above 25 = strong trend — ICT setups high probability. "
            "ADX 20-25 = borderline — reduce size or proceed with caution. "
            "ADX below 20 = choppy/ranging — NO TRADE."
        ),
        "threshold": 25,
    },

    "rsi": {
        "library":      "stockstats",
        "key":          "rsi",
        "function":     "get_math_indicators",
        "timeframes":   ["15m"],
        "description":  "RSI — momentum confirmation",
        "jadecap_note": (
            "RSI below 30 in discount = oversold long confluence. "
            "RSI above 70 in premium = overbought short confluence. "
            "Use as confluence only — never primary signal."
        ),
        "oversold":  30,
        "overbought": 70,
    },

    "supertrend": {
        "library":      "stockstats",
        "key":          "supertrend",
        "function":     "get_math_indicators",
        "timeframes":   ["1H", "4H"],
        "description":  "Supertrend — directional bias filter",
        "jadecap_note": (
            "Price above Supertrend = bullish bias confirmed. "
            "Price below Supertrend = bearish bias confirmed. "
            "Flip of Supertrend = potential bias change — check HTF."
        ),
    },

    # ── manual calculations ───────────────────────────────────────────

    "midnight_open": {
        "library":      "manual",
        "function":     "get_midnight_open",
        "timeframes":   ["1m"],
        "description":  "NY Midnight Open — 12:00 AM EST price",
        "jadecap_note": (
            "KEY reference price for the entire trading day. "
            "All bias decisions are relative to this line. "
            "Above midnight open = PREMIUM (shorts favored). "
            "Below midnight open = DISCOUNT (longs favored). "
            "Mark this before anything else every morning."
        ),
        "premium":  "price above midnight open = sell zone",
        "discount": "price below midnight open = buy zone",
    },

    "fib_ote": {
        "library":      "manual",
        "function":     "get_fib_ote",
        "timeframes":   ["15m", "1H", "4H", "1W"],
        "ote_low":      0.62,
        "ote_high":     0.79,
        "levels":       [0.236, 0.382, 0.50, 0.618, 0.705, 0.79],
        "description":  "Fibonacci OTE — Optimal Trade Entry 62-79%",
        "jadecap_note": (
            "Anchor Fib to most recent confirmed swing H/L. "
            "Bullish: anchor from swing LOW to swing HIGH. "
            "Bearish: anchor from swing HIGH to swing LOW. "
            "OTE zone 62-79% = institutional entry area. "
            "NEVER buy in premium (above 50%). "
            "NEVER sell in discount (below 50%). "
            "Entry 5 in JadeCap playbook."
        ),
        "premium_above":  0.50,
        "discount_below": 0.50,
        "ote_entry":      "62-79% retracement = ideal entry zone",
    },

    "killzone_timer": {
        "library":      "manual",
        "function":     "get_killzone_status",
        "timeframes":   ["realtime"],
        "description":  "Kill Zone timer — is current time inside a valid window",
        "jadecap_note": (
            "HARD RULE: no trades outside Kill Zones. "
            "AM: 9:30-11:30 EST. Silver Bullet 1: 10:00-11:00. "
            "PM: 1:00-4:00 EST. Silver Bullet 2: 2:00-3:00. "
            "If not in Kill Zone -> output NO TRADE immediately."
        ),
    },

    "displacement_candle": {
        "library":      "manual",
        "function":     "get_displacement_candle",
        "timeframes":   ["5m", "15m"],
        "description":  "Strong candle moving away from swept liquidity level",
        "min_body_pct": 0.6,
        "jadecap_note": (
            "Required before any entry. "
            "Displacement = strong directional candle after liquidity sweep. "
            "Confirms institutional intent and direction. "
            "No displacement = no trade — wait for it."
        ),
        "bull_signal": "Strong bullish candle after SSL sweep = long displacement",
        "bear_signal": "Strong bearish candle after BSL sweep = short displacement",
    },

    "liquidity_sweep": {
        "library":      "manual",
        "function":     "get_liquidity_sweep",
        "timeframes":   ["5m", "15m"],
        "description":  "Confirms a liquidity pool has been raided this session",
        "jadecap_note": (
            "Price MUST sweep a key level before entry. "
            "Valid sweeps: equal H/L, session H/L, prev day H/L. "
            "Sweep + displacement + FVG/OB = full confluence setup. "
            "No sweep = accumulation phase still — wait."
        ),
        "bull_signal": "SSL swept + bullish displacement = long entry valid",
        "bear_signal": "BSL swept + bearish displacement = short entry valid",
    },

    "breaker_block": {
        "library":      "manual",
        "function":     "get_breaker_block",
        "timeframes":   ["15m", "1H"],
        "description":  "Failed OB that flipped — now acts as opposite S/R",
        "jadecap_note": (
            "Identify an OB that gets violated (market structure break). "
            "The breached OB becomes the Breaker Block zone. "
            "Wait for price to retrace back into the Breaker. "
            "Very high probability when Breaker pairs with FVG. "
            "Entry 4 in JadeCap playbook."
        ),
        "bull_signal": "Price retraces into bullish Breaker — enter long",
        "bear_signal": "Price retraces into bearish Breaker — enter short",
    },

    "amd_phase": {
        "library":      "manual",
        "function":     "get_amd_phase",
        "timeframes":   ["15m", "1H"],
        "description":  "ICT Power of Three — current AMD phase detection",
        "jadecap_note": (
            "Accumulation: Asia session range-bound, no direction. "
            "Manipulation: London raids Asian H or L — retail trapped. "
            "Distribution: NY delivers true directional move. "
            "JadeCap ONLY trades Distribution phase (NY session)."
        ),
        "phases": {
            "accumulation":  "Asia — range building, do not trade",
            "manipulation":  "London — liquidity raid, note direction",
            "distribution":  "NY AM — true move, JadeCap entry window",
        },
        "rule": "DO NOT trade if daily target hit before Kill Zone opens",
    },

    # ── new in v2: NDOG, NWOG, SFP Detection ─────────────────────────

    "ndog": {
        "library":      "manual",
        "function":     "get_ndog",
        "timeframes":   ["15m", "1H"],
        "description":  "New Day Opening Gap — 5PM close to 6PM open",
        "jadecap_note": (
            "50% level (consequent encroachment) = strongest reaction zone. "
            "Mark before session."
        ),
    },

    "nwog": {
        "library":      "manual",
        "function":     "get_nwog",
        "timeframes":   ["1H", "1D"],
        "description":  "New Week Opening Gap — Friday 5PM close to Sunday 6PM open",
        "jadecap_note": (
            "Weekly bias reference. 50% CE level is the key zone. "
            "Mark on Mondays."
        ),
    },

    "sfp_detection": {
        "library":      "manual",
        "function":     "get_sfp",
        "timeframes":   ["1H"],
        "description":  "Swing Failure Pattern — JadeCap's #1 strategy engine",
        "jadecap_note": (
            "3-candle swing pattern. Breach + close back inside = SFP confirmed. "
            "This is THE signal."
        ),
    },
}


# =====================================================================
# 10. AMD — POWER OF THREE
# =====================================================================
# The AMD (Accumulation-Manipulation-Distribution) framework is the
# backbone of the ICT methodology. It describes how institutional
# order flow creates a predictable 3-phase daily cycle.
#
# Accumulation (Asia): Range builds, no direction.
# Manipulation (London): False breakout raids retail stops.
# Distribution (NY): True directional move — this is where we trade.
#
# Critical rule: if the target H/L has already been hit before
# your Kill Zone opens, the setup is invalid. Wait for tomorrow.
# =====================================================================

AMD = {
    "accumulation": {
        "session":     "asia",
        "description": "Smart money quietly builds positions. Range-bound price.",
        "action":      "DO NOT TRADE. Mark the range H/L for manipulation reference.",
    },
    "manipulation": {
        "session":     "london",
        "description": "Liquidity raid. False breakout. Retail gets trapped.",
        "action": (
            "Note direction of London sweep. "
            "If London raids Asian Low -> bias is BULLISH for NY. "
            "If London raids Asian High -> bias is BEARISH for NY."
        ),
    },
    "distribution": {
        "session":     "ny_am",
        "description": "True directional move. JadeCap entry window.",
        "action": (
            "Wait for Kill Zone. "
            "Enter on FVG/OB retracement after displacement. "
            "Target PDH or PDL."
        ),
    },
    "critical_rule": (
        "DO NOT trade if the target high/low has already been hit "
        "before your Kill Zone opens. "
        "The setup requires catching the manipulation into distribution. "
        "If the move already happened — wait for tomorrow."
    ),
}


# =====================================================================
# 11. DAILY SWEEP — Swing Failure Pattern (SFP)
# =====================================================================
# JadeCap's #1 priority strategy. The Daily Sweep uses Swing Failure
# Patterns on the 1H chart to identify liquidity raids before the
# true directional move begins.
#
# Workflow:
#   1. At 8:00 AM EST, map all 1H swing highs and lows.
#   2. Wait for price to BREACH a mapped swing point (taking stops).
#   3. The hourly candle must CLOSE BACK INSIDE the range = SFP.
#   4. Drop to LTF (1m/5m/15m) for precise entry via FVG or MSS.
#
# This strategy takes priority 0 — it overrides all other entries
# when an SFP is confirmed.
# =====================================================================

DAILY_SWEEP = {
    "name":        "The Daily Sweep — Swing Failure Pattern (SFP)",
    "priority":    0,
    "description": (
        "JadeCap's 'one strategy for life'. Uses SFPs on 1H chart "
        "to catch liquidity raids before true directional move."
    ),
    "pre_market_time": "08:00",
    "timeframe":       "1H",
    "ltf_entry_timeframes": ["1m", "5m", "15m"],
    "steps": {
        "step_1_map": (
            "At 8:00 AM EST, identify all hourly swing highs/lows from "
            "prior session. Swing low = 3-candle pattern where middle "
            "candle low is flanked by two higher lows. Validate only "
            "after 3rd candle closes."
        ),
        "step_2_wait": (
            "Price must BREACH a mapped swing point — running stops. "
            "Mere touch is not enough. The breach takes the liquidity."
        ),
        "step_3_confirm": (
            "The hourly candle must CLOSE BACK INSIDE the range after "
            "breaching. This candle-close confirmation IS the SFP."
        ),
        "step_4_execute": (
            "Drop to 1m/5m/15m for entry precision using FVGs, MSS, "
            "turtle soup, or breaker blocks."
        ),
    },
    "example": (
        "NQ 1H: 3R on 1H alone -> refined to significantly higher R "
        "on 5m entry"
    ),
    "holiday_caution": (
        "During low-volume days (Thanksgiving, Black Friday) SFPs become "
        "'sketchy and unreliable'. Stand aside or reduce size significantly."
    ),
    "jadecap_quote": "Do not be the first person rushing through the door.",
}


# =====================================================================
# 12. DRAW ON LIQUIDITY — 5-question pre-trade framework
# =====================================================================
# Before considering any entry, all 5 questions must be answered.
# This framework ensures that the trader has identified WHERE price
# is being delivered (the draw on liquidity) before risking capital.
#
# The questions cover: trend state, premium/discount zone, liquidity
# targets, unfilled inefficiencies, and NWOG/NDOG gap levels.
#
# IPDA note: Markets cycle from liquidity to imbalance to liquidity.
# Quarterly shifts every 3-4 months reset the delivery algorithm.
# =====================================================================

DRAW_ON_LIQUIDITY = {
    "description": (
        "5-question framework — answer ALL before considering any entry"
    ),
    "jadecap_quote": (
        "Everything starts with an idea. The trade idea is birthed "
        "when there's an OBVIOUS draw on liquidity."
    ),
    "questions": [
        {
            "id":       "q1_trend",
            "question": "Is the market trending or consolidating?",
            "detail": (
                "HH/HL = bullish, LH/LL = bearish, "
                "range = wait for FVG displacement break"
            ),
        },
        {
            "id":       "q2_zone",
            "question": "Premium or discount relative to dealing range?",
            "detail": (
                "Above 50% = premium (sell only). "
                "Below 50% = discount (buy only). Absolute rule."
            ),
        },
        {
            "id":       "q3_liquidity",
            "question": "Are there equal H/L vulnerable to a sweep?",
            "detail": (
                "EQH = BSL (shorts target). EQL = SSL (longs target). "
                "Sweep identifies direction."
            ),
        },
        {
            "id":       "q4_inefficiency",
            "question": "Is there an unfilled inefficiency aligned with bias?",
            "detail": (
                "4H/Daily FVGs act as magnets. Map the gap, "
                "wait for price to reach it."
            ),
        },
        {
            "id":       "q5_gaps",
            "question": "NWOG/NDOG targets?",
            "detail": (
                "50% CE level of any gap = strongest reaction zone. "
                "Mark before session opens."
            ),
        },
    ],
    "ipda_note": (
        "Markets move: liquidity -> imbalance -> liquidity. "
        "Quarterly shifts every 3-4 months reset delivery."
    ),
}


# =====================================================================
# 13. NDOG — New Day Opening Gap
# =====================================================================
# The NDOG is the gap between the 5:00 PM EST close and the 6:00 PM
# EST open. The 50% consequent encroachment (CE) level of this gap
# is the strongest intraday reaction zone. Always mark the NDOG
# and its 50% level on the chart before the session begins.
# =====================================================================

NDOG = {
    "name":        "New Day Opening Gap",
    "gap_start":   "17:00",
    "gap_end":     "18:00",
    "description": "Gap between 5PM close and 6PM open",
    "key_level":   "50% consequent encroachment — strongest reaction zone",
    "usage":       "Price frequently retests to fill. Mark 50% level before session.",
}


# =====================================================================
# 14. NWOG — New Week Opening Gap
# =====================================================================
# The NWOG is the gap from Friday's 5:00 PM EST close to Sunday's
# 6:00 PM EST open. The 50% CE level provides weekly directional
# bias. Mark it on Mondays before the first session begins.
# =====================================================================

NWOG = {
    "name":        "New Week Opening Gap",
    "gap_start":   "Friday 17:00",
    "gap_end":     "Sunday 18:00",
    "description": "Gap from Friday 5PM close to Sunday 6PM open",
    "key_level":   "50% consequent encroachment — weekly directional bias",
    "usage":       "Mark on Mondays. Used for weekly directional bias.",
}


# =====================================================================
# 15. IPDA — Interbank Price Delivery Algorithm
# =====================================================================
# The IPDA describes how institutional order flow delivers price
# from one liquidity pool to the next, through imbalances (FVGs).
# Tracking 20/40/60-day highs and lows identifies the institutional
# delivery targets. Quarterly shifts (every 3-4 months) reset the
# directional delivery of the algorithm.
# =====================================================================

IPDA = {
    "name":             "Interbank Price Delivery Algorithm",
    "description": (
        "Markets move from liquidity to imbalance to liquidity. "
        "Quarterly shifts reset delivery."
    ),
    "lookback_periods": [20, 40, 60],
    "quarterly_shift":  "Every 3-4 months, directional delivery resets",
    "usage": (
        "Track 20/40/60-day highs and lows for institutional "
        "delivery targets"
    ),
}


# =====================================================================
# 16. ENTRY MODELS — 6 models (Entry 0-5) with full rules
# =====================================================================
# JadeCap defines 6 entry models, ranked by priority.
# Entry 0 (Daily Sweep SFP) is NEW in v2 and takes absolute priority
# when an SFP is confirmed on the 1H chart. Entries 1-5 are the
# original ICT playbook models.
#
# Each model specifies:
#   - active: whether the model is enabled
#   - priority: lower number = higher priority
#   - timeframes: which bars the model operates on
#   - rules: ordered list of conditions that must be met
#   - stop_placement: where the stop loss goes
#   - invalidation: what cancels the setup
# =====================================================================

ENTRY_MODELS = {
    "daily_sweep_sfp": {
        "active":     True,
        "name":       "Entry 0 — Daily Sweep (SFP)",
        "priority":   0,
        "timeframes": ["1H"],
        "ltf_entry":  ["1m", "5m", "15m"],
        "rules": [
            "Map all 1H swing highs/lows at 8:00 AM EST",
            "Wait for price to BREACH a mapped swing point",
            "Hourly candle must CLOSE BACK INSIDE the range = SFP confirmed",
            "Drop to LTF (1m/5m/15m) for FVG or MSS entry",
            "This is JadeCap's #1 strategy — takes priority over all other entries",
        ],
        "stop_placement": "Beyond the SFP candle wick (the sweep extreme)",
        "invalidation":   "Price continues beyond sweep without closing back inside range",
    },
    "fvg_entry": {
        "active":     True,
        "name":       "Entry 1 — Fair Value Gap",
        "priority":   1,
        "timeframes": ["5m", "15m"],
        "rules": [
            "Wait for price to retrace INTO the gap — not after rejection",
            "FVGs at HTF POI = highest confluence setup available",
            "FVG in discount zone = bull entries only",
            "FVG in premium zone = bear entries only",
            "FVG inversion confirms order flow direction has shifted",
            "Identify on 15m or 5m within the Kill Zone window",
        ],
        "stop_placement": "Behind candle 1 of the FVG",
        "invalidation":   "Price closes through the FVG without reaction",
    },
    "ob_entry": {
        "active":     True,
        "name":       "Entry 2 — Order Block",
        "priority":   2,
        "timeframes": ["15m", "1H"],
        "rules": [
            "Wait for candle closure to confirm valid OB formation",
            "High probability OBs form WITH an FVG attached",
            "Enter on retracement back into the OB body",
            "Ideal: next candle has no wick in direction of HTF flow",
            "OB must align with HTF order flow bias or skip it",
        ],
        "stop_placement": "Behind the OB body (opposite side of entry)",
        "invalidation":   "Price closes through OB body completely",
    },
    "liquidity_raid": {
        "active":     True,
        "name":       "Entry 3 — Liquidity Raid (Turtle Soup)",
        "priority":   2,
        "timeframes": ["5m", "15m"],
        "rules": [
            "Identify clear liquidity pool — equal H/L or session level",
            "Wait for the sweep — price must breach the level cleanly",
            "Confirm reversal with displacement candle + FVG formation",
            "Entry timing is critical — too early = stop out guaranteed",
            "Only valid if sweep aligns with HTF draw on liquidity",
        ],
        "stop_placement": "Above the swept high or below the swept low",
        "invalidation":   "Price continues past sweep without reversal",
    },
    "breaker_block": {
        "active":     True,
        "name":       "Entry 4 — Breaker Block",
        "priority":   3,
        "timeframes": ["15m", "1H"],
        "rules": [
            "Identify an OB that gets violated (market structure break)",
            "The breached OB becomes the Breaker Block zone",
            "Wait for price to retrace back into the Breaker",
            "Very high probability when Breaker is paired with FVG",
            "Best used after a clear liquidity raid has already occurred",
        ],
        "stop_placement": "Behind the Breaker Block zone",
        "invalidation":   "Price closes through Breaker without reaction",
    },
    "ote_fib": {
        "active":     True,
        "name":       "Entry 5 — OTE Fibonacci (Premium/Discount)",
        "priority":   3,
        "timeframes": ["15m", "1H"],
        "ote_zone":   "62% — 79% retracement",
        "rules": [
            "Anchor Fib to most recent confirmed swing high and low",
            "Bullish setups ONLY in discount (below 50% level)",
            "Bearish setups ONLY in premium (above 50% level)",
            "OTE zone: 62-79% retracement = institutional entry area",
            "Combine OTE with FVG or OB for maximum confluence",
            "Never buy in premium, never sell in discount — hard rule",
        ],
        "stop_placement": "Below swing low (bull) or above swing high (bear)",
        "invalidation":   "Price moves through 100% retracement level",
    },
}


# =====================================================================
# 17. RISK MANAGEMENT
# =====================================================================
# Core risk parameters for all JadeCap trades.
#
# Updates in v2:
#   - base_risk_pct (0.25%) and a_plus_risk_pct (0.50%) added to
#     formalize the two-tier sizing system based on A+ scoring.
#   - midday_exit_rule: True — forces exit of stalling trades before
#     the 11:30-1:00 midday chop zone.
#   - max_losing_streak_before_stop: 3 — after 3 consecutive losses,
#     stop trading for the day and reassess.
#   - scaling_note documents when to scale up from 0.25% to 0.50%.
# =====================================================================

RISK = {
    "max_loss_per_trade":   500,
    "daily_loss_limit":     500,
    "daily_profit_target":  1000,
    "min_rr":               2.0,
    "trades_per_kill_zone": 1,
    "hard_close_time":      "16:00",
    "target_1_pct":         0.50,
    "move_to_be_at_t1":     True,
    "atr_stop_multiplier":  1.0,

    # New in v2 — two-tier risk sizing
    "base_risk_pct":               0.25,
    "a_plus_risk_pct":             0.50,
    "midday_exit_rule":            True,
    "max_losing_streak_before_stop": 3,
    "half_risk_after_consecutive_losses": 2,
    "half_risk_note": (
        "After 2 consecutive losses, cut risk per trade in half "
        "until account returns to starting equity. "
        "This buys more chips to stay in the game."
    ),
    "scaling_note": (
        "0.25% standard. Scale to 0.5% ONLY on 8-10/10 A+ setups."
    ),

    "contract_formula": {
        "description": "contracts = max_loss / (stop_points x point_value)",
        "NQ":  "contracts = 500 / (stop_points x 20)",
        "MNQ": "contracts = 500 / (stop_points x 2)",
        "examples": {
            "NQ_5pt_stop":   "500 / (5 x 20)  = 5 contracts",
            "NQ_10pt_stop":  "500 / (10 x 20) = 2 contracts",
            "NQ_15pt_stop":  "500 / (15 x 20) = 1 contract",
            "NQ_25pt_stop":  "500 / (25 x 20) = 1 contract",
            "MNQ_5pt_stop":  "500 / (5 x 2)   = 50 contracts",
            "MNQ_10pt_stop": "500 / (10 x 2)  = 25 contracts",
            "MNQ_15pt_stop": "500 / (15 x 2)  = 16 contracts",
            "MNQ_25pt_stop": "500 / (25 x 2)  = 10 contracts",
        },
    },

    "target_structure": {
        "target_1": "First liquidity pool — close 50% of position",
        "target_2": "PDH or PDL — move stop to breakeven, let runner go",
    },
}


# =====================================================================
# 18. A+ SCORING — Weighted 1-10 setup quality scoring
# =====================================================================
# Matches JadeCap playbook Section 11. The A+ scoring system uses
# WEIGHTED criteria to grade every potential trade on a 1-10 scale.
# High-value confluence items are worth +2 points, standard items +1,
# and risk factors deduct -1. This weighted approach ensures HTF
# alignment and institutional footprint are valued more than timing.
#
# Max possible: 10 (all positives, no deductions: 2+2+2+1+1+1+1 = 10)
# Thresholds:
#   8-10 = A+ Setup  -> 0.50% risk (scale up, full commitment)
#   6-7  = Standard  -> 0.25% risk (normal size)
#   4-5  = Marginal  -> 0.125% risk (reduce size, consider passing)
#   <4   = NO TRADE  -> 0% risk (skip entirely)
# =====================================================================

A_PLUS_SCORING = {
    "description": "Weighted 1-10 scoring system — matches JadeCap playbook Section 11",
    "criteria": [
        {
            "id":      "htf_ltf_align",
            "name":    "HTF + LTF Alignment",
            "weight":  +2,
            "enabled": True,
            "detail":  "Weekly/Daily and 1H/15m all point same direction",
        },
        {
            "id":      "fvg_at_htf_poi",
            "name":    "FVG at HTF POI",
            "weight":  +2,
            "enabled": True,
            "detail": (
                "FVG entry coincides with 4H or Daily point of interest — "
                "institutional footprint on multiple TFs"
            ),
        },
        {
            "id":      "liq_swept",
            "name":    "Clear Liquidity Sweep First",
            "weight":  +2,
            "enabled": True,
            "detail": (
                "Prior session H/L or equal H/L raided BEFORE entry — "
                "AMD manipulation phase confirmed"
            ),
        },
        {
            "id":      "correct_zone",
            "name":    "Discount / Premium Zone",
            "weight":  +1,
            "enabled": True,
            "detail":  "Price clearly in discount (longs) or premium (shorts)",
        },
        {
            "id":      "kill_zone",
            "name":    "Inside Kill Zone Window",
            "weight":  +1,
            "enabled": True,
            "detail":  "Entry forms during AM KZ or Silver Bullet window",
        },
        {
            "id":      "sfp_confirmed",
            "name":    "SFP Confirmed on 1H",
            "weight":  +1,
            "enabled": True,
            "detail": (
                "1H Swing Failure Pattern confirmed — swing point breached "
                "and candle closed back inside the range"
            ),
        },
        {
            "id":      "three_r_plus",
            "name":    "3R+ Available",
            "weight":  +1,
            "enabled": True,
            "detail":  "Setup offers 3:1 or better R:R to structural target",
        },
        {
            "id":      "conflicting_struct",
            "name":    "No Conflicting Structure",
            "weight":  -1,
            "enabled": True,
            "detail": (
                "DEDUCT if unfilled FVGs or unswept liquidity pools "
                "between entry and target could interrupt the move"
            ),
        },
        {
            "id":      "news_risk",
            "name":    "High-Impact News Within 30 Min",
            "weight":  -1,
            "enabled": True,
            "detail": (
                "DEDUCT if FOMC, NFP, or CPI releasing during trade window — "
                "reduce size or stand aside"
            ),
        },
    ],
    "max_score": 10,
    "sizing": {
        "a_plus": {
            "range": "8-10",
            "risk":  "0.50%",
            "label": "A+ Setup — scale risk, full commitment",
        },
        "standard": {
            "range": "6-7",
            "risk":  "0.25%",
            "label": "Standard — 0.25% risk, normal execution",
        },
        "marginal": {
            "range": "4-5",
            "risk":  "0.125%",
            "label": "Marginal — reduce size, consider passing",
        },
        "no_trade": {
            "range": "below 4",
            "risk":  "0%",
            "label": "NO TRADE — skip entirely",
        },
    },
}


# =====================================================================
# 25. calculate_contracts — Contract sizing utility
# =====================================================================
# Calculates the number of contracts to trade based on the stop
# distance in points and the instrument's point value. The formula
# keeps maximum loss at $500 per trade (RISK["max_loss_per_trade"]).
#
# Examples:
#   NQ with 5-point stop:  500 / (5 * 20)  = 5 contracts
#   NQ with 10-point stop: 500 / (10 * 20) = 2 contracts
#   MNQ with 5-point stop: 500 / (5 * 2)   = 50 contracts
#
# Always returns at least 1 contract.
# =====================================================================

def calculate_contracts(stop_points: float, instrument: str = "NQ") -> int:
    """Calculate contracts to keep max loss at $500.

    Args:
        stop_points: Distance from entry to stop loss in points.
        instrument: "NQ" or "MNQ" — determines point value.

    Returns:
        Number of contracts (minimum 1).
    """
    if stop_points <= 0:
        return 1
    point_value = INSTRUMENTS.get(instrument, INSTRUMENTS["NQ"])["point_value"]
    return max(1, int(RISK["max_loss_per_trade"] / (stop_points * point_value)))


# =====================================================================
# 19. HARD RULES — 21 non-negotiable rules injected into every agent
# =====================================================================
# These rules are absolute constraints. No agent, no scoring system,
# and no market condition can override them. They are injected into
# every agent prompt as the highest-priority instructions.
#
# Rules 1-14: Original JadeCap rules.
# Rules 15-20: New in v2 — SFP confirmation, Silver Bullet protocol,
#   midday avoidance, holiday caution, and A+ scoring discipline.
# =====================================================================

HARD_RULES = [
    # Original 14 rules
    "NEVER trade against HTF order flow — Weekly/4H/Daily bias is law. No exceptions.",
    "ONLY enter inside Kill Zones: AM 9:30-11:30 or PM 1:00-4:00 EST. Nothing outside.",
    "MINIMUM 2R required before entry — measure it before placing the trade.",
    "Stop loss MUST sit behind candle 1 of FVG or the OB body. Never arbitrary.",
    "ONE trade per Kill Zone — if stopped out the window is DONE. No revenge trades.",
    "HARD CLOSE all positions by 4:00 PM EST. No overnight holds on day trades.",
    "If previous day High or Low already taken before Kill Zone — output NO TRADE.",
    "NEVER buy in premium zone — NEVER sell in discount zone. Non-negotiable.",
    "Wait for liquidity sweep BEFORE entry — no anticipation entries ever.",
    "NO TRADE without displacement candle confirming institutional direction.",
    "Max loss per trade is $500 — calculate contracts based on stop distance.",
    "Stop trading when daily profit reaches $1,000 — lock in and protect gains.",
    "No single day loss can exceed $500 — protect the prop account.",
    "Only trade during Distribution phase (NY session). Not Accumulation or Manipulation.",

    # New in v2 — 7 additional rules (total 21)
    "1H SFP must confirm before ANY lower timeframe entry — no anticipation.",
    "Only the FIRST FVG forming in a Silver Bullet window is valid — skip subsequent ones.",
    "Unfilled Silver Bullet limit orders CANCELED when window closes — never leave orders open.",
    "No new entries 11:30 AM – 1:00 PM EST — midday chop zone. Exit stalling trades.",
    "Stand aside or reduce size 75% on holiday/low-volume days — SFPs are unreliable.",
    "A+ score below 4/10 = NO TRADE. Do not override. Discipline IS the edge.",
    "After 2 consecutive losses, CUT RISK IN HALF until account returns to starting equity — buys more chips to stay in the game.",
]


# =====================================================================
# 20. BULL SETUP CRITERIA
# =====================================================================
# Complete criteria for a valid bullish long setup. Every requirement
# must be met before entering. The list combines original ICT
# confluence requirements with v2 additions: SFP confirmation,
# Draw on Liquidity identification, OTE zone confluence, and
# NDOG/NWOG level marking.
# =====================================================================

BULL_SETUP = {
    "name": "Bullish Long Setup",
    "requirements": [
        "HTF structure is bullish — higher highs, higher lows on Weekly/4H/Daily",
        "Price is in DISCOUNT zone — below 50% Fib of HTF range",
        "Price is below Midnight Open — discount confirmed",
        "Bullish FVG on 4H or Daily is unmitigated",
        "Price has swept SELL-SIDE LIQUIDITY (equal lows, prior session low)",
        "Displacement candle forms BACK to the upside after sweep",
        "Bullish FVG or OB visible on 5m or 15m for entry",
        "Entry is inside AM or Silver Bullet Kill Zone",
        # New in v2
        "1H SFP confirmed — hourly candle swept a swing low and CLOSED BACK INSIDE the range",
        "Draw on Liquidity identified — know WHERE price is being delivered before entering",
        "OTE zone (62-79%) contains FVG or OB for maximum confluence",
        "NDOG/NWOG 50% level marked if applicable",
    ],
    "target":       "Previous daily HIGH — buy-side liquidity above",
    "stop":         "Behind candle 1 of bullish FVG or bullish OB body",
    "invalidation": "Price closes below the swept low — setup completely failed",
}


# =====================================================================
# 21. BEAR SETUP CRITERIA
# =====================================================================
# Mirror of BULL_SETUP for bearish short trades. All requirements
# are the inverse: premium zone instead of discount, BSL sweep
# instead of SSL, and PDL target instead of PDH.
# =====================================================================

BEAR_SETUP = {
    "name": "Bearish Short Setup",
    "requirements": [
        "HTF structure is bearish — lower highs, lower lows on Weekly/4H/Daily",
        "Price is in PREMIUM zone — above 50% Fib of HTF range",
        "Price is above Midnight Open — premium confirmed",
        "Bearish FVG on 4H or Daily is unmitigated",
        "Price has swept BUY-SIDE LIQUIDITY (equal highs, prior session high)",
        "Displacement candle forms BACK to the downside after sweep",
        "Bearish FVG or OB visible on 5m or 15m for entry",
        "Entry is inside AM or Silver Bullet Kill Zone",
        # New in v2
        "1H SFP confirmed — hourly candle swept a swing high and CLOSED BACK INSIDE the range",
        "Draw on Liquidity identified — know WHERE price is being delivered before entering",
        "OTE zone (62-79%) contains FVG or OB for maximum confluence",
        "NDOG/NWOG 50% level marked if applicable",
    ],
    "target":       "Previous daily LOW — sell-side liquidity below",
    "stop":         "Behind candle 1 of bearish FVG or bearish OB body",
    "invalidation": "Price closes above the swept high — setup completely failed",
}


# =====================================================================
# 22. PRE-TRADE CHECKLIST — all 14 items must pass before entry
# =====================================================================
# Expanded from 10 to 14 items in v2. The 4 new items enforce:
#   - SFP confirmation on 1H before any LTF entry
#   - Draw on Liquidity identification (know the target)
#   - A+ score calculation (minimum 4/10 to proceed)
#   - Midday chop zone avoidance (no entries 11:30-1:00)
#
# Each item has a required flag. apply_settings() can override
# individual items if the UI allows toggling checklist requirements.
# =====================================================================

CHECKLIST = [
    {
        "id":          "htf_bias",
        "description": "HTF Bias Confirmed",
        "detail":      "Weekly/Daily structure AND 4H FVG order flow both point same direction",
        "required":    True,
    },
    {
        "id":          "correct_zone",
        "description": "Price in Correct Zone",
        "detail":      "Discount for longs, premium for shorts — relative to Fib and Midnight Open",
        "required":    True,
    },
    {
        "id":          "liq_swept",
        "description": "Liquidity Swept",
        "detail":      "A prior H/L, equal H/L, or session level has been raided before entry",
        "required":    True,
    },
    {
        "id":          "displacement",
        "description": "Displacement Candle Present",
        "detail":      "Strong move away from swept level confirms institutional intent",
        "required":    True,
    },
    {
        "id":          "pd_array",
        "description": "LTF PD Array Identified",
        "detail":      "FVG, OB, or Breaker Block visible on 5m or 15m as entry trigger",
        "required":    True,
    },
    {
        "id":          "kill_zone",
        "description": "Inside Kill Zone",
        "detail":      "Current time is 9:30-11:30 AM or 1:00-4:00 PM EST",
        "required":    True,
    },
    {
        "id":          "min_2r",
        "description": "Minimum 2R Available",
        "detail":      "Distance from entry to structural target offers at least 2:1 R:R",
        "required":    True,
    },
    {
        "id":          "target_not_hit",
        "description": "Daily Target Not Yet Hit",
        "detail":      "Previous day High or Low has NOT already been taken today",
        "required":    True,
    },
    {
        "id":          "profit_ok",
        "description": "Daily Profit Under $1,000",
        "detail":      "Has not yet hit daily profit target — still valid to trade",
        "required":    True,
    },
    {
        "id":          "loss_ok",
        "description": "Daily Loss Under $500",
        "detail":      "Has not hit max daily loss — account protected",
        "required":    True,
    },
    # New in v2 — 4 additional checklist items (total 14)
    {
        "id":          "sfp_confirmed",
        "description": "1H SFP Confirmed",
        "detail":      "1H SFP Confirmed — swing point swept and candle closed back inside",
        "required":    True,
    },
    {
        "id":          "dol_identified",
        "description": "Draw on Liquidity Identified",
        "detail":      "Draw on Liquidity Identified — target price known before entry",
        "required":    True,
    },
    {
        "id":          "a_plus_score",
        "description": "A+ Score Calculated",
        "detail":      "A+ Score Calculated — minimum 4/10 to proceed, 8+/10 for full size",
        "required":    True,
    },
    {
        "id":          "not_midday",
        "description": "Not in Midday Chop Zone",
        "detail":      "Not in Midday Chop Zone — current time is NOT 11:30 AM - 1:00 PM EST",
        "required":    True,
    },
]


# =====================================================================
# 23. HOLIDAY RULES — low-volume day avoidance
# =====================================================================
# SFPs become unreliable on low-volume days because institutional
# participation drops significantly. Without institutional order flow,
# the liquidity raids that create SFPs lack follow-through, leading
# to false signals and whipsaw price action.
#
# On listed holidays: stand aside completely or reduce position size
# by 75%. This is not optional — it is a risk management rule.
# =====================================================================

HOLIDAY_RULES = {
    "enabled":     True,
    "description": "SFPs become unreliable on low-volume days",
    "holidays": [
        "Thanksgiving Day",
        "Black Friday",
        "Christmas Eve",
        "New Year's Eve",
        "July 4th",
        "Good Friday",
        "MLK Day",
        "Presidents Day",
    ],
    "action": "Stand aside completely or reduce size by 75%",
    "jadecap_quote": (
        "During low-volume days SFPs become sketchy and unreliable."
    ),
}


# =====================================================================
# 24. TRADE OUTPUT FORMAT — what Trader agent must output
# =====================================================================
# This template defines the exact format that the Trader agent must
# produce for every analysis. It includes all decision fields plus
# the v2 additions: A+ Score, SFP Status, Draw on Liquidity target,
# NDOG level, and NWOG level.
#
# The Trader agent MUST fill in every field. "N/A" is acceptable
# for NDOG/NWOG when those gaps are not relevant (e.g., NWOG is
# only marked on Mondays).
# =====================================================================

TRADE_OUTPUT_FORMAT = """
TRADE PLAN (fill in EVERY field — even for NO TRADE):
Current Price: [REQUIRED — always show the >>> CURRENT PRICE from above, even if NO TRADE]
Direction:    LONG / SHORT / NO TRADE
Entry:        [exact price or N/A if NO TRADE]
Stop Loss:    [exact price or N/A]
Target 1:     [price — first liquidity pool] / N/A
Target 2:     [price — PDH or PDL] / N/A
Stop Points:  [number] / N/A
Risk:         $[amount] / $0
Contracts:    [number] / 0
R:R Ratio:    [number]:1 / N/A
Kill Zone:    [which window or "Outside KZ — market OPEN, waiting for next window"]
A+ Score:     [X/10] — [Full Size / Half Size / Marginal / NO TRADE]
SFP Status:   CONFIRMED at [price] on 1H / NOT YET / NO SFP TODAY
Draw on Liquidity: [target price] — [reason]
NDOG Level:   [price] (50% CE) / N/A
NWOG Level:   [price] (50% CE) / N/A (Monday only)
Invalidation: [exact price action] / N/A
AMD Phase:    [from calc_amd_phase — use ACTUAL session not just "Distribution"]
Checklist:    [X/14 PASS — list all 14]

FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**
"""


# =====================================================================
# 27. JADECAP_CONFIG — Master configuration dictionary
# =====================================================================
# Single import point for all agents. Every section defined above
# is aggregated here. Agents can import JADECAP_CONFIG and access
# any section via key lookup, or import individual sections directly.
#
# Usage in agents:
#   from tradingagents.jadecap_config import JADECAP_CONFIG
#   risk = JADECAP_CONFIG["risk"]
#   rules = JADECAP_CONFIG["hard_rules"]
#
# Or direct imports:
#   from tradingagents.jadecap_config import RISK, HARD_RULES
# =====================================================================

JADECAP_CONFIG = {
    # ── Active settings — change these daily ──────────────────────
    "strategy":          "jadecap",
    "active_instrument": "NQ",
    "active_firm":       "apex",

    # ── All config sections ───────────────────────────────────────
    "instruments":        INSTRUMENTS,
    "prop_firms":         PROP_FIRMS,
    "live_price":         LIVE_PRICE,
    "sessions":           SESSIONS,
    "kill_zones":         KILL_ZONES,
    "silver_bullet":      SILVER_BULLET,
    "midday_avoidance":   MIDDAY_AVOIDANCE,
    "timeframes":         TIMEFRAMES,
    "indicators":         ICT_INDICATORS,
    "amd":                AMD,
    "daily_sweep":        DAILY_SWEEP,
    "draw_on_liquidity":  DRAW_ON_LIQUIDITY,
    "ndog":               NDOG,
    "nwog":               NWOG,
    "ipda":               IPDA,
    "entry_models":       ENTRY_MODELS,
    "risk":               RISK,
    "a_plus_scoring":     A_PLUS_SCORING,
    "hard_rules":         HARD_RULES,
    "bull_setup":         BULL_SETUP,
    "bear_setup":         BEAR_SETUP,
    "checklist":          CHECKLIST,
    "holiday_rules":      HOLIDAY_RULES,
    "trade_output_format": TRADE_OUTPUT_FORMAT,
}


# =====================================================================
# 26. apply_settings — Runtime override from UI settings
# =====================================================================
# Called by the runner before creating TradingAgentsGraph. Since agents
# import RISK, JADECAP_CONFIG, etc. as module-level references to
# mutable dicts, mutating them here affects all agents immediately.
#
# Updates in v2:
#   - a_plus_scoring overrides (enable/disable criteria)
#   - midday_avoidance overrides (start/end times, enable/disable)
#   - holiday_rules overrides (add/remove holidays, enable/disable)
# =====================================================================

def apply_settings(settings: dict) -> None:
    """Apply saved UI settings to jadecap_config module globals.

    Called by the runner before creating TradingAgentsGraph.
    Since agents import RISK, JADECAP_CONFIG, etc. as module-level
    references to mutable dicts, mutating them here affects all agents.

    Args:
        settings: Dict from SQLite strategy_config, may contain:
            - instrument: "NQ" or "MNQ"
            - min_rr: float (e.g. 2.0, 2.5, 3.0)
            - max_trades_per_kz: int (e.g. 1, 2, 3)
            - max_loss_per_trade: int (e.g. 500)
            - daily_profit_target: int (e.g. 1000)
            - entry_models: list of active model keys
            - active_firm: str (e.g. "apex", "mff", "lucid")
            - a_plus_scoring: dict of overrides for scoring criteria
            - midday_avoidance: dict with start/end/enabled overrides
            - holiday_rules: dict with holidays list or enabled flag
    """
    if not settings:
        return

    # -- Instrument ------------------------------------------------
    if "instrument" in settings:
        inst = settings["instrument"]
        if inst in INSTRUMENTS:
            JADECAP_CONFIG["active_instrument"] = inst

    # -- Active firm -----------------------------------------------
    if "active_firm" in settings:
        firm = settings["active_firm"]
        if firm in PROP_FIRMS:
            JADECAP_CONFIG["active_firm"] = firm

    # -- Risk parameters -------------------------------------------
    if "min_rr" in settings:
        RISK["min_rr"] = float(settings["min_rr"])

    if "max_trades_per_kz" in settings:
        RISK["trades_per_kill_zone"] = int(settings["max_trades_per_kz"])

    if "max_loss_per_trade" in settings:
        RISK["max_loss_per_trade"] = int(settings["max_loss_per_trade"])
        RISK["daily_loss_limit"] = int(settings["max_loss_per_trade"])

    if "daily_profit_target" in settings:
        RISK["daily_profit_target"] = int(settings["daily_profit_target"])

    # -- Entry models on/off ---------------------------------------
    if "entry_models" in settings:
        active_models = settings["entry_models"]
        if isinstance(active_models, list):
            for key, model in ENTRY_MODELS.items():
                model["active"] = key in active_models

    # -- Checklist requirements on/off -----------------------------
    if "checklist" in settings:
        checklist_overrides = settings["checklist"]
        if isinstance(checklist_overrides, dict):
            for item in CHECKLIST:
                if item["id"] in checklist_overrides:
                    item["required"] = bool(checklist_overrides[item["id"]])

    # -- A+ Scoring overrides (new in v2) --------------------------
    # Allows UI to toggle individual scoring criteria on/off or
    # adjust the sizing thresholds.
    if "a_plus_scoring" in settings:
        scoring_overrides = settings["a_plus_scoring"]
        if isinstance(scoring_overrides, dict):
            # Override individual criteria enabled/disabled
            if "criteria" in scoring_overrides:
                criteria_map = {
                    c["id"]: c for c in A_PLUS_SCORING["criteria"]
                }
                for crit_id, enabled in scoring_overrides["criteria"].items():
                    if crit_id in criteria_map:
                        criteria_map[crit_id]["enabled"] = bool(enabled)
            # Override sizing thresholds
            if "sizing" in scoring_overrides:
                for tier, overrides in scoring_overrides["sizing"].items():
                    if tier in A_PLUS_SCORING["sizing"]:
                        A_PLUS_SCORING["sizing"][tier].update(overrides)

    # -- Midday avoidance overrides (new in v2) --------------------
    # Allows UI to adjust the midday chop zone window or disable it.
    if "midday_avoidance" in settings:
        midday_overrides = settings["midday_avoidance"]
        if isinstance(midday_overrides, dict):
            if "start" in midday_overrides:
                MIDDAY_AVOIDANCE["start"] = midday_overrides["start"]
            if "end" in midday_overrides:
                MIDDAY_AVOIDANCE["end"] = midday_overrides["end"]
            if "enabled" in midday_overrides:
                MIDDAY_AVOIDANCE["enabled"] = bool(
                    midday_overrides["enabled"]
                )

    # -- Holiday rules overrides (new in v2) -----------------------
    # Allows UI to add/remove holidays or disable holiday avoidance.
    if "holiday_rules" in settings:
        holiday_overrides = settings["holiday_rules"]
        if isinstance(holiday_overrides, dict):
            if "holidays" in holiday_overrides:
                if isinstance(holiday_overrides["holidays"], list):
                    HOLIDAY_RULES["holidays"] = holiday_overrides["holidays"]
            if "enabled" in holiday_overrides:
                HOLIDAY_RULES["enabled"] = bool(
                    holiday_overrides["enabled"]
                )
            if "action" in holiday_overrides:
                HOLIDAY_RULES["action"] = holiday_overrides["action"]

    # -- Flat toggle keys from the Settings UI -------------------------
    # The UI sends flat keys like midday_avoidance_enabled and
    # holiday_rules_enabled (booleans) instead of nested dicts.
    if "midday_avoidance_enabled" in settings:
        MIDDAY_AVOIDANCE["enabled"] = bool(settings["midday_avoidance_enabled"])

    if "holiday_rules_enabled" in settings:
        HOLIDAY_RULES["enabled"] = bool(settings["holiday_rules_enabled"])

    # -- Base risk percentage ------------------------------------------
    if "base_risk_pct" in settings:
        RISK["base_risk_pct"] = float(settings["base_risk_pct"])

    # -- Hard close time -----------------------------------------------
    if "hard_close_time" in settings:
        RISK["hard_close_time"] = settings["hard_close_time"]

    # -- Kill Zones on/off ---------------------------------------------
    # UI sends a list of active kill zone keys: ["am", "silver1", "pm", "silver2"]
    # Any KZ not in the list gets active=False → agent outputs NO TRADE for that window
    if "kill_zones" in settings:
        active_kzs = settings["kill_zones"]
        if isinstance(active_kzs, list):
            kz_key_map = {
                "am": "am",
                "silver1": "silver_bullet_1",
                "pm": "pm",
                "silver2": "silver_bullet_2",
            }
            for ui_key, config_key in kz_key_map.items():
                if config_key in KILL_ZONES:
                    KILL_ZONES[config_key]["active"] = ui_key in active_kzs
