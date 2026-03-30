# OpenClaw Trading Integration — Full Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the trading module a first-class citizen in OpenClaw — visible in the OpenClaw agent list, controllable via TRADING.md, and accessible through a dedicated WebUI Trading Monitor page with bias control, watchlist, pipeline status, halt switch, and risk parameters.

**Architecture:** Three integration layers: (1) OpenClaw agent registration in `openclaw.json` so trading appears in the agent list, (2) `TRADING.md` as the human-readable control panel the agent reads on startup, (3) React WebUI Trading Monitor page backed by new FastAPI endpoints reading from `trading-config.json` + `trading.db`.

**Tech Stack:** OpenClaw agent system (`openclaw.json`, `agents/` directory), React 19, Vite, Tailwind CSS variables, FastAPI, SQLite

---

## File Structure

```
/home/hoang/.openclaw/
├── openclaw.json                                    ← MODIFY: register trading agent
├── agents/
│   ├── main/                                        ← existing main agent
│   └── trading-monitor/                             ← CREATE: trading agent registration
│       └── agent/
│           └── models.json                          ← CREATE: model config
│
├── workspace/
│   ├── TRADING.md                                   ← EXISTS (created earlier)
│   ├── dashboard/web/
│   │   ├── backend/
│   │   │   ├── app.py                               ← MODIFY: register trading router
│   │   │   └── routes/
│   │   │       └── trading.py                       ← CREATE: 5 API endpoints
│   │   └── frontend/src/
│   │       ├── App.jsx                              ← MODIFY: add /trading route
│   │       ├── components/
│   │       │   ├── Layout.jsx                       ← MODIFY: add Trading nav + rename to OpenClaw
│   │       │   ├── HaltSwitch.jsx                   ← CREATE
│   │       │   ├── BiasControl.jsx                  ← CREATE
│   │       │   ├── WatchlistPanel.jsx               ← CREATE
│   │       │   ├── PipelineStatus.jsx               ← CREATE
│   │       │   └── RiskPanel.jsx                    ← CREATE
│   │       └── pages/
│   │           └── TradingMonitor.jsx               ← CREATE: main page
│   └── tests/
│       └── test_trading_api.py                      ← CREATE: backend endpoint tests
```

---

## Phase A: OpenClaw Agent Registration (2 tasks)

### Task A.1: Register trading agent in openclaw.json

**Files:**
- Modify: `/home/hoang/.openclaw/openclaw.json`

- [ ] **Step 1: Add trading-monitor to agents.list**

Open `/home/hoang/.openclaw/openclaw.json` and change the `agents.list` array from:

```json
"list": [
  {
    "id": "main",
    "tools": {
      "profile": "full"
    }
  }
]
```

To:

```json
"list": [
  {
    "id": "main",
    "tools": {
      "profile": "full"
    }
  },
  {
    "id": "trading-monitor",
    "label": "Trading Monitor",
    "description": "Analysis-only trading pipeline — 12 subagents producing BUY/HOLD/SELL signals",
    "tools": {
      "profile": "full"
    },
    "workspace": "/home/hoang/.openclaw/workspace",
    "boot": [
      "TRADING.md",
      "SOUL.md"
    ]
  }
]
```

- [ ] **Step 2: Verify the JSON is valid**

```bash
python3 -c "import json; json.load(open('/home/hoang/.openclaw/openclaw.json')); print('VALID')"
```
Expected: `VALID`

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/.openclaw/workspace
git add /home/hoang/.openclaw/openclaw.json
git commit -m "feat: register trading-monitor agent in openclaw.json"
```

---

### Task A.2: Create trading agent directory

**Files:**
- Create: `/home/hoang/.openclaw/agents/trading-monitor/agent/models.json`

- [ ] **Step 1: Create directory and models.json**

```bash
mkdir -p /home/hoang/.openclaw/agents/trading-monitor/agent
mkdir -p /home/hoang/.openclaw/agents/trading-monitor/sessions
```

Create `/home/hoang/.openclaw/agents/trading-monitor/agent/models.json`:

```json
{
  "primary": "openai-codex/gpt-5.4",
  "available": {
    "openai-codex/gpt-5.4": { "label": "GPT-5.4 (default)" },
    "anthropic/claude-opus-4-6": { "label": "Claude Opus 4.6 (deep think)" }
  }
}
```

- [ ] **Step 2: Verify agent directory exists**

```bash
ls -la /home/hoang/.openclaw/agents/trading-monitor/agent/
```
Expected: `models.json` listed

- [ ] **Step 3: Commit**

```bash
git add /home/hoang/.openclaw/agents/trading-monitor/
git commit -m "feat: create trading-monitor agent directory with model config"
```

---

## Phase B: Backend — Trading API Endpoints (1 task)

### Task B.1: Create trading router with 5 endpoints

**Files:**
- Create: `dashboard/web/backend/routes/trading.py`
- Modify: `dashboard/web/backend/app.py`
- Create: `tests/test_trading_api.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_trading_api.py
"""Tests for /api/trading/* endpoints."""

import json
import os
import pytest
from openclaw.config import load_config, save_config, SCHEMA_DEFAULTS
from openclaw.database import init_db, get_db


@pytest.fixture
def config_file(tmp_path):
    """Create a test config and DB."""
    config = {
        "strategy": "default",
        "watchlist": ["NVDA"],
        "bias": {"direction": "neutral", "reason": "", "confidence": "medium"},
        "halt": False,
        "risk": {"max_loss_per_trade": 500, "daily_loss_limit": 1000},
        "llm": {"default": "gpt-4o", "deep_think": "claude-opus-4-6", "quick_think": "gpt-4o-mini"},
        "analysis": {"analysts": ["market"], "max_debate_rounds": 1, "max_risk_discuss_rounds": 1, "agent_timeout_seconds": 300},
        "paths": {"database": str(tmp_path / "test.db"), "agents_dir": str(tmp_path / "agents")},
    }
    path = str(tmp_path / "test-config.json")
    with open(path, "w") as f:
        json.dump(config, f)
    init_db(config["paths"]["database"])
    return path


def test_bias_roundtrip(config_file):
    """Set bias, reload config, verify persisted."""
    config = load_config(config_file)
    config["bias"] = {"direction": "bullish", "reason": "NQ displacement", "confidence": "high"}
    save_config(config, config_file)

    reloaded = load_config(config_file)
    assert reloaded["bias"]["direction"] == "bullish"
    assert reloaded["bias"]["reason"] == "NQ displacement"
    assert reloaded["bias"]["confidence"] == "high"


def test_halt_roundtrip(config_file):
    """Set halt, reload, verify."""
    config = load_config(config_file)
    config["halt"] = True
    save_config(config, config_file)

    reloaded = load_config(config_file)
    assert reloaded["halt"] is True


def test_watchlist_add_remove(config_file):
    """Add and remove tickers from watchlist."""
    config = load_config(config_file)
    assert "NVDA" in config["watchlist"]

    config["watchlist"].append("AAPL")
    save_config(config, config_file)
    reloaded = load_config(config_file)
    assert "AAPL" in reloaded["watchlist"]

    config["watchlist"] = [t for t in config["watchlist"] if t != "NVDA"]
    save_config(config, config_file)
    reloaded = load_config(config_file)
    assert "NVDA" not in reloaded["watchlist"]
    assert "AAPL" in reloaded["watchlist"]


def test_risk_update(config_file):
    """Update risk params, verify merge."""
    config = load_config(config_file)
    config["risk"]["max_loss_per_trade"] = 750
    save_config(config, config_file)

    reloaded = load_config(config_file)
    assert reloaded["risk"]["max_loss_per_trade"] == 750
    assert reloaded["risk"]["daily_loss_limit"] == 1000  # unchanged


def test_schema_defaults_has_bias():
    """SCHEMA_DEFAULTS must include bias section."""
    assert "bias" in SCHEMA_DEFAULTS
    assert SCHEMA_DEFAULTS["bias"]["direction"] == "neutral"
    assert SCHEMA_DEFAULTS["bias"]["confidence"] == "medium"
```

- [ ] **Step 2: Run tests — expect PASS**

```bash
cd /home/hoang/.openclaw/workspace
.venv/bin/python -m pytest tests/test_trading_api.py -v
```
Expected: 5 PASSED

- [ ] **Step 3: Create `dashboard/web/backend/routes/trading.py`**

```python
"""Trading monitor API endpoints.

Endpoints:
    GET  /api/trading/status    — full trading state (config + DB + market phase)
    PUT  /api/trading/bias      — update market bias
    PUT  /api/trading/halt      — toggle halt state
    PUT  /api/trading/watchlist  — add/remove/set watchlist tickers
    PUT  /api/trading/risk      — update risk parameters
"""

import os
from typing import Any, Dict

from fastapi import APIRouter

from openclaw.config import load_config, save_config, deep_merge
from openclaw.database import safe_get_db
from openclaw.heartbeat import get_market_phase

router = APIRouter(prefix="/api/trading")


@router.get("/status")
async def get_trading_status() -> dict:
    """Return full trading status for the monitor page.

    Combines: config values, recent run data from DB, memory stats, market phase.
    Single call gives the frontend everything it needs.
    """
    config = load_config()
    db_path = config.get("paths", {}).get("database", "trading.db")
    phase = get_market_phase(config)

    watchlist_data = []
    last_run = None
    memory_stats = []

    try:
        with safe_get_db(db_path) as conn:
            for ticker in config.get("watchlist", []):
                row = conn.execute(
                    "SELECT signal, trade_date, status FROM runs "
                    "WHERE ticker = ? ORDER BY created_at DESC LIMIT 1",
                    (ticker,),
                ).fetchone()
                outcome = conn.execute(
                    "SELECT correct FROM outcomes "
                    "WHERE ticker = ? ORDER BY created_at DESC LIMIT 1",
                    (ticker,),
                ).fetchone()
                watchlist_data.append({
                    "ticker": ticker,
                    "signal": row["signal"] if row else None,
                    "date": row["trade_date"] if row else None,
                    "status": row["status"] if row else None,
                    "correct": bool(outcome["correct"]) if outcome and outcome["correct"] is not None else None,
                })

            row = conn.execute(
                "SELECT id, ticker, trade_date, strategy, signal, status, "
                "duration_seconds, created_at FROM runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if row:
                last_run = dict(row)

            rows = conn.execute(
                "SELECT agent_name, COUNT(*) as count FROM memories "
                "GROUP BY agent_name ORDER BY count DESC"
            ).fetchall()
            memory_stats = [{"agent": r["agent_name"], "count": r["count"]} for r in rows]
    except Exception:
        pass

    return {
        "state": "halted" if config.get("halt") else "active",
        "strategy": config.get("strategy", "default"),
        "market_phase": phase,
        "bias": config.get("bias", {"direction": "neutral", "reason": "", "confidence": "medium"}),
        "watchlist": watchlist_data,
        "last_run": last_run,
        "memory_stats": memory_stats,
        "risk": config.get("risk", {}),
        "llm": config.get("llm", {}),
        "analysis": config.get("analysis", {}),
        "schedule": config.get("schedule", {}),
        "jadecap": config.get("jadecap", {}) if config.get("strategy") == "jadecap" else None,
    }


@router.put("/bias")
async def set_bias(payload: Dict[str, Any]) -> dict:
    """Update market bias direction, reason, and confidence.

    Args (JSON body):
        direction: "bullish" | "bearish" | "neutral"
        reason: free text explaining the bias
        confidence: "low" | "medium" | "high"
    """
    config = load_config()
    config["bias"] = {
        "direction": payload.get("direction", "neutral"),
        "reason": payload.get("reason", ""),
        "confidence": payload.get("confidence", "medium"),
    }
    save_config(config)
    return {"status": "ok", "bias": config["bias"]}


@router.put("/halt")
async def set_halt(payload: Dict[str, Any]) -> dict:
    """Toggle halt state. When halted, RunEngine.run() raises RuntimeError.

    Args (JSON body):
        halt: boolean
    """
    config = load_config()
    config["halt"] = bool(payload.get("halt", False))
    save_config(config)
    return {"status": "ok", "halt": config["halt"]}


@router.put("/watchlist")
async def set_watchlist(payload: Dict[str, Any]) -> dict:
    """Add, remove, or replace watchlist tickers.

    Args (JSON body):
        action: "add" | "remove" | "set"
        ticker: single ticker (for add/remove)
        tickers: list of tickers (for set)
    """
    config = load_config()
    action = payload.get("action", "set")
    ticker = payload.get("ticker", "").upper().strip()

    if action == "add" and ticker:
        if ticker not in config.get("watchlist", []):
            config.setdefault("watchlist", []).append(ticker)
    elif action == "remove" and ticker:
        config["watchlist"] = [t for t in config.get("watchlist", []) if t != ticker]
    elif action == "set":
        config["watchlist"] = [t.upper().strip() for t in payload.get("tickers", [])]

    save_config(config)
    return {"status": "ok", "watchlist": config["watchlist"]}


@router.put("/risk")
async def set_risk(payload: Dict[str, Any]) -> dict:
    """Update risk parameters (deep-merged with existing).

    Args (JSON body): any subset of risk fields to update.
    """
    config = load_config()
    config["risk"] = deep_merge(config.get("risk", {}), payload)
    save_config(config)
    return {"status": "ok", "risk": config["risk"]}
```

- [ ] **Step 4: Register router in app.py**

In `dashboard/web/backend/app.py`, add this import near the other router imports:

```python
from dashboard.web.backend.routes.trading import router as trading_router
```

And add this line after the other `app.include_router(...)` calls:

```python
app.include_router(trading_router)
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/web/backend/routes/trading.py dashboard/web/backend/app.py tests/test_trading_api.py
git commit -m "feat: add /api/trading/* endpoints + tests"
```

---

## Phase C: Frontend Components (5 tasks)

### Task C.1: HaltSwitch component

**Files:**
- Create: `dashboard/web/frontend/src/components/HaltSwitch.jsx`

- [ ] **Step 1: Create `HaltSwitch.jsx`**

```jsx
import { api } from '../hooks/useApi';

export default function HaltSwitch({ halted, onToggle }) {
  const handleToggle = async () => {
    try {
      await api('/api/trading/halt', { method: 'PUT', body: { halt: !halted } });
      onToggle(!halted);
    } catch (err) {
      console.error('Halt toggle failed:', err);
    }
  };

  return (
    <button
      onClick={handleToggle}
      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all"
      style={{
        backgroundColor: halted
          ? 'color-mix(in srgb, var(--danger) 15%, transparent)'
          : 'color-mix(in srgb, var(--success) 15%, transparent)',
        color: halted ? 'var(--danger)' : 'var(--success)',
        border: `1px solid ${halted ? 'var(--danger)' : 'var(--success)'}`,
      }}
    >
      <span
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: halted ? 'var(--danger)' : 'var(--success)' }}
      />
      {halted ? 'HALTED — Click to Resume' : 'ACTIVE — Click to Halt'}
    </button>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/web/frontend/src/components/HaltSwitch.jsx
git commit -m "feat: add HaltSwitch component"
```

---

### Task C.2: BiasControl component

**Files:**
- Create: `dashboard/web/frontend/src/components/BiasControl.jsx`

- [ ] **Step 1: Create `BiasControl.jsx`**

```jsx
import { useState } from 'react';
import { api } from '../hooks/useApi';

const DIRECTIONS = ['bullish', 'neutral', 'bearish'];
const CONFIDENCES = ['low', 'medium', 'high'];
const DIR_STYLES = {
  bullish: { color: 'var(--success)', bg: 'color-mix(in srgb, var(--success) 15%, transparent)' },
  neutral: { color: 'var(--text-secondary)', bg: 'color-mix(in srgb, var(--text-secondary) 10%, transparent)' },
  bearish: { color: 'var(--danger)', bg: 'color-mix(in srgb, var(--danger) 15%, transparent)' },
};

export default function BiasControl({ bias, onUpdate }) {
  const [reason, setReason] = useState(bias?.reason || '');
  const [saving, setSaving] = useState(false);
  const dir = bias?.direction || 'neutral';
  const conf = bias?.confidence || 'medium';
  const style = DIR_STYLES[dir] || DIR_STYLES.neutral;

  const save = async (updates) => {
    setSaving(true);
    try {
      const body = { direction: dir, reason, confidence: conf, ...updates };
      const result = await api('/api/trading/bias', { method: 'PUT', body });
      onUpdate(result.bias);
      if (updates.reason !== undefined) setReason(updates.reason);
    } catch (err) {
      console.error('Bias update failed:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {DIRECTIONS.map((d) => {
          const s = DIR_STYLES[d];
          const active = dir === d;
          return (
            <button key={d} onClick={() => save({ direction: d })} disabled={saving}
              className="flex-1 py-2 px-3 rounded-lg text-sm font-semibold transition-all capitalize"
              style={{
                backgroundColor: active ? s.bg : 'transparent',
                color: active ? s.color : 'var(--text-secondary)',
                border: `1.5px solid ${active ? s.color : 'var(--border)'}`,
                opacity: saving ? 0.5 : 1,
              }}>
              {d}
            </button>
          );
        })}
      </div>
      <div className="flex gap-2 items-center">
        <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Confidence:</span>
        {CONFIDENCES.map((c) => (
          <button key={c} onClick={() => save({ confidence: c })} disabled={saving}
            className="px-2 py-0.5 rounded text-xs font-medium transition-all capitalize"
            style={{
              backgroundColor: conf === c ? style.bg : 'transparent',
              color: conf === c ? style.color : 'var(--text-secondary)',
              border: `1px solid ${conf === c ? style.color : 'var(--border)'}`,
            }}>
            {c}
          </button>
        ))}
      </div>
      <input type="text" value={reason} onChange={(e) => setReason(e.target.value)}
        onBlur={() => save({ reason })} onKeyDown={(e) => e.key === 'Enter' && save({ reason })}
        placeholder="Bias reason (e.g. NQ displacement above midnight open)"
        className="w-full px-3 py-1.5 rounded-lg text-sm border outline-none focus:ring-2"
        style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/web/frontend/src/components/BiasControl.jsx
git commit -m "feat: add BiasControl component"
```

---

### Task C.3: WatchlistPanel component

**Files:**
- Create: `dashboard/web/frontend/src/components/WatchlistPanel.jsx`

- [ ] **Step 1: Create `WatchlistPanel.jsx`**

```jsx
import { useState } from 'react';
import { api } from '../hooks/useApi';
import SignalBadge from './SignalBadge';

export default function WatchlistPanel({ watchlist, onUpdate }) {
  const [newTicker, setNewTicker] = useState('');

  const handleAdd = async () => {
    if (!newTicker.trim()) return;
    try {
      const result = await api('/api/trading/watchlist', { method: 'PUT', body: { action: 'add', ticker: newTicker.trim() } });
      onUpdate(result.watchlist);
      setNewTicker('');
    } catch (err) { console.error('Add failed:', err); }
  };

  const handleRemove = async (ticker) => {
    try {
      const result = await api('/api/trading/watchlist', { method: 'PUT', body: { action: 'remove', ticker } });
      onUpdate(result.watchlist);
    } catch (err) { console.error('Remove failed:', err); }
  };

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <input type="text" value={newTicker} onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()} placeholder="Add ticker (e.g. NVDA)"
          className="flex-1 px-3 py-1.5 rounded-lg text-sm border outline-none focus:ring-2"
          style={{ backgroundColor: 'var(--bg-secondary)', borderColor: 'var(--border)', color: 'var(--text-primary)' }} />
        <button onClick={handleAdd} className="px-3 py-1.5 rounded-lg text-sm font-semibold text-white"
          style={{ backgroundColor: 'var(--accent)' }}>Add</button>
      </div>
      {(!watchlist || watchlist.length === 0) ? (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No tickers — add one above</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: 'var(--text-secondary)' }}>
              <th className="text-left py-1.5">Ticker</th>
              <th className="text-left py-1.5">Signal</th>
              <th className="text-left py-1.5">Date</th>
              <th className="text-left py-1.5">Status</th>
              <th className="text-center py-1.5">Correct?</th>
              <th className="text-right py-1.5"></th>
            </tr>
          </thead>
          <tbody>
            {watchlist.map((item) => (
              <tr key={item.ticker} className="border-t" style={{ borderColor: 'var(--border)' }}>
                <td className="py-2 font-semibold" style={{ color: 'var(--text-primary)' }}>{item.ticker}</td>
                <td className="py-2">{item.signal ? <SignalBadge signal={item.signal} /> : '—'}</td>
                <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{item.date || '—'}</td>
                <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{item.status || '—'}</td>
                <td className="py-2 text-center">{item.correct === true ? '✓' : item.correct === false ? '✗' : '—'}</td>
                <td className="py-2 text-right">
                  <button onClick={() => handleRemove(item.ticker)} className="text-xs px-2 py-0.5 rounded" style={{ color: 'var(--danger)' }}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/web/frontend/src/components/WatchlistPanel.jsx
git commit -m "feat: add WatchlistPanel component"
```

---

### Task C.4: PipelineStatus and RiskPanel components

**Files:**
- Create: `dashboard/web/frontend/src/components/PipelineStatus.jsx`
- Create: `dashboard/web/frontend/src/components/RiskPanel.jsx`

- [ ] **Step 1: Create `PipelineStatus.jsx`**

```jsx
export default function PipelineStatus({ analysis, strategy }) {
  const analysts = analysis?.analysts || ['market', 'social', 'news', 'fundamentals'];
  const debateRounds = analysis?.max_debate_rounds || 1;
  const riskRounds = analysis?.max_risk_discuss_rounds || 1;

  const tiers = [
    { label: 'Tier 1: Analysts', detail: analysts.join(', '), color: 'var(--accent)' },
    { label: 'Tier 2: Bull/Bear Debate', detail: `${debateRounds} round${debateRounds > 1 ? 's' : ''}`, color: 'var(--success)' },
    { label: 'Tier 3: Judge + Trader + Risk', detail: `${riskRounds} round${riskRounds > 1 ? 's' : ''} (aggressive → conservative → neutral)`, color: 'var(--warning)' },
    { label: 'Tier 4: Portfolio Manager', detail: 'Final BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL', color: 'var(--danger)' },
  ];

  return (
    <div className="space-y-2">
      {tiers.map((tier, i) => (
        <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: tier.color }} />
          <div>
            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{tier.label}</div>
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{tier.detail}</div>
          </div>
        </div>
      ))}
      <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
        Strategy: <strong>{strategy || 'default'}</strong> | Timeout: {analysis?.agent_timeout_seconds || 300}s/agent
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `RiskPanel.jsx`**

```jsx
export default function RiskPanel({ risk, jadecap }) {
  const params = [
    { label: 'Max Loss / Trade', value: `$${risk?.max_loss_per_trade || 500}` },
    { label: 'Daily Loss Limit', value: `$${risk?.daily_loss_limit || 1000}` },
    { label: 'Max Drawdown', value: `${risk?.max_drawdown_pct || 5}%` },
    { label: 'Max Consecutive Losses', value: risk?.max_consecutive_losses || 3 },
    { label: 'Min Risk/Reward', value: `${risk?.min_risk_reward || 3}:1` },
  ];
  if (jadecap) {
    params.push(
      { label: 'ATR Stop Multiplier', value: `${jadecap.atr_stop_multiplier || 1.5}x` },
      { label: 'T1 Close', value: `${(jadecap.t1_close_pct || 0.5) * 100}%` },
      { label: 'Hard Close', value: `${jadecap.hard_close_time || '15:45'} ET` },
      { label: 'Instrument', value: `${jadecap.active_instrument || 'NQ'} ($${jadecap.instruments?.[jadecap.active_instrument]?.point_value || 20}/pt)` },
    );
  }
  return (
    <div className="grid grid-cols-2 gap-2">
      {params.map(({ label, value }) => (
        <div key={label} className="px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
          <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</div>
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{value}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/web/frontend/src/components/PipelineStatus.jsx dashboard/web/frontend/src/components/RiskPanel.jsx
git commit -m "feat: add PipelineStatus and RiskPanel components"
```

---

### Task C.5: TradingMonitor page

**Files:**
- Create: `dashboard/web/frontend/src/pages/TradingMonitor.jsx`

- [ ] **Step 1: Create the full page**

```jsx
import { useState, useEffect, useCallback } from 'react';
import { api } from '../hooks/useApi';
import ErrorBanner from '../components/ErrorBanner';
import HaltSwitch from '../components/HaltSwitch';
import BiasControl from '../components/BiasControl';
import WatchlistPanel from '../components/WatchlistPanel';
import PipelineStatus from '../components/PipelineStatus';
import RiskPanel from '../components/RiskPanel';
import SignalBadge from '../components/SignalBadge';

function Card({ title, children }) {
  return (
    <div className="rounded-xl border p-5" style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border)' }}>
      {title && <h3 className="text-base font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>{title}</h3>}
      {children}
    </div>
  );
}

const PHASE_LABELS = { pre: 'Pre-Session', open: 'Market Open', midday: 'Midday', close: 'Near Close', post: 'Post-Session', closed: 'Market Closed' };

export default function TradingMonitor() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api('/api/trading/status');
      setStatus(data);
      setError(null);
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading) return <div className="flex items-center justify-center h-64"><p style={{ color: 'var(--text-secondary)' }}>Loading...</p></div>;

  const s = status || {};
  const phase = PHASE_LABELS[s.market_phase] || s.market_phase || 'Unknown';

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>Trading Monitor</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>{s.strategy?.toUpperCase()} | {phase}</p>
        </div>
        <HaltSwitch halted={s.state === 'halted'} onToggle={() => fetchStatus()} />
      </div>

      {error && <ErrorBanner message={error} type="error" onDismiss={() => setError(null)} />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Market Bias">
          <BiasControl bias={s.bias} onUpdate={(bias) => setStatus((p) => ({ ...p, bias }))} />
        </Card>
        <Card title="Last Run">
          {s.last_run ? (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>{s.last_run.ticker}</span>
                {s.last_run.signal && <SignalBadge signal={s.last_run.signal} />}
              </div>
              <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
                <div>Date: {s.last_run.trade_date} | Strategy: {s.last_run.strategy}</div>
                <div>Duration: {s.last_run.duration_seconds?.toFixed(1)}s | Status: {s.last_run.status}</div>
              </div>
            </div>
          ) : <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No runs yet</p>}
        </Card>
      </div>

      <Card title="Watchlist">
        <WatchlistPanel watchlist={s.watchlist} onUpdate={() => fetchStatus()} />
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Pipeline"><PipelineStatus analysis={s.analysis} strategy={s.strategy} /></Card>
        <Card title="Risk Parameters"><RiskPanel risk={s.risk} jadecap={s.jadecap} /></Card>
      </div>

      {s.memory_stats?.length > 0 && (
        <Card title="Memory Stats">
          <div className="flex flex-wrap gap-3">
            {s.memory_stats.map(({ agent, count }) => (
              <div key={agent} className="px-3 py-1.5 rounded-lg text-xs" style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>
                <span className="font-medium">{agent}</span> <span style={{ color: 'var(--text-secondary)' }}>({count})</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card title="LLM Configuration">
        <div className="grid grid-cols-3 gap-2 text-sm">
          {[['Default', s.llm?.default || 'gpt-4o'], ['Deep Think', s.llm?.deep_think || 'claude-opus-4-6'], ['Quick Think', s.llm?.quick_think || 'gpt-4o-mini']].map(([label, val]) => (
            <div key={label} className="px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
              <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>{label}</div>
              <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{val}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/web/frontend/src/pages/TradingMonitor.jsx
git commit -m "feat: add TradingMonitor page"
```

---

## Phase D: Wire Route + Navigation + Build (1 task)

### Task D.1: Add route, nav link, rename header, rebuild

**Files:**
- Modify: `dashboard/web/frontend/src/App.jsx`
- Modify: `dashboard/web/frontend/src/components/Layout.jsx`

- [ ] **Step 1: Update App.jsx — add /trading route**

Replace full content of `dashboard/web/frontend/src/App.jsx`:

```jsx
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import TradingMonitor from './pages/TradingMonitor';
import LiveRun from './pages/LiveRun';
import RunDetails from './pages/RunDetails';
import CompareView from './pages/CompareView';
import Memories from './pages/Memories';
import Settings from './pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/trading" element={<TradingMonitor />} />
        <Route path="/runs/:id/live" element={<LiveRun />} />
        <Route path="/runs/:id" element={<RunDetails />} />
        <Route path="/runs/:id/compare/:id2" element={<CompareView />} />
        <Route path="/memories" element={<Memories />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
```

- [ ] **Step 2: Update Layout.jsx — add Trading nav link + rename title**

In `dashboard/web/frontend/src/components/Layout.jsx`, change `navLinks`:

```jsx
const navLinks = [
  { to: '/', label: 'Dashboard' },
  { to: '/trading', label: 'Trading' },
  { to: '/memories', label: 'Memories' },
  { to: '/settings', label: 'Settings' },
];
```

And change the header title from `TradingAgents` to `OpenClaw`:

```jsx
<h1 className="text-lg font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
  OpenClaw
</h1>
```

- [ ] **Step 3: Rebuild frontend**

```bash
cd /home/hoang/.openclaw/workspace/dashboard/web/frontend
npm run build
```
Expected: `✓ built in` message, `dist/` directory updated

- [ ] **Step 4: Run backend tests**

```bash
cd /home/hoang/.openclaw/workspace
.venv/bin/python -m pytest tests/ -v
```
Expected: ALL PASS (58+ tests)

- [ ] **Step 5: Commit everything**

```bash
git add dashboard/web/frontend/src/App.jsx dashboard/web/frontend/src/components/Layout.jsx dashboard/web/frontend/dist/
git commit -m "feat: wire Trading page into nav, rename to OpenClaw, rebuild frontend"
```

---

## Phase E: Update Plan + Final Push (1 task)

### Task E.1: Update main plan, push, retag

- [ ] **Step 1: Append Phase 10 to main plan**

Append to `docs/superpowers/plans/2026-03-27-openclaw-tradingagents-merge.md`:

```markdown
## Phase 10: WebUI Trading Monitor + OpenClaw Agent Registration (added 2026-03-29)

### New Backend
- `dashboard/web/backend/routes/trading.py` — 5 endpoints:
  - `GET /api/trading/status` → full state (config + DB + market phase + bias + watchlist + memory stats)
  - `PUT /api/trading/bias` → update direction/reason/confidence
  - `PUT /api/trading/halt` → toggle halt
  - `PUT /api/trading/watchlist` → add/remove/set tickers
  - `PUT /api/trading/risk` → update risk params (deep merge)

### New Frontend
- `TradingMonitor.jsx` — main page: halt switch, bias control, watchlist, last run, pipeline, risk, memory stats, LLM config. Auto-refreshes every 30s.
- `HaltSwitch.jsx` — green ACTIVE / red HALTED toggle
- `BiasControl.jsx` — BULLISH/NEUTRAL/BEARISH buttons + confidence + reason input
- `WatchlistPanel.jsx` — ticker table with signals, add/remove
- `PipelineStatus.jsx` — 4-tier pipeline visualization
- `RiskPanel.jsx` — risk parameters grid (adapts for JadeCap)

### Modified
- `App.jsx` — add `/trading` route
- `Layout.jsx` — add "Trading" nav link, rename header to "OpenClaw"
- `app.py` — register trading router

### OpenClaw Agent Registration
- `openclaw.json` → `agents.list` includes `trading-monitor`
- `agents/trading-monitor/agent/models.json` — model config
```

- [ ] **Step 2: Push and retag**

```bash
git add -A
git commit -m "feat: Phase 10 — WebUI Trading Monitor + OpenClaw agent registration"
git tag -f v0.1.0-merge -m "OpenClaw + TradingAgents merge complete (with Trading Monitor)"
git push origin main --tags --force
```

---

## Summary

| Phase | Tasks | Creates | Modifies |
|-------|-------|---------|----------|
| A. Agent Registration | 2 | `openclaw.json` entry, `agents/trading-monitor/` | `openclaw.json` |
| B. Backend API | 1 | `routes/trading.py`, `test_trading_api.py` | `app.py` |
| C. Frontend Components | 5 | 6 React components | — |
| D. Wire + Build | 1 | — | `App.jsx`, `Layout.jsx`, `dist/` |
| E. Plan + Push | 1 | — | plan .md |
| **Total** | **10** | **9 new files** | **4 modified** |
