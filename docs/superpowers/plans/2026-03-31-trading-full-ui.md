# Trading Full UI — Complete Feature Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Trading tab in OpenClaw Control UI fully functional — run analysis, monitor live agent progress, view run history and details, reflect on outcomes, auto-update bias from reports. All on port 18789.

**Architecture:** Gateway spawns Python subprocess for RunEngine. Subprocess writes progress to a JSON lines file that the gateway polls and broadcasts via WebSocket. UI subscribes to `trading.progress` events. After a run completes, bias auto-updates from the final signal.

**Tech Stack:** TypeScript (gateway handlers + Lit UI), Python (RunEngine subprocess), better-sqlite3 (DB reads), child_process.spawn (Python bridge)

---

## File Structure

```
Modified files:
├── /home/hoang/openclaw/src/gateway/server-methods/trading.ts    ← add 7 new handlers
├── /home/hoang/openclaw/src/gateway/method-scopes.ts             ← register new methods
├── /home/hoang/openclaw/ui/src/ui/views/trading.ts               ← add 4 new panels
├── /home/hoang/openclaw/ui/src/ui/controllers/trading.ts         ← add 7 new functions + types
├── /home/hoang/openclaw/ui/src/ui/app.ts                         ← add state fields
├── /home/hoang/openclaw/ui/src/ui/app-render.ts                  ← wire new callbacks
├── /home/hoang/.openclaw/workspace/openclaw/engine.py            ← add auto-bias update

New files:
├── /home/hoang/.openclaw/workspace/openclaw/run_bridge.py        ← subprocess entry point
```

### Architecture: Python Bridge

The gateway is Node.js. The RunEngine is Python. The bridge works like this:

1. `trading.run` handler spawns: `python3 -m openclaw.run_bridge --ticker NVDA --date 2026-03-31 --progress-file /tmp/trading-run-<id>.jsonl`
2. `run_bridge.py` creates a `JsonLinesCallback` that writes one JSON line per event to the progress file
3. The gateway polls the progress file every 500ms and broadcasts `trading.progress` events to all connected UI clients
4. When the subprocess exits, the gateway reads the final status and responds

Progress file format (one JSON object per line):
```json
{"event": "agent_status", "agent": "market-analyst", "status": "running", "ts": "..."}
{"event": "agent_status", "agent": "market-analyst", "status": "completed", "ts": "..."}
{"event": "report", "name": "market_report", "length": 4523, "ts": "..."}
{"event": "signal", "signal": "BUY", "ts": "..."}
{"event": "complete", "run_id": "abc123", "signal": "BUY", "duration": 142.3, "ts": "..."}
{"event": "error", "message": "Timeout on news-analyst", "ts": "..."}
```

### Bias Auto-Update

After a run completes with a signal, the engine updates `trading-config.json`:
- BUY/OVERWEIGHT → `bias.direction = "bullish"`
- SELL/UNDERWEIGHT → `bias.direction = "bearish"`
- HOLD → `bias.direction = "neutral"`
- `bias.reason` = "Auto-set from {ticker} analysis on {date}: {signal}"
- `bias.confidence` = "high" (for BUY/SELL), "medium" (for OVERWEIGHT/UNDERWEIGHT), "low" (for HOLD)

The UI already reads bias from config, so it auto-reflects.

---

## Phase A: Run Bridge + Backend (Tasks 1-4)

### Task 1: Create run_bridge.py subprocess entry point

**Files:**
- Create: `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py`

- [ ] **Step 1: Create the JsonLinesCallback class**

```python
"""Subprocess entry point for running trading analysis from the gateway.

Usage:
    python3 -m openclaw.run_bridge --ticker NVDA --date 2026-03-31 --progress-file /tmp/run-abc.jsonl

Writes JSON-lines progress events to the progress file.
Exits with code 0 on success, 1 on failure.
Final line is always {"event": "complete", ...} or {"event": "error", ...}.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


class JsonLinesCallback:
    """RunCallback that writes JSON lines to a file for the gateway to poll."""

    def __init__(self, progress_path: str):
        self.progress_path = progress_path
        self._f = open(progress_path, "a")

    def _write(self, obj: dict):
        obj["ts"] = datetime.now(timezone.utc).isoformat()
        self._f.write(json.dumps(obj) + "\n")
        self._f.flush()

    def on_run_start(self, ticker, date):
        self._write({"event": "run_start", "ticker": ticker, "date": date})

    def on_agent_status(self, agent, status):
        self._write({"event": "agent_status", "agent": agent, "status": status})

    def on_report_section(self, name, content):
        self._write({"event": "report", "name": name, "length": len(content)})

    def on_debate_turn(self, speaker, argument):
        self._write({"event": "debate", "speaker": speaker, "length": len(argument)})

    def on_signal(self, signal):
        self._write({"event": "signal", "signal": signal})

    def on_run_complete(self, result):
        self._write({
            "event": "complete",
            "run_id": result.run_id,
            "signal": result.signal,
            "duration": result.duration_seconds,
        })
        self._f.close()

    def on_error(self, error):
        self._write({"event": "error", "message": str(error)})
        self._f.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--progress-file", required=True)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    config_path = args.config or os.path.join(
        os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace"),
        "trading-config.json",
    )

    from openclaw.engine import RunEngine
    from openclaw.callbacks import PrintCallback

    engine = RunEngine(config_path)
    jl_cb = JsonLinesCallback(args.progress_file)
    print_cb = PrintCallback()

    try:
        result = engine.run(
            ticker=args.ticker,
            date=args.date,
            callbacks=[jl_cb, print_cb],
        )
        print(json.dumps({
            "ok": True,
            "run_id": result.run_id,
            "signal": result.signal,
            "duration": result.duration_seconds,
        }))
    except Exception as exc:
        jl_cb.on_error(exc)
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test that it imports without error**

Run: `cd /home/hoang/.openclaw/workspace && python3 -c "from openclaw.run_bridge import JsonLinesCallback; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/.openclaw/workspace
git add openclaw/run_bridge.py
git commit -m "feat: add run_bridge.py subprocess entry point for gateway"
```

---

### Task 2: Add auto-bias update to RunEngine

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/engine.py` (after signal extraction, ~line 163)

- [ ] **Step 1: Add _update_bias_from_signal method to RunEngine**

Add this method to the `RunEngine` class (after `_extract_signal`):

```python
def _update_bias_from_signal(self, signal: str, ticker: str, date: str) -> None:
    """Auto-update bias in config based on the final analysis signal."""
    signal_to_bias = {
        "BUY": ("bullish", "high"),
        "OVERWEIGHT": ("bullish", "medium"),
        "HOLD": ("neutral", "low"),
        "UNDERWEIGHT": ("bearish", "medium"),
        "SELL": ("bearish", "high"),
    }
    direction, confidence = signal_to_bias.get(signal, ("neutral", "low"))
    self.config.setdefault("bias", {})
    self.config["bias"]["direction"] = direction
    self.config["bias"]["confidence"] = confidence
    self.config["bias"]["reason"] = f"Auto: {ticker} analysis on {date} → {signal}"
    try:
        save_config(self.config, self.config_path)
    except Exception as exc:
        logger.warning("Failed to update bias from signal: %s", exc)
```

- [ ] **Step 2: Call it after signal extraction in run()**

In `run()`, after line `signal = self._extract_signal(final_decision)` and before the callback loop, add:

```python
self._update_bias_from_signal(signal, ticker, date)
```

- [ ] **Step 3: Test the method independently**

Run: `cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.engine import RunEngine
import tempfile, json, os
tf = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
json.dump({'strategy': 'stocks', 'paths': {'database': 'trading.db', 'agents_dir': 'agents/trading'}}, tf)
tf.close()
e = RunEngine(tf.name)
e._update_bias_from_signal('BUY', 'NVDA', '2026-03-31')
with open(tf.name) as f:
    cfg = json.load(f)
assert cfg['bias']['direction'] == 'bullish', f'Got {cfg[\"bias\"]}'
assert cfg['bias']['confidence'] == 'high'
print('PASS')
os.unlink(tf.name)
"`
Expected: `PASS`

- [ ] **Step 4: Commit**

```bash
cd /home/hoang/.openclaw/workspace
git add openclaw/engine.py
git commit -m "feat: auto-update bias from analysis signal"
```

---

### Task 3: Add trading.run gateway handler (spawn Python subprocess)

**Files:**
- Modify: `/home/hoang/openclaw/src/gateway/server-methods/trading.ts`
- Modify: `/home/hoang/openclaw/src/gateway/method-scopes.ts`

- [ ] **Step 1: Add imports and running-runs tracker at top of trading.ts**

After the existing imports, add:

```typescript
import { spawn, type ChildProcess } from "child_process";
import * as os from "os";

// Track running analysis processes: runId → { proc, progressFile, startedAt }
const runningRuns = new Map<
  string,
  { proc: ChildProcess; progressFile: string; startedAt: number }
>();
```

- [ ] **Step 2: Add the trading.run handler**

Add this handler to the `tradingHandlers` object (before the closing `};`):

```typescript
"trading.run": async ({ params, respond, context }) => {
  try {
    const p = params as { ticker: string; date?: string };
    const ticker = p.ticker?.toUpperCase().trim();
    if (!ticker) {
      respond(false, undefined, errorShape(ErrorCodes.BAD_REQUEST, "ticker is required"));
      return;
    }
    const date = p.date ?? new Date().toISOString().slice(0, 10);
    const runId = Math.random().toString(36).slice(2, 10);
    const progressFile = path.join(os.tmpdir(), `trading-run-${runId}.jsonl`);

    const proc = spawn("python3", [
      "-m", "openclaw.run_bridge",
      "--ticker", ticker,
      "--date", date,
      "--progress-file", progressFile,
      "--config", CONFIG_PATH,
    ], {
      cwd: WORKSPACE,
      env: { ...process.env, PYTHONPATH: WORKSPACE },
      stdio: ["ignore", "pipe", "pipe"],
    });

    runningRuns.set(runId, { proc, progressFile, startedAt: Date.now() });

    // Poll progress file and broadcast events
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
            context.broadcast("trading.progress", { runId, ...evt });
          } catch { /* skip malformed lines */ }
        }
      } catch { /* file may not exist yet */ }
    }, 500);

    let stdout = "";
    let stderr = "";
    proc.stdout?.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr?.on("data", (d: Buffer) => { stderr += d.toString(); });

    proc.on("close", (code) => {
      clearInterval(pollInterval);
      runningRuns.delete(runId);
      // Clean up progress file
      try { fs.unlinkSync(progressFile); } catch { /* ok */ }

      if (code === 0) {
        try {
          const result = JSON.parse(stdout.trim().split("\n").pop() ?? "{}");
          context.broadcast("trading.progress", {
            runId, event: "done", signal: result.signal, duration: result.duration,
          });
        } catch { /* ok */ }
      } else {
        context.broadcast("trading.progress", {
          runId, event: "failed", error: stderr.slice(0, 500),
        });
      }
    });

    respond(true, { runId, ticker, date, status: "started" });
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
  }
},
```

- [ ] **Step 3: Add trading.run.cancel handler**

```typescript
"trading.run.cancel": async ({ params, respond }) => {
  try {
    const p = params as { runId: string };
    const entry = runningRuns.get(p.runId);
    if (!entry) {
      respond(false, undefined, errorShape(ErrorCodes.NOT_FOUND, "Run not found or already finished"));
      return;
    }
    entry.proc.kill("SIGTERM");
    runningRuns.delete(p.runId);
    try { fs.unlinkSync(entry.progressFile); } catch { /* ok */ }
    respond(true, { ok: true, runId: p.runId });
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
  }
},
```

- [ ] **Step 4: Register methods in method-scopes.ts**

In WRITE_SCOPE array, add:

```typescript
"trading.run",
"trading.run.cancel",
```

- [ ] **Step 5: Rebuild gateway**

Run: `cd /home/hoang/openclaw && pnpm build 2>&1 | tail -5`
Expected: Build succeeds without errors.

- [ ] **Step 6: Commit**

```bash
cd /home/hoang/openclaw
git add src/gateway/server-methods/trading.ts src/gateway/method-scopes.ts
git commit -m "feat: add trading.run and trading.run.cancel gateway handlers"
```

---

### Task 4: Add trading.runs and trading.run.get handlers (run history + details)

**Files:**
- Modify: `/home/hoang/openclaw/src/gateway/server-methods/trading.ts`
- Modify: `/home/hoang/openclaw/src/gateway/method-scopes.ts`

- [ ] **Step 1: Add trading.runs handler (list past runs)**

```typescript
"trading.runs": async ({ params, respond }) => {
  try {
    const p = params as { page?: number; perPage?: number };
    const page = p.page ?? 1;
    const perPage = Math.min(p.perPage ?? 20, 100);
    const offset = (page - 1) * perPage;
    const config = readConfig();
    const dbPath = getDbPath(config);

    try {
      const db = new Database(dbPath, { readonly: true });
      const total = (db.prepare("SELECT COUNT(*) as cnt FROM runs").get() as { cnt: number }).cnt;
      const runs = db.prepare(
        "SELECT id, ticker, trade_date, strategy, signal, status, error_message, duration_seconds, created_at FROM runs ORDER BY created_at DESC LIMIT ? OFFSET ?"
      ).all(perPage, offset);
      db.close();
      respond(true, { runs, total, page, perPage });
    } catch {
      respond(true, { runs: [], total: 0, page, perPage });
    }
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
  }
},
```

- [ ] **Step 2: Add trading.run.get handler (single run with reports + debates)**

```typescript
"trading.run.get": async ({ params, respond }) => {
  try {
    const p = params as { runId: string };
    const config = readConfig();
    const dbPath = getDbPath(config);

    try {
      const db = new Database(dbPath, { readonly: true });
      const run = db.prepare(
        "SELECT id, ticker, trade_date, strategy, signal, status, error_message, duration_seconds, created_at FROM runs WHERE id = ?"
      ).get(p.runId);
      if (!run) {
        db.close();
        respond(false, undefined, errorShape(ErrorCodes.NOT_FOUND, "Run not found"));
        return;
      }
      const reports = db.prepare(
        "SELECT section_name, content FROM reports WHERE run_id = ?"
      ).all(p.runId);
      const debates = db.prepare(
        "SELECT debate_type, full_history, side_a_history, side_b_history, side_c_history, judge_decision FROM debates WHERE run_id = ?"
      ).all(p.runId);
      const outcome = db.prepare(
        "SELECT signal, actual_close, actual_change_pct, correct, reflection, created_at FROM outcomes WHERE run_id = ?"
      ).get(p.runId);
      db.close();
      respond(true, { run, reports, debates, outcome: outcome ?? null });
    } catch {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, "Database not available"));
    }
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
  }
},
```

- [ ] **Step 3: Add trading.run.delete handler**

```typescript
"trading.run.delete": async ({ params, respond }) => {
  try {
    const p = params as { runId: string };
    const config = readConfig();
    const dbPath = getDbPath(config);

    try {
      const db = new Database(dbPath);
      db.prepare("DELETE FROM reports WHERE run_id = ?").run(p.runId);
      db.prepare("DELETE FROM debates WHERE run_id = ?").run(p.runId);
      db.prepare("DELETE FROM outcomes WHERE run_id = ?").run(p.runId);
      db.prepare("DELETE FROM runs WHERE id = ?").run(p.runId);
      db.close();
      respond(true, { ok: true });
    } catch {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, "Database not available"));
    }
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
  }
},
```

- [ ] **Step 4: Add trading.run.reflect handler**

```typescript
"trading.run.reflect": async ({ params, respond }) => {
  try {
    const p = params as { ticker: string; date: string };
    const proc = spawn("python3", ["-c", `
import json
from openclaw.engine import RunEngine
engine = RunEngine("${CONFIG_PATH}")
result = engine.reflect("${p.ticker}", "${p.date}")
print(json.dumps(result))
`], {
      cwd: WORKSPACE,
      env: { ...process.env, PYTHONPATH: WORKSPACE },
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    proc.stdout?.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr?.on("data", (d: Buffer) => { stderr += d.toString(); });

    proc.on("close", (code) => {
      if (code === 0) {
        try {
          respond(true, JSON.parse(stdout.trim()));
        } catch {
          respond(true, { raw: stdout.trim() });
        }
      } else {
        respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, stderr.slice(0, 500)));
      }
    });
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
  }
},
```

- [ ] **Step 5: Register all new methods in method-scopes.ts**

In READ_SCOPE:
```typescript
"trading.runs",
"trading.run.get",
```

In WRITE_SCOPE:
```typescript
"trading.run.delete",
"trading.run.reflect",
```

- [ ] **Step 6: Rebuild gateway**

Run: `cd /home/hoang/openclaw && pnpm build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 7: Commit**

```bash
cd /home/hoang/openclaw
git add src/gateway/server-methods/trading.ts src/gateway/method-scopes.ts
git commit -m "feat: add trading.runs, trading.run.get, trading.run.delete, trading.run.reflect handlers"
```

---

## Phase B: UI Controller + Types (Task 5)

### Task 5: Add controller functions and types for new handlers

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/controllers/trading.ts`

- [ ] **Step 1: Add new types**

After the existing types, add:

```typescript
export interface RunListItem {
  id: string;
  ticker: string;
  trade_date: string;
  strategy: string;
  signal: string | null;
  status: string;
  error_message: string | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface RunReport {
  section_name: string;
  content: string;
}

export interface RunDebate {
  debate_type: string;
  full_history: string;
  side_a_history: string;
  side_b_history: string;
  side_c_history: string;
  judge_decision: string;
}

export interface RunOutcome {
  signal: string;
  actual_close: number | null;
  actual_change_pct: number | null;
  correct: number | null;
  reflection: string | null;
  created_at: string;
}

export interface RunDetail {
  run: RunListItem;
  reports: RunReport[];
  debates: RunDebate[];
  outcome: RunOutcome | null;
}

export interface RunProgress {
  runId: string;
  event: string;
  agent?: string;
  status?: string;
  signal?: string;
  duration?: number;
  error?: string;
  name?: string;
  length?: number;
  speaker?: string;
}
```

- [ ] **Step 2: Add controller functions**

```typescript
export async function startRun(
  client: GatewayBrowserClient,
  ticker: string,
  date?: string,
): Promise<{ runId: string; ticker: string; date: string }> {
  return await client.request("trading.run", { ticker, date });
}

export async function cancelRun(
  client: GatewayBrowserClient,
  runId: string,
): Promise<void> {
  await client.request("trading.run.cancel", { runId });
}

export async function loadRuns(
  client: GatewayBrowserClient,
  page = 1,
  perPage = 20,
): Promise<{ runs: RunListItem[]; total: number; page: number; perPage: number }> {
  return await client.request("trading.runs", { page, perPage });
}

export async function loadRunDetail(
  client: GatewayBrowserClient,
  runId: string,
): Promise<RunDetail> {
  return await client.request("trading.run.get", { runId });
}

export async function deleteRun(
  client: GatewayBrowserClient,
  runId: string,
): Promise<void> {
  await client.request("trading.run.delete", { runId });
}

export async function reflectRun(
  client: GatewayBrowserClient,
  ticker: string,
  date: string,
): Promise<Record<string, unknown>> {
  return await client.request("trading.run.reflect", { ticker, date });
}
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/controllers/trading.ts
git commit -m "feat: add controller functions for run management"
```

---

## Phase C: Run Analysis UI (Tasks 6-8)

### Task 6: Add run form + agent progress panel to trading view

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/views/trading.ts`

- [ ] **Step 1: Add new props to TradingProps**

Add these to the `TradingProps` type:

```typescript
// Run analysis
runTicker: string;
runDate: string;
runningRunId: string | null;
agentProgress: Array<{ agent: string; status: string }>;
onRunTickerChange: (value: string) => void;
onRunDateChange: (value: string) => void;
onStartRun: () => void;
onCancelRun: () => void;
```

- [ ] **Step 2: Add renderRunForm function**

Add this function after `renderHaltSwitch`:

```typescript
const PIPELINE_AGENTS = [
  { name: "market-analyst", tier: "Tier 1" },
  { name: "social-analyst", tier: "Tier 1" },
  { name: "news-analyst", tier: "Tier 1" },
  { name: "fundamentals-analyst", tier: "Tier 1" },
  { name: "bull-researcher", tier: "Tier 2" },
  { name: "bear-researcher", tier: "Tier 2" },
  { name: "research-manager", tier: "Tier 3" },
  { name: "trader", tier: "Tier 3" },
  { name: "aggressive-risk", tier: "Tier 3" },
  { name: "conservative-risk", tier: "Tier 3" },
  { name: "neutral-risk", tier: "Tier 3" },
  { name: "portfolio-manager", tier: "Tier 4" },
];

const STATUS_ICONS: Record<string, string> = {
  pending: "○",
  running: "◉",
  completed: "●",
  failed: "✗",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "var(--claw-text-secondary)",
  running: "var(--claw-accent)",
  completed: "var(--claw-green)",
  failed: "var(--claw-red)",
};

function renderRunForm(props: TradingProps) {
  const isRunning = props.runningRunId !== null;
  const today = new Date().toISOString().slice(0, 10);

  return html`
    <section style="${sectionStyle}">
      <div style="font-weight:600;color:var(--claw-text);margin-bottom:12px;">Run Analysis</div>
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:14px;">
        <input
          type="text"
          .value=${props.runTicker}
          placeholder="Ticker (e.g. NVDA)"
          ?disabled=${isRunning}
          @input=${(e: Event) => props.onRunTickerChange((e.target as HTMLInputElement).value)}
          @keydown=${(e: KeyboardEvent) => { if (e.key === "Enter" && !isRunning) props.onStartRun(); }}
          style="${inputStyle}max-width:140px;text-transform:uppercase;"
        />
        <input
          type="date"
          .value=${props.runDate || today}
          ?disabled=${isRunning}
          @input=${(e: Event) => props.onRunDateChange((e.target as HTMLInputElement).value)}
          style="${inputStyle}max-width:160px;"
        />
        ${isRunning
          ? html`
            <button
              @click=${props.onCancelRun}
              style="padding:6px 14px;border:none;background:var(--claw-red);color:#fff;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;"
            >Cancel</button>
          `
          : html`
            <button
              @click=${props.onStartRun}
              style="padding:6px 14px;border:none;background:var(--claw-green);color:#fff;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;"
            >Analyze</button>
          `
        }
      </div>
      ${isRunning || props.agentProgress.length > 0
        ? html`
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px;">
            ${PIPELINE_AGENTS.map((agent) => {
              const progress = props.agentProgress.find((p) => p.agent === agent.name);
              const status = progress?.status ?? "pending";
              return html`
                <div style="display:flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid var(--claw-border);border-radius:6px;font-size:12px;">
                  <span style="color:${STATUS_COLORS[status] ?? "var(--claw-text-secondary)"};font-size:14px;">${STATUS_ICONS[status] ?? "○"}</span>
                  <div>
                    <div style="color:var(--claw-text);font-weight:500;">${agent.name}</div>
                    <div style="color:var(--claw-text-secondary);font-size:10px;">${agent.tier}</div>
                  </div>
                </div>
              `;
            })}
          </div>
        `
        : nothing
      }
    </section>
  `;
}
```

- [ ] **Step 3: Insert renderRunForm into the main render function**

In `renderTrading()`, add `${renderRunForm(props)}` after `${renderHaltSwitch(props)}`:

```typescript
return html`
  <div style="padding:24px;max-width:1100px;">
    ${renderHaltSwitch(props)} ${renderRunForm(props)} ${renderBiasControl(props)} ${renderLastRun(props)}
    ${renderWatchlist(props)} ${renderPipeline(props)} ${renderRiskParams(props)}
    ${renderLlmConfig(props)} ${renderMemoryStats(props)}
  </div>
`;
```

- [ ] **Step 4: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/views/trading.ts
git commit -m "feat: add run analysis form and agent progress panel"
```

---

### Task 7: Add run history table to trading view

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/views/trading.ts`

- [ ] **Step 1: Add new props for run history**

Add to `TradingProps`:

```typescript
// Run history
runs: Array<{ id: string; ticker: string; trade_date: string; signal: string | null; status: string; duration_seconds: number | null; created_at: string }>;
runsTotal: number;
runsPage: number;
onLoadRuns: (page: number) => void;
onViewRun: (runId: string) => void;
onDeleteRun: (runId: string) => void;
onReflectRun: (ticker: string, date: string) => void;
```

- [ ] **Step 2: Add renderRunHistory function**

```typescript
function renderRunHistory(props: TradingProps) {
  const runs = props.runs ?? [];
  const total = props.runsTotal ?? 0;
  const page = props.runsPage ?? 1;
  const perPage = 10;
  const totalPages = Math.ceil(total / perPage);

  return html`
    <section style="${sectionStyle}">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div style="font-weight:600;color:var(--claw-text);">Run History (${total})</div>
        <button @click=${() => props.onLoadRuns(1)} style="${btnStyle}">Refresh</button>
      </div>
      ${runs.length === 0
        ? html`<div style="color:var(--claw-text-secondary);font-size:13px;">No runs yet. Run an analysis above.</div>`
        : html`
          <table style="width:100%;border-collapse:collapse;font-size:13px;color:var(--claw-text);">
            <thead>
              <tr style="border-bottom:1px solid var(--claw-border);">
                <th style="text-align:left;padding:4px 8px;color:var(--claw-text-secondary);">Ticker</th>
                <th style="text-align:left;padding:4px 8px;color:var(--claw-text-secondary);">Date</th>
                <th style="text-align:left;padding:4px 8px;color:var(--claw-text-secondary);">Signal</th>
                <th style="text-align:left;padding:4px 8px;color:var(--claw-text-secondary);">Status</th>
                <th style="text-align:left;padding:4px 8px;color:var(--claw-text-secondary);">Duration</th>
                <th style="padding:4px 8px;"></th>
              </tr>
            </thead>
            <tbody>
              ${runs.map((run) => html`
                <tr style="border-bottom:1px solid var(--claw-border);">
                  <td style="padding:6px 8px;font-weight:600;">${run.ticker}</td>
                  <td style="padding:6px 8px;color:var(--claw-text-secondary);">${run.trade_date}</td>
                  <td style="padding:6px 8px;color:${signalColor(run.signal)};font-weight:600;">${run.signal ?? "—"}</td>
                  <td style="padding:6px 8px;">${run.status}</td>
                  <td style="padding:6px 8px;color:var(--claw-text-secondary);">${run.duration_seconds ? `${Math.round(run.duration_seconds)}s` : "—"}</td>
                  <td style="padding:6px 8px;display:flex;gap:4px;">
                    <button @click=${() => props.onViewRun(run.id)} style="${btnStyle}">View</button>
                    <button @click=${() => props.onReflectRun(run.ticker, run.trade_date)} style="${btnStyle}">Reflect</button>
                    <button @click=${() => props.onDeleteRun(run.id)} style="padding:4px 10px;border:1px solid var(--claw-border);background:transparent;color:var(--claw-red);border-radius:4px;cursor:pointer;font-size:12px;">Del</button>
                  </td>
                </tr>
              `)}
            </tbody>
          </table>
          ${totalPages > 1 ? html`
            <div style="display:flex;justify-content:center;gap:8px;margin-top:10px;">
              <button ?disabled=${page <= 1} @click=${() => props.onLoadRuns(page - 1)} style="${btnStyle}">← Prev</button>
              <span style="font-size:12px;color:var(--claw-text-secondary);align-self:center;">Page ${page} of ${totalPages}</span>
              <button ?disabled=${page >= totalPages} @click=${() => props.onLoadRuns(page + 1)} style="${btnStyle}">Next →</button>
            </div>
          ` : nothing}
        `
      }
    </section>
  `;
}
```

- [ ] **Step 3: Add to main render function**

In `renderTrading()`, add `${renderRunHistory(props)}` after `${renderLastRun(props)}`:

```typescript
${renderHaltSwitch(props)} ${renderRunForm(props)} ${renderBiasControl(props)} ${renderLastRun(props)}
${renderRunHistory(props)}
${renderWatchlist(props)} ${renderPipeline(props)} ${renderRiskParams(props)}
```

- [ ] **Step 4: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/views/trading.ts
git commit -m "feat: add run history table with pagination"
```

---

### Task 8: Add run detail modal to trading view

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/views/trading.ts`

- [ ] **Step 1: Add new props for run detail**

Add to `TradingProps`:

```typescript
// Run detail
selectedRun: {
  run: { id: string; ticker: string; trade_date: string; signal: string | null; status: string; duration_seconds: number | null };
  reports: Array<{ section_name: string; content: string }>;
  debates: Array<{ debate_type: string; full_history: string; judge_decision: string }>;
  outcome: { signal: string; actual_close: number | null; actual_change_pct: number | null; correct: number | null } | null;
} | null;
selectedRunTab: string;
onCloseRunDetail: () => void;
onSelectRunTab: (tab: string) => void;
```

- [ ] **Step 2: Add renderRunDetail function**

```typescript
function renderRunDetail(props: TradingProps) {
  const detail = props.selectedRun;
  if (!detail) return nothing;

  const run = detail.run;
  const tabs = ["reports", "debates", "outcome"];
  const activeTab = props.selectedRunTab || "reports";

  return html`
    <section style="${sectionStyle}border:2px solid var(--claw-accent);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div style="font-weight:600;color:var(--claw-text);">
          Run Detail: ${run.ticker} on ${run.trade_date}
          <span style="color:${signalColor(run.signal)};margin-left:8px;">${run.signal ?? "pending"}</span>
        </div>
        <button @click=${props.onCloseRunDetail} style="${btnStyle}">Close</button>
      </div>

      <div style="display:flex;gap:6px;margin-bottom:14px;">
        ${tabs.map((tab) => html`
          <button
            @click=${() => props.onSelectRunTab(tab)}
            style="padding:5px 14px;border:2px solid ${activeTab === tab ? "var(--claw-accent)" : "var(--claw-border)"};background:${activeTab === tab ? "var(--claw-accent)" : "transparent"};color:${activeTab === tab ? "#fff" : "var(--claw-text)"};border-radius:6px;cursor:pointer;font-size:12px;text-transform:capitalize;"
          >${tab}</button>
        `)}
      </div>

      ${activeTab === "reports" ? html`
        ${detail.reports.length === 0
          ? html`<div style="color:var(--claw-text-secondary);font-size:13px;">No reports.</div>`
          : detail.reports.map((r) => html`
            <div style="margin-bottom:14px;">
              <div style="font-weight:600;font-size:13px;color:var(--claw-accent);margin-bottom:6px;">${r.section_name.replace(/_/g, " ").toUpperCase()}</div>
              <pre style="font-size:12px;color:var(--claw-text);background:var(--claw-surface-2, #1a1a2e);padding:12px;border-radius:6px;overflow-x:auto;white-space:pre-wrap;max-height:400px;overflow-y:auto;">${r.content}</pre>
            </div>
          `)
        }
      ` : nothing}

      ${activeTab === "debates" ? html`
        ${detail.debates.length === 0
          ? html`<div style="color:var(--claw-text-secondary);font-size:13px;">No debates.</div>`
          : detail.debates.map((d) => html`
            <div style="margin-bottom:14px;">
              <div style="font-weight:600;font-size:13px;color:var(--claw-accent);margin-bottom:6px;">${d.debate_type.toUpperCase()} DEBATE</div>
              ${d.judge_decision ? html`
                <div style="background:var(--claw-accent);color:#fff;padding:8px 12px;border-radius:6px;margin-bottom:8px;font-size:12px;">
                  <strong>Judge Decision:</strong> ${d.judge_decision.slice(0, 500)}${d.judge_decision.length > 500 ? "..." : ""}
                </div>
              ` : nothing}
              <pre style="font-size:12px;color:var(--claw-text);background:var(--claw-surface-2, #1a1a2e);padding:12px;border-radius:6px;overflow-x:auto;white-space:pre-wrap;max-height:400px;overflow-y:auto;">${d.full_history}</pre>
            </div>
          `)
        }
      ` : nothing}

      ${activeTab === "outcome" ? html`
        ${detail.outcome
          ? html`
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;font-size:13px;">
              <div style="border:1px solid var(--claw-border);border-radius:6px;padding:10px;">
                <div style="font-size:11px;color:var(--claw-text-secondary);">Signal</div>
                <div style="font-weight:600;color:${signalColor(detail.outcome.signal)};">${detail.outcome.signal}</div>
              </div>
              <div style="border:1px solid var(--claw-border);border-radius:6px;padding:10px;">
                <div style="font-size:11px;color:var(--claw-text-secondary);">Actual Close</div>
                <div style="font-weight:600;color:var(--claw-text);">${detail.outcome.actual_close != null ? `$${detail.outcome.actual_close.toFixed(2)}` : "—"}</div>
              </div>
              <div style="border:1px solid var(--claw-border);border-radius:6px;padding:10px;">
                <div style="font-size:11px;color:var(--claw-text-secondary);">Change</div>
                <div style="font-weight:600;color:${(detail.outcome.actual_change_pct ?? 0) >= 0 ? "var(--claw-green)" : "var(--claw-red)"};">
                  ${detail.outcome.actual_change_pct != null ? `${detail.outcome.actual_change_pct.toFixed(2)}%` : "—"}
                </div>
              </div>
              <div style="border:1px solid var(--claw-border);border-radius:6px;padding:10px;">
                <div style="font-size:11px;color:var(--claw-text-secondary);">Correct?</div>
                <div style="font-weight:600;">
                  ${detail.outcome.correct === 1 ? html`<span style="color:var(--claw-green);">✓ Yes</span>` :
                    detail.outcome.correct === 0 ? html`<span style="color:var(--claw-red);">✗ No</span>` :
                    html`<span style="color:var(--claw-text-secondary);">N/A</span>`}
                </div>
              </div>
            </div>
          `
          : html`<div style="color:var(--claw-text-secondary);font-size:13px;">No outcome recorded. Click "Reflect" on a run to record actual results.</div>`
        }
      ` : nothing}
    </section>
  `;
}
```

- [ ] **Step 3: Add to main render function**

In `renderTrading()`, add `${renderRunDetail(props)}` after `${renderRunHistory(props)}`:

```typescript
${renderRunHistory(props)}
${renderRunDetail(props)}
```

- [ ] **Step 4: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/views/trading.ts
git commit -m "feat: add run detail panel with reports/debates/outcome tabs"
```

---

## Phase D: Wire UI State + Callbacks (Tasks 9-10)

### Task 9: Add state fields to app.ts

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/app.ts`

- [ ] **Step 1: Add new @state() fields**

After the existing trading state fields (`tradingBiasReason`), add:

```typescript
@state() tradingRunTicker = "";
@state() tradingRunDate = "";
@state() tradingRunningRunId: string | null = null;
@state() tradingAgentProgress: Array<{ agent: string; status: string }> = [];
@state() tradingRuns: Array<{ id: string; ticker: string; trade_date: string; signal: string | null; status: string; duration_seconds: number | null; created_at: string }> = [];
@state() tradingRunsTotal = 0;
@state() tradingRunsPage = 1;
@state() tradingSelectedRun: Record<string, unknown> | null = null;
@state() tradingSelectedRunTab = "reports";
```

- [ ] **Step 2: Add loadRuns method**

After the existing `loadTrading()` method, add:

```typescript
async loadRuns(page = 1) {
  if (!this.client) return;
  try {
    const { loadRuns } = await import("./controllers/trading.ts");
    const result = await loadRuns(this.client, page, 10);
    this.tradingRuns = result.runs;
    this.tradingRunsTotal = result.total;
    this.tradingRunsPage = result.page;
  } catch { /* ok */ }
}
```

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/app.ts
git commit -m "feat: add trading run state fields to app"
```

---

### Task 10: Wire all new callbacks in app-render.ts

**Files:**
- Modify: `/home/hoang/openclaw/ui/src/ui/app-render.ts`

- [ ] **Step 1: Add the new props to the renderTrading call**

In the `m.renderTrading({...})` call, add after the existing callbacks:

```typescript
// Run analysis
runTicker: state.tradingRunTicker,
runDate: state.tradingRunDate,
runningRunId: state.tradingRunningRunId,
agentProgress: state.tradingAgentProgress,
onRunTickerChange: (value: string) => {
  state.tradingRunTicker = value;
},
onRunDateChange: (value: string) => {
  state.tradingRunDate = value;
},
onStartRun: async () => {
  if (!state.tradingRunTicker.trim()) return;
  const { startRun } = await import("./controllers/trading.ts");
  const result = await startRun(
    state.client!,
    state.tradingRunTicker.trim(),
    state.tradingRunDate || undefined,
  );
  state.tradingRunningRunId = result.runId;
  state.tradingAgentProgress = [];
},
onCancelRun: async () => {
  if (!state.tradingRunningRunId) return;
  const { cancelRun } = await import("./controllers/trading.ts");
  await cancelRun(state.client!, state.tradingRunningRunId);
  state.tradingRunningRunId = null;
},
// Run history
runs: state.tradingRuns,
runsTotal: state.tradingRunsTotal,
runsPage: state.tradingRunsPage,
onLoadRuns: (page: number) => void state.loadRuns(page),
onViewRun: async (runId: string) => {
  const { loadRunDetail } = await import("./controllers/trading.ts");
  const detail = await loadRunDetail(state.client!, runId);
  state.tradingSelectedRun = detail as unknown as Record<string, unknown>;
  state.tradingSelectedRunTab = "reports";
},
onDeleteRun: async (runId: string) => {
  const { deleteRun } = await import("./controllers/trading.ts");
  await deleteRun(state.client!, runId);
  void state.loadRuns(state.tradingRunsPage);
  void state.loadTrading();
},
onReflectRun: async (ticker: string, date: string) => {
  const { reflectRun } = await import("./controllers/trading.ts");
  await reflectRun(state.client!, ticker, date);
  void state.loadRuns(state.tradingRunsPage);
  void state.loadTrading();
},
// Run detail
selectedRun: state.tradingSelectedRun as TradingProps["selectedRun"],
selectedRunTab: state.tradingSelectedRunTab,
onCloseRunDetail: () => {
  state.tradingSelectedRun = null;
},
onSelectRunTab: (tab: string) => {
  state.tradingSelectedRunTab = tab;
},
```

- [ ] **Step 2: Add WebSocket event listener for trading.progress**

In the trading tab lazy-load section, before the `lazyRender` call, add a progress event subscription. Find the section that does `void state.loadTrading()` on first load and add:

```typescript
// Subscribe to trading progress events
if (state.client && !state._tradingProgressSubscribed) {
  state._tradingProgressSubscribed = true;
  state.client.on("trading.progress", (data: Record<string, unknown>) => {
    const evt = data as { runId: string; event: string; agent?: string; status?: string; signal?: string };
    if (evt.event === "agent_status" && evt.agent && evt.status) {
      const progress = [...state.tradingAgentProgress];
      const idx = progress.findIndex((p) => p.agent === evt.agent);
      if (idx >= 0) {
        progress[idx] = { agent: evt.agent!, status: evt.status! };
      } else {
        progress.push({ agent: evt.agent!, status: evt.status! });
      }
      state.tradingAgentProgress = progress;
    }
    if (evt.event === "done" || evt.event === "failed" || evt.event === "complete") {
      state.tradingRunningRunId = null;
      void state.loadTrading();
      void state.loadRuns(1);
    }
  });
}
```

Note: The exact mechanism for subscribing to broadcast events depends on the `GatewayBrowserClient` API. Check how other views subscribe to events (e.g., `chat` events in `app-chat.ts`). If the client uses `.on(event, handler)`, use that. If it uses a different pattern, match it.

- [ ] **Step 3: Auto-load runs when trading tab opens**

In the trading tab's first-load trigger (where `state.loadTrading()` is called), add:

```typescript
void state.loadRuns(1);
```

- [ ] **Step 4: Rebuild UI**

Run: `cd /home/hoang/openclaw && pnpm ui:build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
cd /home/hoang/openclaw
git add ui/src/ui/app-render.ts
git commit -m "feat: wire trading run analysis, history, detail callbacks"
```

---

## Phase E: Build + Test (Tasks 11-12)

### Task 11: Full rebuild and restart

- [ ] **Step 1: Rebuild gateway**

Run: `cd /home/hoang/openclaw && pnpm build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 2: Rebuild UI**

Run: `cd /home/hoang/openclaw && pnpm ui:build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 3: Restart gateway**

Run: `systemctl --user restart openclaw-gateway && sleep 2 && systemctl --user status openclaw-gateway | head -5`
Expected: `active (running)`

- [ ] **Step 4: Verify trading tab loads**

Run: `curl -s http://127.0.0.1:18789/ | head -5`
Expected: HTML content.

- [ ] **Step 5: Verify trading.runs handler works**

Run: `curl -s -X POST http://127.0.0.1:18789/rpc -H "Content-Type: application/json" -H "Authorization: Bearer 94e40f37036ff3883f1b0a4077a7235a82f7dcc3631638c0" -d '{"method":"trading.runs","params":{"page":1}}' | python3 -m json.tool | head -10`
Expected: JSON with `runs` array.

---

### Task 12: Test run_bridge subprocess independently

- [ ] **Step 1: Test with dry run (no dispatch_fn = stub responses)**

Run: `cd /home/hoang/.openclaw/workspace && python3 -m openclaw.run_bridge --ticker TEST --date 2026-03-31 --progress-file /tmp/test-run.jsonl 2>&1 | head -5`
Expected: Output showing dispatch to stub agents (will use `_default_dispatch` since no real AI is connected).

- [ ] **Step 2: Check progress file was created**

Run: `cat /tmp/test-run.jsonl`
Expected: JSON lines with `agent_status`, `report`, `signal`, `complete` events.

- [ ] **Step 3: Clean up**

Run: `rm -f /tmp/test-run.jsonl`

- [ ] **Step 4: Commit all remaining changes**

```bash
cd /home/hoang/.openclaw/workspace
git add -A
git commit -m "feat: trading full UI — run analysis, progress, history, detail, reflect, auto-bias"
```

---

## Summary

| Phase | Tasks | What it adds |
|-------|-------|-------------|
| A: Backend | 1-4 | run_bridge.py, auto-bias, trading.run/cancel/runs/get/delete/reflect handlers |
| B: Controller | 5 | Types + functions for all new handlers |
| C: UI | 6-8 | Run form, agent progress, run history table, run detail panel |
| D: Wiring | 9-10 | State fields, callbacks, WebSocket progress events |
| E: Build | 11-12 | Rebuild, restart, test |

**After completion:** Open http://127.0.0.1:18789/ → Trading tab. You'll see:
- **Run Analysis** — enter ticker + date, click Analyze, watch 12 agent progress dots go from ○ → ◉ → ●
- **Bias auto-updates** — after analysis completes, bias panel updates to match the signal
- **Run History** — table of past runs with View/Reflect/Delete buttons
- **Run Detail** — click View to see reports, debates, and outcomes in tabbed panels
- **All existing controls** — halt, bias, watchlist, risk, LLM, pipeline, JadeCap — all still editable
