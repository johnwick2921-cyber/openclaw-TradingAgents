# Backtest Enhancements: 1H SFP + Multi-Contract + Memory Integration

**Date:** 2026-04-03
**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Status:** PLANNED

## Summary

Three enhancements to the JadeCap ICT backtester:

1. **1H SFP Detection** -- Model 0 (SFP_RAID, score 9) never fires because `_find_entry_realtime` only uses 5m data. JadeCap's highest-conviction signal is the 1H SFP. Add 1H candle aggregation and SFP detection so Model 0 actually triggers.
2. **Multi-Contract Sizing** -- Currently hardcoded to 5 MNQ ($2/pt). Add CLI args for point value and contract count, run comparison across 5 MNQ / 10 MNQ / 1 NQ.
3. **Memory Integration** -- Feed backtest trade outcomes into BM25 agent memory via `FinancialSituationMemory` and persist to SQLite.

## Current State

- Backtest file: `/home/hoang/.openclaw/workspace/openclaw/backtest.py` (757 lines)
- Data source: `openclaw.dataflows.databento_nq.get_databento_ohlcv(symbol, start_date, end_date, timeframe)` -- returns CSV string
- Memory: `openclaw.memory.FinancialSituationMemory` with `add_situations([(situation, recommendation)])`
- Persistence: `openclaw.memory_persistence.persist_memories(memories_dict, db_path, run_id)`
- Database: `openclaw.database.get_db(db_path)` -- SQLite with `memories` table (agent_name, situation, recommendation, run_id, created_at)
- Module globals: `POINT_VALUE = 2`, `FIXED_CONTRACTS = 5`, `MAX_LOSS = 500`

## Baseline Metrics (5 MNQ, 1 year)

| Metric | Value |
|--------|-------|
| Profit Factor | 2.02 |
| Win Rate | 40% |
| Total P&L | +$12,395 |
| SFP_RAID triggers | 0 (broken) |

---

## Feature 1: Add 1H SFP Detection

### Problem

In `_find_entry_realtime` (line 282), Model 0 (SFP_RAID) at line 388 requires `sweep_seen` and `fvgs` but `sweep_seen` is a 1m-level liquidity sweep (PDH/PDL raid). The actual JadeCap Model 0 requires a **1H SFP** -- a 1-hour candle that sweeps a prior swing high/low and closes back inside the range. The backtester never constructs 1H candles, so SFP_RAID with score 9 never fires.

### Design

1. In `_find_entry_realtime`, aggregate the **full day's 1m data up to the current candle** into 1H candles using the existing `_agg()` helper.
2. Add a new function `_detect_1h_sfp()` that scans 1H candles for a swing failure pattern.
3. Track `sfp_1h_seen` state alongside `sweep_seen`. When a 1H SFP is confirmed, set `sfp_1h_seen`.
4. Model 0 triggers when: `sfp_1h_seen` + `fvgs` (displacement + FVG retrace after the SFP).
5. Keep existing `sweep_seen` logic for the 1m sweep -- Model 0 fires on **either** 1H SFP or 1m sweep, whichever comes first.

### Steps

- [ ] **1.1** Add `_detect_1h_sfp()` function after `_atr()` (line 84)

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Insert after line 84** (after `_atr` function):

```python
def _detect_1h_sfp(df_1h: pd.DataFrame, direction: str) -> Optional[dict]:
    """Detect 1H Swing Failure Pattern -- JadeCap's #1 signal.

    SFP: A 1H candle sweeps a prior swing high/low and CLOSES BACK INSIDE
    the prior range, trapping breakout traders.

    Long SFP: 1H candle wicks below a prior swing low but closes above it.
    Short SFP: 1H candle wicks above a prior swing high but closes below it.

    Requires at least 5 candles to establish swing points.
    """
    if len(df_1h) < 5:
        return None

    # Find swing points (local min/max over 3 bars)
    highs = df_1h["high"].values
    lows = df_1h["low"].values
    closes = df_1h["close"].values

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

    if direction == "long" and swing_lows:
        # Check if latest 1H candle sweeps a prior swing low and closes above
        for _, sw_low in reversed(swing_lows):
            if last_candle["low"] < sw_low and last_candle["close"] > sw_low:
                return {
                    "time": last_ts,
                    "sfp_type": "long",
                    "swing_level": sw_low,
                    "sweep_price": float(last_candle["low"]),
                    "close_price": float(last_candle["close"]),
                }
    elif direction == "short" and swing_highs:
        for _, sw_high in reversed(swing_highs):
            if last_candle["high"] > sw_high and last_candle["close"] < sw_high:
                return {
                    "time": last_ts,
                    "sfp_type": "short",
                    "swing_level": sw_high,
                    "sweep_price": float(last_candle["high"]),
                    "close_price": float(last_candle["close"]),
                }

    return None
```

- [ ] **1.2** Modify `_find_entry_realtime` signature to accept the full day's 1m data

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Change line 282** from:

```python
def _find_entry_realtime(kz_df: pd.DataFrame, direction: str, midnight_open: float,
                         pdh: float, pdl: float) -> Optional[dict]:
```

to:

```python
def _find_entry_realtime(kz_df: pd.DataFrame, direction: str, midnight_open: float,
                         pdh: float, pdl: float,
                         pre_kz_df: Optional[pd.DataFrame] = None) -> Optional[dict]:
```

- [ ] **1.3** Add 1H SFP state tracking and detection inside `_find_entry_realtime`

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Change line 305** (state initialization) from:

```python
    # State -- built up as we walk forward
    sweep_seen = None       # {"time": ts, "level": price, "sweep_price": price}
    displacements = []      # [{"idx": i, "candle": row, "time": ts}]
    fvgs = []               # [{"fvg_top", "fvg_bottom", "fvg_ce", "c1_low"/"c1_high", "time"}]
    obs = []                # [{"ob_high", "ob_low", "ob_ce", "time"}]
```

to:

```python
    # State -- built up as we walk forward
    sweep_seen = None       # {"time": ts, "level": price, "sweep_price": price}
    sfp_1h_seen = None      # {"time": ts, "sfp_type": str, "swing_level": float, ...}
    displacements = []      # [{"idx": i, "candle": row, "time": ts}]
    fvgs = []               # [{"fvg_top", "fvg_bottom", "fvg_ce", "c1_low"/"c1_high", "time"}]
    obs = []                # [{"ob_high", "ob_low", "ob_ce", "time"}]

    # Build 1H candles from pre-KZ + KZ data for SFP detection
    if pre_kz_df is not None and not pre_kz_df.empty:
        full_1m_for_1h = pd.concat([pre_kz_df, kz_df])
    else:
        full_1m_for_1h = kz_df
```

- [ ] **1.4** Add 1H SFP check inside the walk-forward loop

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Insert after the sweep detection block** (after line 324, before the displacement check), add:

```python
        # ── Update state: check for 1H SFP ──
        if sfp_1h_seen is None:
            # Aggregate all 1m data up to current candle into 1H
            data_up_to_now = full_1m_for_1h[full_1m_for_1h.index <= ts + pd.Timedelta(minutes=5)]
            if len(data_up_to_now) >= 60:  # need at least 1 hour of data
                df_1h = _agg(data_up_to_now, 60)
                sfp_result = _detect_1h_sfp(df_1h, direction)
                if sfp_result is not None:
                    sfp_1h_seen = sfp_result
```

- [ ] **1.5** Modify Model 0 (SFP_RAID) trigger to use 1H SFP

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Change lines 388-400** (Model 0 block) from:

```python
        # Model 0: SFP Raid -- sweep + displacement + FVG retrace (best)
        # FIX: Only use FVGs formed AFTER the sweep (time ordering)
        if sweep_seen and fvgs:
            for fvg in fvgs:
                if fvg["time"] < sweep_seen["time"]:
                    continue  # FVG predates sweep -- skip
                if direction == "long" and candle["low"] <= fvg["fvg_ce"]:
                    stop = _fvg_stop(fvg, direction)
                    return _build_entry(direction, fvg["fvg_ce"], ts, stop,
                                        "SFP_RAID", 9, {"sweep": sweep_seen["sweep_price"]})
                elif direction == "short" and candle["high"] >= fvg["fvg_ce"]:
                    stop = _fvg_stop(fvg, direction)
                    return _build_entry(direction, fvg["fvg_ce"], ts, stop,
                                        "SFP_RAID", 9, {"sweep": sweep_seen["sweep_price"]})
```

to:

```python
        # Model 0: SFP Raid -- 1H SFP OR 1m sweep + displacement + FVG retrace (best)
        # Priority: 1H SFP (score 9) > 1m sweep (score 8)
        sfp_trigger = sfp_1h_seen or sweep_seen
        if sfp_trigger and fvgs:
            trigger_time = sfp_trigger["time"]
            is_1h_sfp = sfp_1h_seen is not None
            for fvg in fvgs:
                if fvg["time"] < trigger_time:
                    continue  # FVG predates SFP/sweep -- skip
                if direction == "long" and candle["low"] <= fvg["fvg_ce"]:
                    stop = _fvg_stop(fvg, direction)
                    score = 9 if is_1h_sfp else 8
                    extra = {"sweep": sfp_trigger.get("sweep_price", sfp_trigger.get("swing_level"))}
                    if is_1h_sfp:
                        extra["sfp_1h"] = True
                        extra["sfp_swing_level"] = sfp_trigger["swing_level"]
                    return _build_entry(direction, fvg["fvg_ce"], ts, stop,
                                        "SFP_RAID", score, extra)
                elif direction == "short" and candle["high"] >= fvg["fvg_ce"]:
                    stop = _fvg_stop(fvg, direction)
                    score = 9 if is_1h_sfp else 8
                    extra = {"sweep": sfp_trigger.get("sweep_price", sfp_trigger.get("swing_level"))}
                    if is_1h_sfp:
                        extra["sfp_1h"] = True
                        extra["sfp_swing_level"] = sfp_trigger["swing_level"]
                    return _build_entry(direction, fvg["fvg_ce"], ts, stop,
                                        "SFP_RAID", score, extra)
```

- [ ] **1.6** Pass pre-KZ data to `_find_entry_realtime` from `backtest_day`

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Change line 567** from:

```python
        entry = _find_entry_realtime(kz_df, direction, mo, pdh, pdl)
```

to:

```python
        # Pass pre-KZ data for 1H SFP aggregation
        pre_kz = df.between_time("00:00", kz_start)
        entry = _find_entry_realtime(kz_df, direction, mo, pdh, pdl, pre_kz_df=pre_kz)
```

- [ ] **1.7** Verify: Run backtest and confirm SFP_RAID triggers appear

```bash
cd /home/hoang/.openclaw/workspace
python3 -m openclaw.backtest --ticker NQ --days 20 2>&1 | grep -c SFP_RAID
# Expected: > 0 (was 0 before)
```

---

## Feature 2: Multi-Contract Sizing Test

### Problem

`POINT_VALUE` (line 31) and `FIXED_CONTRACTS` (line 33) are module-level constants. No way to compare different sizing without editing the file. Need CLI args and a comparison mode.

### Steps

- [ ] **2.1** Add CLI arguments for point value and contracts

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Change lines 592-597** (argparse block) from:

```python
    parser = argparse.ArgumentParser(description="JadeCap Backtester")
    parser.add_argument("--ticker", default="NQ", help="Instrument (default: NQ)")
    parser.add_argument("--days", type=int, default=20, help="Number of trading days")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    args = parser.parse_args()
```

to:

```python
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
    parser.add_argument("--save-memory", action="store_true",
                        help="Save trade outcomes to BM25 agent memory")
    args = parser.parse_args()
```

- [ ] **2.2** Replace module-level constants with a config dict pattern

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Change lines 31-33** from:

```python
POINT_VALUE = 2   # MNQ $2/point (Micro Nasdaq)
MAX_LOSS = 500    # $500 max loss per trade
FIXED_CONTRACTS = 5  # Fixed 5 MNQ contracts
```

to:

```python
POINT_VALUE = 2   # MNQ $2/point (Micro Nasdaq) -- default, overridden by CLI
MAX_LOSS = 500    # $500 max loss per trade
FIXED_CONTRACTS = 5  # Fixed 5 MNQ contracts -- default, overridden by CLI
```

- [ ] **2.3** Add `_run_backtest()` function to encapsulate current `main()` logic

Extract the trading loop + summary from `main()` into a reusable function.

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Add before `main()`** (before line 591):

```python
def _run_backtest(ticker: str, dates: list, point_value: float, contracts: int,
                  quiet: bool = False) -> dict:
    """Run a full backtest and return results dict.

    Args:
        ticker: Instrument symbol
        dates: List of date strings (YYYY-MM-DD)
        point_value: Dollar per point (2=MNQ, 20=NQ)
        contracts: Number of contracts
        quiet: Suppress per-trade output

    Returns:
        Dict with total_pnl, wins, losses, trades list, etc.
    """
    global POINT_VALUE, FIXED_CONTRACTS
    orig_pv, orig_fc = POINT_VALUE, FIXED_CONTRACTS
    POINT_VALUE = point_value
    FIXED_CONTRACTS = contracts

    try:
        trades = []
        total_pnl = 0.0
        wins = 0
        losses = 0
        closes = 0
        no_trade_days = 0
        prev_df = None
        consecutive_losses = 0

        for date in dates:
            result = backtest_day(ticker, date, prev_df, consecutive_losses)
            if result.get("_df") is not None:
                prev_df = result["_df"]
            if result["status"] != "ok":
                continue

            trade = result.get("trade")
            if trade is None:
                no_trade_days += 1
                continue

            pnl = trade["pnl"]
            total_pnl += pnl
            result_str = trade["result"]
            if result_str == "WIN":
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

            trades.append(trade)
            if not quiet:
                half = " (HALF)" if trade.get("half_size") else ""
                model = trade.get("model", "?")
                icon = {"WIN": "+", "LOSS": "-"}.get(result_str, "=")
                print(f"  {date}  {icon} {trade['direction']:5s} {trade['kz']:3s} "
                      f"[{model:12s}] "
                      f"entry:{trade['entry']:.0f} stop:{trade['stop']:.0f} "
                      f"target:{trade['target']:.0f} exit:{trade['exit']:.0f} "
                      f"{result_str:5s}{half} ${pnl:+.0f}  (total: ${total_pnl:+.0f})")

        total_trades = wins + losses + closes
        win_rate = wins / total_trades * 100 if total_trades > 0 else 0
        avg_win = np.mean([t["pnl"] for t in trades if t["result"] == "WIN"]) if wins > 0 else 0
        avg_loss = np.mean([t["pnl"] for t in trades if t["result"] == "LOSS"]) if losses > 0 else 0
        profit_factor = abs(avg_win * wins / (avg_loss * losses)) if (losses > 0 and avg_loss != 0) else float("inf")

        # Max drawdown
        peak = 0
        max_dd = 0
        running = 0
        for t in trades:
            running += t["pnl"]
            peak = max(peak, running)
            max_dd = max(max_dd, peak - running)

        return {
            "ticker": ticker,
            "point_value": point_value,
            "contracts": contracts,
            "label": f"{contracts} {'MNQ' if point_value == 2 else 'NQ'} (${point_value}/pt)",
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
            "trades": trades,
        }
    finally:
        POINT_VALUE = orig_pv
        FIXED_CONTRACTS = orig_fc
```

- [ ] **2.4** Add comparison table printer

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Add after `_run_backtest()`**:

```python
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
```

- [ ] **2.5** Update `main()` to use `_run_backtest()` and `--compare`

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Replace the main() body** (from line ~599 after argparse, through end of function) with:

```python
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
        # Run 3 configs and compare
        configs = [
            (2, 5, "5 MNQ"),
            (2, 10, "10 MNQ"),
            (20, 1, "1 NQ"),
        ]
        print(f"\n  JadeCap Multi-Contract Backtest -- {ticker}")
        print(f"   {len(dates)} trading days: {dates[0]} -> {dates[-1]}")
        print()

        all_results = []
        for pv, ct, label in configs:
            print(f"\n  --- Running: {label} (${pv}/pt x {ct} contracts) ---")
            result = _run_backtest(ticker, dates, pv, ct, quiet=True)
            all_results.append(result)
            print(f"      P&L: ${result['total_pnl']:+,.0f} | "
                  f"WR: {result['win_rate']:.0f}% | "
                  f"PF: {result['profit_factor']:.2f} | "
                  f"MaxDD: ${result['max_drawdown']:,.0f}")

        _print_comparison(all_results)

        # Use first config's trades for memory saving
        trades_for_memory = all_results[0]["trades"]
        result_for_save = all_results[0]
    else:
        # Single config run
        point_value = args.point_value if args.point_value else POINT_VALUE
        contracts = args.contracts if args.contracts else FIXED_CONTRACTS

        print(f"\n  JadeCap Backtest -- {ticker}")
        print(f"   {len(dates)} trading days: {dates[0]} -> {dates[-1]}")
        print(f"   Point value: ${point_value} | Contracts: {contracts}")
        print()

        result_for_save = _run_backtest(ticker, dates, point_value, contracts)
        trades_for_memory = result_for_save["trades"]

        # Print summary
        r = result_for_save
        print(f"\n{'='*70}")
        print(f"  BACKTEST RESULTS -- {ticker} | {dates[0]} -> {dates[-1]}")
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

        # Model distribution
        from collections import Counter
        model_counts = Counter(t.get("model", "?") for t in trades_for_memory)
        model_wins = Counter(t.get("model", "?") for t in trades_for_memory if t["result"] == "WIN")
        print(f"\n  Entry Models:")
        for model, count in model_counts.most_common():
            w = model_wins.get(model, 0)
            wr = w / count * 100 if count > 0 else 0
            print(f"    {model:15s}: {count:3d} trades, {w:2d} wins ({wr:.0f}%)")
        print()

    # Save results JSON
    workspace = os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace")
    out_path = os.path.join(workspace, "backtest-results.json")
    with open(out_path, "w") as f:
        json.dump(result_for_save, f, indent=2, default=str)
    print(f"  Saved to: {out_path}")

    # Feature 3: Save to memory (if --save-memory)
    if args.save_memory and trades_for_memory:
        _save_trades_to_memory(trades_for_memory, ticker, dates)
```

- [ ] **2.6** Verify: Run comparison mode

```bash
cd /home/hoang/.openclaw/workspace
python3 -m openclaw.backtest --ticker NQ --days 20 --compare
# Expected: table with 3 columns (5 MNQ, 10 MNQ, 1 NQ)
```

---

## Feature 3: Feed Backtest Results into Agent Memory

### Problem

Backtest results are saved to JSON but never feed into the BM25 memory system. The trading agents cannot learn from historical backtest outcomes.

### Design

- Each trade becomes a `(situation, recommendation)` tuple
- Situation: structured description of market conditions + entry model
- Recommendation: outcome + lesson learned
- Stored under agent name `"backtest"` in the memories table
- Gated behind `--save-memory` CLI flag

### Steps

- [ ] **3.1** Add `_save_trades_to_memory()` function

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`
**Add before `_run_backtest()`**:

```python
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
```

- [ ] **3.2** Verify: Run with `--save-memory` and check SQLite

```bash
cd /home/hoang/.openclaw/workspace
python3 -m openclaw.backtest --ticker NQ --days 10 --save-memory

# Verify memories were saved
python3 -c "
import sqlite3
conn = sqlite3.connect('/home/hoang/.openclaw/workspace/trading.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(\"SELECT agent_name, situation, recommendation FROM memories WHERE agent_name = 'backtest' ORDER BY id DESC LIMIT 3\").fetchall()
for r in rows:
    print(f'Agent: {r[\"agent_name\"]}')
    print(f'Situation: {r[\"situation\"][:80]}...')
    print(f'Recommendation: {r[\"recommendation\"][:80]}...')
    print()
conn.close()
"
# Expected: 3 rows with agent_name='backtest', structured situation/recommendation text
```

- [ ] **3.3** Verify: Memories are retrievable via BM25

```bash
cd /home/hoang/.openclaw/workspace
python3 -c "
from openclaw.memory import FinancialSituationMemory
from openclaw.memory_persistence import hydrate_memories

mem = FinancialSituationMemory(name='backtest')
hydrate_memories({'backtest': mem}, '/home/hoang/.openclaw/workspace/trading.db')
results = mem.get_memories('NQ long SFP_RAID setup in AM Kill Zone', n_matches=3)
for r in results:
    print(f'Score: {r[\"similarity_score\"]:.2f}')
    print(f'Match: {r[\"matched_situation\"][:80]}...')
    print()
"
# Expected: relevant matches ranked by BM25 score
```

---

## Integration Test

- [ ] **4.1** Full end-to-end test

```bash
cd /home/hoang/.openclaw/workspace

# Test 1: Single run with 1H SFP
python3 -m openclaw.backtest --ticker NQ --days 20 2>&1 | tail -20

# Test 2: Comparison mode
python3 -m openclaw.backtest --ticker NQ --days 20 --compare

# Test 3: Memory integration
python3 -m openclaw.backtest --ticker NQ --days 10 --save-memory

# Test 4: Custom sizing
python3 -m openclaw.backtest --ticker NQ --days 10 --point-value 20 --contracts 1
```

- [ ] **4.2** Validate SFP_RAID now appears in model distribution

```bash
cd /home/hoang/.openclaw/workspace
python3 -m openclaw.backtest --ticker NQ --start 2025-04-03 --end 2026-04-02 2>&1 | grep "Entry Models" -A 10
# Expected: SFP_RAID line with > 0 trades
```

---

## Files Modified

| File | Changes |
|------|---------|
| `/home/hoang/.openclaw/workspace/openclaw/backtest.py` | Add `_detect_1h_sfp()`, modify `_find_entry_realtime()` for 1H SFP, add `_run_backtest()`, `_print_comparison()`, `_save_trades_to_memory()`, update `main()` with new CLI args |

## Files NOT Modified

| File | Reason |
|------|--------|
| `openclaw/memory.py` | API already supports `add_situations()` -- no changes needed |
| `openclaw/memory_persistence.py` | `persist_memories()` already handles arbitrary agent names -- no changes needed |
| `openclaw/database.py` | `memories` table schema already supports new `backtest` agent name |
| `openclaw/dataflows/databento_nq.py` | `get_databento_ohlcv()` already supports `1m` timeframe -- no changes needed |

## Risk Notes

- **1H SFP detection** adds a `_agg(data, 60)` call inside the walk-forward loop. This is O(n) per 5m candle. For a single KZ (~24 candles), this is ~24 aggregations. Acceptable for a backtester. If slow, cache the 1H aggregation and only recompute when a new 1H boundary is crossed.
- **Global mutation** in `_run_backtest()` (setting `POINT_VALUE` / `FIXED_CONTRACTS` globally) is safe because `main()` runs sequentially. The `try/finally` restores originals. Not thread-safe -- acceptable for CLI tool.
- **Memory deduplication** is handled by `persist_memories()` -- re-running the same backtest won't create duplicate rows.
