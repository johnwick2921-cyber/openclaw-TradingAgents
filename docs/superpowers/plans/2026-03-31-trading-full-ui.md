# Trading Full UI — Complete Feature Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Trading tab in OpenClaw Control UI fully functional — matching all features from the old TradingAgents WebUI. Run analysis, monitor agent progress live, view results, reflect, manage memories. All on port 18789.

**Current state:** Trading tab shows status/config only (bias, watchlist, pipeline, risk). Missing: run analysis, agent progress, run history, run details, reflect, memories.

**Architecture:**
- Gateway server methods (TypeScript) for run management + WebSocket events for live streaming
- Lit views for each feature panel
- RunEngine (Python) invoked via gateway's `agent` method or a bridge script
- All on port 18789, zero companion services

**The critical bridge problem:** The RunEngine is Python. The gateway is Node.js. To run analysis from the UI, we need a bridge. Options:
1. Gateway spawns `python -c "from openclaw.engine import RunEngine; ..."` as a subprocess
2. Gateway calls the trading-monitor agent via `agent` method (which dispatches via OpenClaw's AI system)
3. A small Python HTTP server on localhost that the gateway proxies to

**Recommended: Option 2** — Use OpenClaw's own agent system. The Trading tab's "Run Analysis" button sends a message to the trading-monitor agent: "Run analysis for NVDA on 2026-03-31". The agent reads TRADING.md, calls RunEngine, and streams results back. This is the OpenClaw-native way.

---

## Missing Features (from old WebUI)

### Priority 1 — Core (must have)
1. **Run Analysis button** — ticker input + "Analyze" button → dispatch to trading-monitor agent
2. **Agent Progress** — live status of each agent (pending/running/completed/failed)
3. **Run History** — list of past runs from trading.db
4. **Run Details** — view reports, debates, final decision for any run

### Priority 2 — Actions
5. **Cancel Run** — abort running analysis
6. **Reflect** — enter P&L, generate memory lessons
7. **Re-run** — re-run same ticker/date

### Priority 3 — Advanced
8. **Memories viewer** — browse/search/delete agent memories
9. **Export/Import** — export run data as JSON
10. **Compare** — side-by-side run comparison
11. **Live Price** — streaming ticker price

---

## Gateway Server Methods Needed

### New methods to add to trading.ts:

```
trading.run         — Start analysis (ticker, date) → returns runId
trading.runs        — List past runs (page, perPage, sortBy, order) → runs[]
trading.run.get     — Get single run with reports + debates
trading.run.cancel  — Cancel running analysis
trading.run.delete  — Delete a run
trading.run.reflect — Save P&L reflection + generate memories
trading.run.rerun   — Re-run with same config
trading.memories    — List memories by agent
trading.memories.search — Search memories
trading.memories.delete — Delete memory
```

### For live streaming:
The gateway already has WebSocket event streaming. When a run starts, the handler emits `trading.agent.status` events that the UI subscribes to.

---

## Implementation Tasks (18 tasks)

### Phase A: Run Management Backend (Tasks 1-5)
1. Add `trading.run` handler — spawn Python subprocess to run analysis
2. Add `trading.runs` handler — query runs table with pagination
3. Add `trading.run.get` handler — fetch run + reports + debates
4. Add `trading.run.cancel` handler — kill subprocess
5. Add `trading.run.reflect` handler — write outcomes + memories

### Phase B: Run Analysis UI (Tasks 6-9)
6. Add run form to trading view (ticker input + analyze button)
7. Add agent progress panel (12 agents with status icons)
8. Add run history table (past runs with signals)
9. Add run details panel (tabbed: analysts, debate, trader, risk, final)

### Phase C: Memory Management (Tasks 10-12)
10. Add `trading.memories` + `trading.memories.search` handlers
11. Add `trading.memories.delete` handler
12. Add memories panel to trading view

### Phase D: Actions (Tasks 13-15)
13. Add reflect panel (P&L input + generate lessons)
14. Add re-run + cancel buttons
15. Add export/import handlers

### Phase E: Build + Test (Tasks 16-18)
16. Rebuild gateway + UI
17. Test all features end-to-end
18. Update plan + push

---

## Critical Design: Python Bridge

The `trading.run` handler needs to execute Python code (RunEngine). Here's how:

```typescript
import { spawn } from "child_process";

// In trading.run handler:
const proc = spawn("python3", ["-c", `
import json, sys
from openclaw.engine import RunEngine

engine = RunEngine("${CONFIG_PATH}")

def dispatch(agent_name, prompt, model):
    # For now: stub dispatch. Real dispatch needs AI API call.
    return f"[Analysis from {agent_name}]"

result = engine.run("${ticker}", "${date}", dispatch_fn=dispatch)
print(json.dumps({
    "run_id": result.run_id,
    "signal": result.signal,
    "duration": result.duration_seconds,
}))
`], { cwd: WORKSPACE });
```

For REAL dispatch (with actual AI), the handler should use OpenClaw's agent system:
```typescript
// Send message to trading-monitor agent session
context.sendToAgent("trading-monitor", `Run full analysis for ${ticker} on ${date}`);
```

This lets the trading-monitor agent use its configured LLM to dispatch all 12 subagents.

---

**This plan needs to be detailed with full code before execution. The scope is large (18 tasks). Should I write the full detailed plan now, or start with Phase A (backend) and iterate?**
