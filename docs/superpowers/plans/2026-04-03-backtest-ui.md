# Backtest UI — Implementation Plan

**Date:** 2026-04-03
**Goal:** Add backtest controls to the Trading tab — run backtests from the UI, display results with equity curve, entry model distribution, monthly P&L, and trade list.

---

## Files to Modify

| File | Change |
|------|--------|
| `/home/hoang/openclaw/src/gateway/server-methods/trading.ts` | Add `trading.backtest` and `trading.backtest.results` handlers |
| `/home/hoang/openclaw/ui/src/ui/controllers/trading.ts` | Add backtest types, controller functions |
| `/home/hoang/openclaw/ui/src/ui/views/trading.ts` | Add `TradingProps` fields, `renderBacktest()` section, equity curve SVG |
| `/home/hoang/.openclaw/workspace/openclaw/backtest.py` | Add `--progress-file` support for gateway progress streaming |

---

## Step 1: Add Progress File Support to backtest.py

- [ ] **1.1** Add `--progress-file` argument to `argparse` in `main()`
- [ ] **1.2** Write progress events as JSONL during the day loop
- [ ] **1.3** Write final results to stdout as JSON (last line) for gateway to capture

**File:** `/home/hoang/.openclaw/workspace/openclaw/backtest.py`

In `main()`, after the `argparse` block (line ~592-597), add `--progress-file`, `--point-value`, and `--contracts` arguments:

```python
    parser.add_argument("--progress-file", help="JSONL file for progress events")
    parser.add_argument("--point-value", type=int, default=None, help="Override POINT_VALUE")
    parser.add_argument("--contracts", type=int, default=None, help="Override FIXED_CONTRACTS")
```

After `args = parser.parse_args()` (line ~597), add overrides:

```python
    global POINT_VALUE, FIXED_CONTRACTS
    if args.point_value is not None:
        POINT_VALUE = args.point_value
    if args.contracts is not None:
        FIXED_CONTRACTS = args.contracts
```

Inside the `for date in dates:` loop (line ~635), after each day result, write progress to the progress file:

```python
        # Write progress event
        if args.progress_file:
            day_num = dates.index(date) + 1
            evt = {
                "event": "day_progress",
                "day": day_num,
                "total_days": len(dates),
                "date": date,
                "status": result["status"],
                "has_trade": trade is not None,
                "cumulative_pnl": total_pnl,
            }
            with open(args.progress_file, "a") as pf:
                pf.write(json.dumps(evt) + "\n")
```

After the summary section (line ~731), before `# Save`, write the final result to stdout as JSON:

```python
    # Monthly P&L breakdown
    monthly_pnl = {}
    for t in trades:
        # entry_time format: "2025-04-08 10:45:00-04:00"
        month_key = t["entry_time"][:7]  # "2025-04"
        monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + t["pnl"]

    # Entry model distribution
    from collections import Counter
    model_counts = Counter(t.get("model", "?") for t in trades)
    model_wins = Counter(t.get("model", "?") for t in trades if t["result"] == "WIN")
    model_losses = Counter(t.get("model", "?") for t in trades if t["result"] == "LOSS")
    model_pnl = {}
    for t in trades:
        m = t.get("model", "?")
        model_pnl[m] = model_pnl.get(m, 0) + t["pnl"]
    model_dist = []
    for model, count in model_counts.most_common():
        w = model_wins.get(model, 0)
        l = model_losses.get(model, 0)
        wr = w / count * 100 if count > 0 else 0
        model_dist.append({
            "model": model, "trades": count, "wins": w, "losses": l,
            "win_rate": round(wr, 1), "pnl": round(model_pnl.get(model, 0), 2),
        })
```

Then modify the JSON dump at line ~737 to include the new fields:

```python
    results_json = {
        "ticker": ticker,
        "period": f"{dates[0]} to {dates[-1]}",
        "start_date": dates[0],
        "end_date": dates[-1],
        "days_scanned": len(dates),
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "closes": closes,
        "win_rate": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_dd, 2),
        "equity_curve": [round(e, 2) for e in equity_curve],
        "monthly_pnl": monthly_pnl,
        "model_distribution": model_dist,
        "point_value": POINT_VALUE,
        "contracts": FIXED_CONTRACTS,
        "trades": [{k: v for k, v in t.items() if k != "_df"} for t in trades],
    }

    # Write to file
    with open(out_path, "w") as f:
        json.dump(results_json, f, indent=2, default=str)

    # Write final JSON to stdout for gateway to capture
    print(json.dumps(results_json, default=str))
```

---

## Step 2: Add Gateway Handlers

- [ ] **2.1** Add `trading.backtest` handler (spawns subprocess, streams progress)
- [ ] **2.2** Add `trading.backtest.results` handler (reads JSON file)

**File:** `/home/hoang/openclaw/src/gateway/server-methods/trading.ts`

### 2.1 — Tracking map (add near line 10, alongside `runningRuns`)

```typescript
const runningBacktests = new Map<
  string,
  { proc: ChildProcess; progressFile: string; startedAt: number }
>();
```

### 2.2 — `trading.backtest` handler (add inside `tradingHandlers` object, after `trading.run.reflect`)

```typescript
  "trading.backtest": async ({ params, respond, context }) => {
    try {
      const p = params as {
        ticker?: string;
        start?: string;
        end?: string;
        pointValue?: number;
        contracts?: number;
      };
      const ticker = (p.ticker ?? "NQ").toUpperCase().trim();
      const start = p.start ?? "";
      const end = p.end ?? "";
      const pointValue = p.pointValue ?? 2;
      const contracts = p.contracts ?? 5;

      if (!start || !end) {
        respond(false, undefined, errorShape(ErrorCodes.INVALID_REQUEST, "start and end dates are required"));
        return;
      }

      // Only one backtest at a time
      if (runningBacktests.size > 0) {
        respond(false, undefined, errorShape(ErrorCodes.INVALID_REQUEST, "A backtest is already running"));
        return;
      }

      const backtestId = "bt-" + Math.random().toString(36).slice(2, 10);
      const progressFile = path.join(os.tmpdir(), `backtest-${backtestId}.jsonl`);

      const proc = spawn("python3", [
        "-m", "openclaw.backtest",
        "--ticker", ticker,
        "--start", start,
        "--end", end,
        "--point-value", String(pointValue),
        "--contracts", String(contracts),
        "--progress-file", progressFile,
      ], {
        cwd: WORKSPACE,
        env: { ...process.env, PYTHONPATH: WORKSPACE, OPENCLAW_WORKSPACE: WORKSPACE },
        stdio: ["ignore", "pipe", "pipe"],
      });

      runningBacktests.set(backtestId, { proc, progressFile, startedAt: Date.now() });

      let lastReadPos = 0;
      const pollInterval = setInterval(() => {
        try {
          if (!fs.existsSync(progressFile)) return;
          const content = fs.readFileSync(progressFile, "utf8");
          const newContent = content.slice(lastReadPos);
          lastReadPos = content.length;
          if (!newContent.trim()) return;
          for (const line of newContent.trim().split("\n")) {
            try {
              const evt = JSON.parse(line);
              context.broadcast("trading.backtest.progress", { backtestId, ...evt });
            } catch { /* skip malformed lines */ }
          }
        } catch { /* file may not exist yet */ }
      }, 1000);

      let stdout = "";
      let stderr = "";
      proc.stdout?.on("data", (d: Buffer) => { stdout += d.toString(); });
      proc.stderr?.on("data", (d: Buffer) => { stderr += d.toString(); });

      proc.on("close", (code) => {
        clearInterval(pollInterval);
        runningBacktests.delete(backtestId);
        try { fs.unlinkSync(progressFile); } catch { /* ok */ }

        if (code === 0) {
          context.broadcast("trading.backtest.progress", {
            backtestId, event: "done",
          });
        } else {
          context.broadcast("trading.backtest.progress", {
            backtestId, event: "failed", error: stderr.slice(0, 500),
          });
        }
      });

      respond(true, { backtestId, ticker, start, end, status: "started" });
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    }
  },

  "trading.backtest.cancel": async ({ params, respond }) => {
    try {
      const p = params as { backtestId: string };
      const entry = runningBacktests.get(p.backtestId);
      if (!entry) {
        respond(false, undefined, errorShape(ErrorCodes.INVALID_REQUEST, "Backtest not found or already finished"));
        return;
      }
      entry.proc.kill("SIGTERM");
      runningBacktests.delete(p.backtestId);
      try { fs.unlinkSync(entry.progressFile); } catch { /* ok */ }
      respond(true, { ok: true });
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    }
  },

  "trading.backtest.results": async ({ respond }) => {
    try {
      const resultsPath = path.join(WORKSPACE, "backtest-results.json");
      if (!fs.existsSync(resultsPath)) {
        respond(true, null);
        return;
      }
      const raw = fs.readFileSync(resultsPath, "utf8");
      const results = JSON.parse(raw);
      respond(true, results);
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    }
  },
```

---

## Step 3: Add Controller Functions

- [ ] **3.1** Add `BacktestResults` interface
- [ ] **3.2** Add `startBacktest()`, `cancelBacktest()`, `loadBacktestResults()` functions

**File:** `/home/hoang/openclaw/ui/src/ui/controllers/trading.ts`

Add at the end of the file, before the closing (after `reflectRun` function at line ~254):

```typescript
// --- Backtest ---

export interface BacktestTrade {
  direction: string;
  entry: number;
  stop: number;
  target: number;
  risk_pts: number;
  contracts: number;
  score: number;
  model: string;
  entry_time: string;
  result: string;
  exit: number;
  exit_time: string;
  pnl: number;
  kz: string;
}

export interface BacktestModelDist {
  model: string;
  trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  pnl: number;
}

export interface BacktestResults {
  ticker: string;
  period: string;
  start_date: string;
  end_date: string;
  days_scanned: number;
  total_trades: number;
  wins: number;
  losses: number;
  closes: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  total_pnl: number;
  max_drawdown: number;
  equity_curve: number[];
  monthly_pnl: Record<string, number>;
  model_distribution: BacktestModelDist[];
  point_value: number;
  contracts: number;
  trades: BacktestTrade[];
}

export async function startBacktest(
  client: GatewayBrowserClient,
  ticker: string,
  start: string,
  end: string,
  pointValue: number,
  contracts: number,
): Promise<{ backtestId: string }> {
  return await client.request("trading.backtest", { ticker, start, end, pointValue, contracts });
}

export async function cancelBacktest(
  client: GatewayBrowserClient,
  backtestId: string,
): Promise<void> {
  await client.request("trading.backtest.cancel", { backtestId });
}

export async function loadBacktestResults(
  client: GatewayBrowserClient,
): Promise<BacktestResults | null> {
  try {
    return await client.request<BacktestResults>("trading.backtest.results", {});
  } catch {
    return null;
  }
}
```

---

## Step 4: Add Backtest Props to TradingProps

- [ ] **4.1** Extend `TradingProps` with backtest fields

**File:** `/home/hoang/openclaw/ui/src/ui/views/trading.ts`

Add these fields inside the `TradingProps` type (after the `onSetApiKey` line, before the closing `}`):

```typescript
  // Backtest
  backtestTicker: string;
  backtestStart: string;
  backtestEnd: string;
  backtestPointValue: number;
  backtestContracts: number;
  backtestRunning: boolean;
  backtestProgress: { day: number; total_days: number; date: string; cumulative_pnl: number } | null;
  backtestResults: import("../controllers/trading.ts").BacktestResults | null;
  onBacktestTickerChange: (value: string) => void;
  onBacktestStartChange: (value: string) => void;
  onBacktestEndChange: (value: string) => void;
  onBacktestPointValueChange: (value: number) => void;
  onBacktestContractsChange: (value: number) => void;
  onStartBacktest: () => void;
  onCancelBacktest: () => void;
  onLoadBacktestResults: () => void;
```

---

## Step 5: Add Backtest UI Render Functions

- [ ] **5.1** Add `renderEquityCurve()` — SVG line chart
- [ ] **5.2** Add `renderBacktestResults()` — stats, model dist, monthly P&L, trades
- [ ] **5.3** Add `renderBacktest()` — form + results container
- [ ] **5.4** Wire into `renderTrading()`

**File:** `/home/hoang/openclaw/ui/src/ui/views/trading.ts`

### 5.1 — Equity Curve SVG (add before `renderTrading`)

```typescript
function renderEquityCurve(equityCurve: number[], maxDrawdown: number) {
  if (!equityCurve || equityCurve.length < 2) return nothing;

  const W = 700;
  const H = 200;
  const PAD = 40;
  const plotW = W - PAD * 2;
  const plotH = H - PAD * 2;

  const minVal = Math.min(0, ...equityCurve);
  const maxVal = Math.max(0, ...equityCurve);
  const range = maxVal - minVal || 1;

  const xStep = plotW / (equityCurve.length - 1);

  // Build path + split into green/red segments
  const points = equityCurve.map((v, i) => ({
    x: PAD + i * xStep,
    y: PAD + plotH - ((v - minVal) / range) * plotH,
  }));

  const zeroY = PAD + plotH - ((0 - minVal) / range) * plotH;

  // Build SVG path
  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");

  // Area fill above zero (green) and below zero (red)
  const areaAbove = `${pathD} L ${points[points.length - 1].x.toFixed(1)} ${zeroY.toFixed(1)} L ${points[0].x.toFixed(1)} ${zeroY.toFixed(1)} Z`;

  // Find max drawdown region
  let peak = 0;
  let ddStart = 0;
  let ddEnd = 0;
  let maxDd = 0;
  let currentDdStart = 0;
  for (let i = 0; i < equityCurve.length; i++) {
    if (equityCurve[i] > peak) {
      peak = equityCurve[i];
      currentDdStart = i;
    }
    const dd = peak - equityCurve[i];
    if (dd > maxDd) {
      maxDd = dd;
      ddStart = currentDdStart;
      ddEnd = i;
    }
  }

  // Y-axis labels
  const yLabels = [maxVal, maxVal * 0.5, 0, minVal * 0.5, minVal].filter(
    (v, i, arr) => arr.indexOf(v) === i,
  );

  return html`
    <div style="margin-top:12px;overflow-x:auto;">
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;max-width:${W}px;height:auto;background:var(--claw-surface-2, #1a1a2e);border-radius:6px;">
        <!-- Zero line -->
        <line x1="${PAD}" y1="${zeroY.toFixed(1)}" x2="${W - PAD}" y2="${zeroY.toFixed(1)}"
          stroke="var(--claw-border)" stroke-width="1" stroke-dasharray="4,4" />

        <!-- Max drawdown region highlight -->
        ${maxDd > 0 ? html`
          <rect x="${points[ddStart].x.toFixed(1)}" y="${Math.min(points[ddStart].y, points[ddEnd].y).toFixed(1)}"
            width="${(points[ddEnd].x - points[ddStart].x).toFixed(1)}"
            height="${Math.abs(points[ddEnd].y - points[ddStart].y).toFixed(1)}"
            fill="var(--claw-red)" opacity="0.1" rx="2" />
        ` : nothing}

        <!-- Green area (above zero) -->
        <clipPath id="above-zero"><rect x="${PAD}" y="0" width="${plotW}" height="${zeroY.toFixed(1)}" /></clipPath>
        <path d="${areaAbove}" fill="var(--claw-green)" opacity="0.15" clip-path="url(#above-zero)" />

        <!-- Red area (below zero) -->
        <clipPath id="below-zero"><rect x="${PAD}" y="${zeroY.toFixed(1)}" width="${plotW}" height="${H}" /></clipPath>
        <path d="${areaAbove}" fill="var(--claw-red)" opacity="0.15" clip-path="url(#below-zero)" />

        <!-- Equity line -->
        <path d="${pathD}" fill="none" stroke="var(--claw-accent)" stroke-width="1.5" />

        <!-- Y-axis labels -->
        ${yLabels.map((v) => {
          const y = PAD + plotH - ((v - minVal) / range) * plotH;
          return html`
            <text x="${PAD - 4}" y="${y.toFixed(1)}" text-anchor="end" font-size="9"
              fill="var(--claw-text-secondary)" dominant-baseline="middle">
              $${v >= 0 ? "+" : ""}${v.toFixed(0)}
            </text>
          `;
        })}

        <!-- X-axis label -->
        <text x="${W / 2}" y="${H - 4}" text-anchor="middle" font-size="9" fill="var(--claw-text-secondary)">
          Trade #
        </text>
      </svg>
    </div>
  `;
}
```

### 5.2 — Backtest Results Display

```typescript
function renderBacktestResults(props: TradingProps) {
  const r = props.backtestResults;
  if (!r) return nothing;

  const trades = r.trades ?? [];
  const last20 = trades.slice(-20).reverse();

  return html`
    <div style="margin-top:16px;">
      <!-- Summary Stats -->
      <div style="font-weight:600;color:var(--claw-text);margin-bottom:10px;">
        ${r.ticker} | ${r.period}
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;font-size:13px;margin-bottom:16px;">
        ${[
          { label: "Total P&L", value: `$${r.total_pnl >= 0 ? "+" : ""}${r.total_pnl.toFixed(0)}`, color: r.total_pnl >= 0 ? "var(--claw-green)" : "var(--claw-red)" },
          { label: "Win Rate", value: `${r.win_rate.toFixed(1)}%`, color: r.win_rate >= 50 ? "var(--claw-green)" : "var(--claw-text)" },
          { label: "Profit Factor", value: r.profit_factor.toFixed(2), color: r.profit_factor >= 1.5 ? "var(--claw-green)" : r.profit_factor >= 1 ? "var(--claw-text)" : "var(--claw-red)" },
          { label: "Max Drawdown", value: `$${r.max_drawdown.toFixed(0)}`, color: "var(--claw-red)" },
          { label: "Trades", value: `${r.total_trades}`, color: "var(--claw-text)" },
          { label: "Wins / Losses", value: `${r.wins} / ${r.losses}`, color: "var(--claw-text)" },
          { label: "Avg Win", value: `$${r.avg_win >= 0 ? "+" : ""}${r.avg_win.toFixed(0)}`, color: "var(--claw-green)" },
          { label: "Avg Loss", value: `$${r.avg_loss.toFixed(0)}`, color: "var(--claw-red)" },
        ].map((s) => html`
          <div style="border:1px solid var(--claw-border);border-radius:6px;padding:10px;">
            <div style="font-size:11px;color:var(--claw-text-secondary);">${s.label}</div>
            <div style="font-weight:600;color:${s.color};font-size:15px;">${s.value}</div>
          </div>
        `)}
      </div>

      <!-- Equity Curve -->
      <div style="font-weight:600;color:var(--claw-text);margin-bottom:8px;font-size:13px;">Equity Curve</div>
      ${renderEquityCurve(r.equity_curve, r.max_drawdown)}

      <!-- Entry Model Distribution -->
      ${r.model_distribution && r.model_distribution.length > 0 ? html`
        <div style="margin-top:16px;">
          <div style="font-weight:600;color:var(--claw-text);margin-bottom:8px;font-size:13px;">Entry Models</div>
          <table style="width:100%;border-collapse:collapse;font-size:12px;color:var(--claw-text);">
            <thead><tr style="border-bottom:1px solid var(--claw-border);">
              <th style="text-align:left;padding:4px 8px;color:var(--claw-text-secondary);">Model</th>
              <th style="text-align:right;padding:4px 8px;color:var(--claw-text-secondary);">Trades</th>
              <th style="text-align:right;padding:4px 8px;color:var(--claw-text-secondary);">Wins</th>
              <th style="text-align:right;padding:4px 8px;color:var(--claw-text-secondary);">Win Rate</th>
              <th style="text-align:right;padding:4px 8px;color:var(--claw-text-secondary);">P&L</th>
            </tr></thead>
            <tbody>
              ${r.model_distribution.map((m) => html`
                <tr style="border-bottom:1px solid var(--claw-border);">
                  <td style="padding:5px 8px;font-weight:600;">${m.model}</td>
                  <td style="padding:5px 8px;text-align:right;">${m.trades}</td>
                  <td style="padding:5px 8px;text-align:right;">${m.wins}</td>
                  <td style="padding:5px 8px;text-align:right;">${m.win_rate.toFixed(1)}%</td>
                  <td style="padding:5px 8px;text-align:right;color:${m.pnl >= 0 ? "var(--claw-green)" : "var(--claw-red)"};">
                    $${m.pnl >= 0 ? "+" : ""}${m.pnl.toFixed(0)}
                  </td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      ` : nothing}

      <!-- Monthly P&L -->
      ${r.monthly_pnl && Object.keys(r.monthly_pnl).length > 0 ? html`
        <div style="margin-top:16px;">
          <div style="font-weight:600;color:var(--claw-text);margin-bottom:8px;font-size:13px;">Monthly P&L</div>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:6px;">
            ${Object.entries(r.monthly_pnl).sort(([a], [b]) => a.localeCompare(b)).map(([month, pnl]) => html`
              <div style="border:1px solid var(--claw-border);border-radius:6px;padding:8px;text-align:center;">
                <div style="font-size:10px;color:var(--claw-text-secondary);">${month}</div>
                <div style="font-weight:600;font-size:13px;color:${pnl >= 0 ? "var(--claw-green)" : "var(--claw-red)"};">
                  $${pnl >= 0 ? "+" : ""}${pnl.toFixed(0)}
                </div>
              </div>
            `)}
          </div>
        </div>
      ` : nothing}

      <!-- Last 20 Trades -->
      <div style="margin-top:16px;">
        <div style="font-weight:600;color:var(--claw-text);margin-bottom:8px;font-size:13px;">Last 20 Trades</div>
        <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;font-size:11px;color:var(--claw-text);min-width:600px;">
            <thead><tr style="border-bottom:1px solid var(--claw-border);">
              <th style="text-align:left;padding:4px 6px;color:var(--claw-text-secondary);">Date</th>
              <th style="text-align:left;padding:4px 6px;color:var(--claw-text-secondary);">Dir</th>
              <th style="text-align:left;padding:4px 6px;color:var(--claw-text-secondary);">KZ</th>
              <th style="text-align:left;padding:4px 6px;color:var(--claw-text-secondary);">Model</th>
              <th style="text-align:right;padding:4px 6px;color:var(--claw-text-secondary);">Entry</th>
              <th style="text-align:right;padding:4px 6px;color:var(--claw-text-secondary);">Exit</th>
              <th style="text-align:left;padding:4px 6px;color:var(--claw-text-secondary);">Result</th>
              <th style="text-align:right;padding:4px 6px;color:var(--claw-text-secondary);">P&L</th>
            </tr></thead>
            <tbody>
              ${last20.map((t) => html`
                <tr style="border-bottom:1px solid var(--claw-border);">
                  <td style="padding:4px 6px;">${t.entry_time.slice(0, 10)}</td>
                  <td style="padding:4px 6px;color:${t.direction === "long" ? "var(--claw-green)" : "var(--claw-red)"};">${t.direction}</td>
                  <td style="padding:4px 6px;">${t.kz}</td>
                  <td style="padding:4px 6px;font-weight:600;">${t.model}</td>
                  <td style="padding:4px 6px;text-align:right;">${t.entry.toFixed(0)}</td>
                  <td style="padding:4px 6px;text-align:right;">${t.exit.toFixed(0)}</td>
                  <td style="padding:4px 6px;color:${t.result === "WIN" ? "var(--claw-green)" : t.result === "LOSS" ? "var(--claw-red)" : "var(--claw-text-secondary)"};">
                    ${t.result}
                  </td>
                  <td style="padding:4px 6px;text-align:right;color:${t.pnl >= 0 ? "var(--claw-green)" : "var(--claw-red)"};">
                    $${t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(0)}
                  </td>
                </tr>
              `)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}
```

### 5.3 — Main Backtest Section (form + results)

```typescript
function renderBacktest(props: TradingProps) {
  const today = new Date().toISOString().slice(0, 10);
  const thirtyDaysAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);

  return html`
    <section style="${sectionStyle}">
      <div style="font-weight:600;color:var(--claw-text);margin-bottom:12px;">Backtest</div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px;">
        <input type="text" .value=${props.backtestTicker} placeholder="Ticker"
          ?disabled=${props.backtestRunning}
          @input=${(e: Event) => props.onBacktestTickerChange((e.target as HTMLInputElement).value)}
          style="${inputStyle}max-width:90px;text-transform:uppercase;" />

        <input type="date" .value=${props.backtestStart || thirtyDaysAgo}
          ?disabled=${props.backtestRunning}
          @input=${(e: Event) => props.onBacktestStartChange((e.target as HTMLInputElement).value)}
          style="${inputStyle}max-width:155px;" />

        <span style="color:var(--claw-text-secondary);font-size:12px;">to</span>

        <input type="date" .value=${props.backtestEnd || today}
          ?disabled=${props.backtestRunning}
          @input=${(e: Event) => props.onBacktestEndChange((e.target as HTMLInputElement).value)}
          style="${inputStyle}max-width:155px;" />

        <div style="display:flex;align-items:center;gap:4px;">
          <span style="color:var(--claw-text-secondary);font-size:11px;">Pt$</span>
          <input type="number" .value=${String(props.backtestPointValue)} min="1"
            ?disabled=${props.backtestRunning}
            @change=${(e: Event) => props.onBacktestPointValueChange(Number((e.target as HTMLInputElement).value))}
            style="${inputStyle}max-width:60px;" />
        </div>

        <div style="display:flex;align-items:center;gap:4px;">
          <span style="color:var(--claw-text-secondary);font-size:11px;">Cts</span>
          <input type="number" .value=${String(props.backtestContracts)} min="1"
            ?disabled=${props.backtestRunning}
            @change=${(e: Event) => props.onBacktestContractsChange(Number((e.target as HTMLInputElement).value))}
            style="${inputStyle}max-width:60px;" />
        </div>

        ${props.backtestRunning
          ? html`<button @click=${props.onCancelBacktest}
              style="padding:6px 14px;border:none;background:var(--claw-red);color:#fff;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">Cancel</button>`
          : html`<button @click=${props.onStartBacktest}
              style="padding:6px 14px;border:none;background:var(--claw-accent);color:#fff;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;">Run Backtest</button>`
        }

        ${!props.backtestRunning && !props.backtestResults ? html`
          <button @click=${props.onLoadBacktestResults} style="${btnStyle}">Load Last</button>
        ` : nothing}
      </div>

      ${props.backtestRunning && props.backtestProgress ? html`
        <div style="display:flex;align-items:center;gap:12px;padding:10px;border:1px solid var(--claw-border);border-radius:6px;margin-bottom:12px;">
          <div style="flex:1;">
            <div style="height:6px;background:var(--claw-border);border-radius:3px;overflow:hidden;">
              <div style="height:100%;background:var(--claw-accent);border-radius:3px;width:${((props.backtestProgress.day / props.backtestProgress.total_days) * 100).toFixed(1)}%;transition:width 0.3s;"></div>
            </div>
          </div>
          <div style="font-size:12px;color:var(--claw-text-secondary);white-space:nowrap;">
            Day ${props.backtestProgress.day}/${props.backtestProgress.total_days}
            (${props.backtestProgress.date})
            — P&L: <span style="color:${props.backtestProgress.cumulative_pnl >= 0 ? "var(--claw-green)" : "var(--claw-red)"};">
              $${props.backtestProgress.cumulative_pnl >= 0 ? "+" : ""}${props.backtestProgress.cumulative_pnl.toFixed(0)}
            </span>
          </div>
        </div>
      ` : nothing}

      ${props.backtestRunning && !props.backtestProgress ? html`
        <div style="color:var(--claw-text-secondary);font-size:12px;">Starting backtest...</div>
      ` : nothing}

      ${renderBacktestResults(props)}
    </section>
  `;
}
```

### 5.4 — Wire into `renderTrading()`

In the `renderTrading()` function (line ~897), add `${renderBacktest(props)}` after `${renderRunForm(props)}`:

```diff
  return html`
    <div style="padding:24px;max-width:1100px;">
      ${renderHaltSwitch(props)}
      ${renderRunForm(props)}
+     ${renderBacktest(props)}
      ${renderBiasConfluence(props)}
      ${renderLastRun(props)}
```

---

## Step 6: Wire Props in the Parent Component

- [ ] **6.1** Find the component that creates `TradingProps` and add backtest state + handlers

The parent component that creates `TradingProps` needs to be updated to manage backtest state. Find it by searching for `onStartRun` or `renderTrading`:

```bash
grep -rn "onStartRun\|renderTrading" /home/hoang/openclaw/ui/src/ui/ --include="*.ts" | grep -v views/trading
```

In that parent component, add:

**State variables:**

```typescript
private _backtestTicker = "NQ";
private _backtestStart = "";
private _backtestEnd = "";
private _backtestPointValue = 2;
private _backtestContracts = 5;
private _backtestRunning = false;
private _backtestId: string | null = null;
private _backtestProgress: { day: number; total_days: number; date: string; cumulative_pnl: number } | null = null;
private _backtestResults: BacktestResults | null = null;
```

**Props wiring (in the object passed to `renderTrading()`):**

```typescript
backtestTicker: this._backtestTicker,
backtestStart: this._backtestStart,
backtestEnd: this._backtestEnd,
backtestPointValue: this._backtestPointValue,
backtestContracts: this._backtestContracts,
backtestRunning: this._backtestRunning,
backtestProgress: this._backtestProgress,
backtestResults: this._backtestResults,
onBacktestTickerChange: (v: string) => { this._backtestTicker = v; this.requestUpdate(); },
onBacktestStartChange: (v: string) => { this._backtestStart = v; this.requestUpdate(); },
onBacktestEndChange: (v: string) => { this._backtestEnd = v; this.requestUpdate(); },
onBacktestPointValueChange: (v: number) => { this._backtestPointValue = v; this.requestUpdate(); },
onBacktestContractsChange: (v: number) => { this._backtestContracts = v; this.requestUpdate(); },
onStartBacktest: async () => {
  try {
    const result = await startBacktest(
      this._client, this._backtestTicker, this._backtestStart, this._backtestEnd,
      this._backtestPointValue, this._backtestContracts,
    );
    this._backtestId = result.backtestId;
    this._backtestRunning = true;
    this._backtestProgress = null;
    this._backtestResults = null;
    this.requestUpdate();
  } catch (e) {
    console.error("Backtest start failed:", e);
  }
},
onCancelBacktest: async () => {
  if (this._backtestId) {
    await cancelBacktest(this._client, this._backtestId);
  }
  this._backtestRunning = false;
  this._backtestId = null;
  this._backtestProgress = null;
  this.requestUpdate();
},
onLoadBacktestResults: async () => {
  const results = await loadBacktestResults(this._client);
  this._backtestResults = results;
  this.requestUpdate();
},
```

**Broadcast listener (alongside existing `trading.progress` listener):**

```typescript
this._client.on("trading.backtest.progress", (data: Record<string, unknown>) => {
  if (data.event === "done") {
    this._backtestRunning = false;
    this._backtestId = null;
    this._backtestProgress = null;
    // Auto-load results
    loadBacktestResults(this._client).then((r) => {
      this._backtestResults = r;
      this.requestUpdate();
    });
  } else if (data.event === "failed") {
    this._backtestRunning = false;
    this._backtestId = null;
    this._backtestProgress = null;
    console.error("Backtest failed:", data.error);
  } else if (data.event === "day_progress") {
    this._backtestProgress = {
      day: data.day as number,
      total_days: data.total_days as number,
      date: data.date as string,
      cumulative_pnl: data.cumulative_pnl as number,
    };
  }
  this.requestUpdate();
});
```

---

## Step 7: Build and Test

- [ ] **7.1** Build and restart

```bash
cd /home/hoang/openclaw && pnpm build && pnpm ui:build && systemctl --user restart openclaw-gateway
```

- [ ] **7.2** Verify gateway starts without errors

```bash
journalctl --user -u openclaw-gateway -n 50 --no-pager
```

- [ ] **7.3** Test `trading.backtest.results` returns existing data

Open UI, go to Trading tab, click "Load Last" to verify existing `backtest-results.json` loads and displays.

- [ ] **7.4** Test backtest run (short range)

Set ticker=NQ, start=2026-03-25, end=2026-03-28 (3 days). Click "Run Backtest". Verify:
- Progress bar updates
- Results appear when done
- Equity curve renders
- Model distribution table shows
- Monthly P&L shows
- Last 20 trades list shows

- [ ] **7.5** Test cancel

Start a longer backtest, click Cancel, verify it stops cleanly.

---

## Summary

| Feature | Handler | UI Function |
|---------|---------|-------------|
| Run backtest | `trading.backtest` | `renderBacktest()` form + progress bar |
| Cancel backtest | `trading.backtest.cancel` | Cancel button |
| Load results | `trading.backtest.results` | `renderBacktestResults()` |
| Equity curve | — | `renderEquityCurve()` SVG |
| Model distribution | — | Table in `renderBacktestResults()` |
| Monthly P&L | — | Grid in `renderBacktestResults()` |
| Trade list | — | Table (last 20) in `renderBacktestResults()` |

**Total files modified:** 4
**New files:** 0
**Estimated time:** 45-60 minutes
