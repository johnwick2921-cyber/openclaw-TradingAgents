# WebUI Trading Monitor Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Trading" page to the React WebUI that shows live trading status, bias control, watchlist with signals, pipeline config, halt switch, and risk parameters — matching what `TRADING.md` shows but as an interactive web view.

**Architecture:** New React page (`TradingMonitor.jsx`) fetching from existing `/api/trading-config` GET/PUT endpoints + new `/api/trading/status` endpoint for live state. Uses the same CSS variable theming as all other pages. No new dependencies.

**Tech Stack:** React 19, Vite, Tailwind CSS (via CSS variables), FastAPI backend

---

## File Structure

```
dashboard/web/
├── frontend/src/
│   ├── pages/
│   │   └── TradingMonitor.jsx   ← CREATE: main trading monitor page
│   ├── components/
│   │   ├── Layout.jsx           ← MODIFY: add "Trading" nav link
│   │   ├── BiasControl.jsx      ← CREATE: bias direction selector
│   │   ├── WatchlistPanel.jsx   ← CREATE: watchlist table with signals
│   │   ├── PipelineStatus.jsx   ← CREATE: 4-tier pipeline visualization
│   │   ├── RiskPanel.jsx        ← CREATE: risk parameters display/edit
│   │   └── HaltSwitch.jsx       ← CREATE: halt/resume toggle
│   └── App.jsx                  ← MODIFY: add /trading route
├── backend/routes/
│   └── trading.py               ← CREATE: /api/trading/* endpoints
└── backend/app.py               ← MODIFY: register trading router
```

---

## Task 1: Backend — Trading Status Endpoint

**Files:**
- Create: `dashboard/web/backend/routes/trading.py`
- Modify: `dashboard/web/backend/app.py`

- [ ] **Step 1: Create `dashboard/web/backend/routes/trading.py`**

```python
"""Trading monitor API endpoints."""

from typing import Any, Dict, List
from fastapi import APIRouter
from openclaw.config import load_config, save_config, deep_merge
from openclaw.database import safe_get_db
from openclaw.heartbeat import get_market_phase

router = APIRouter(prefix="/api/trading")


@router.get("/status")
async def get_trading_status() -> dict:
    """Return full trading status for the monitor page.

    Combines config, recent runs, memory stats, market phase into one response.
    """
    config = load_config()
    db_path = config.get("paths", {}).get("database", "trading.db")
    phase = get_market_phase(config)

    # Recent runs from DB
    watchlist_data = []
    last_run = None
    memory_stats = []

    try:
        with safe_get_db(db_path) as conn:
            # Watchlist with latest signals
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

            # Last run
            row = conn.execute(
                "SELECT id, ticker, trade_date, strategy, signal, status, "
                "duration_seconds, created_at FROM runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if row:
                last_run = dict(row)

            # Memory stats
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
    """Update market bias (direction, reason, confidence)."""
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
    """Toggle halt state."""
    config = load_config()
    config["halt"] = bool(payload.get("halt", False))
    save_config(config)
    return {"status": "ok", "halt": config["halt"]}


@router.put("/watchlist")
async def set_watchlist(payload: Dict[str, Any]) -> dict:
    """Update watchlist (add/remove tickers)."""
    config = load_config()
    action = payload.get("action", "set")
    ticker = payload.get("ticker", "").upper().strip()

    if action == "add" and ticker:
        if ticker not in config.get("watchlist", []):
            config.setdefault("watchlist", []).append(ticker)
    elif action == "remove" and ticker:
        config["watchlist"] = [t for t in config.get("watchlist", []) if t != ticker]
    elif action == "set":
        config["watchlist"] = payload.get("tickers", [])

    save_config(config)
    return {"status": "ok", "watchlist": config["watchlist"]}


@router.put("/risk")
async def set_risk(payload: Dict[str, Any]) -> dict:
    """Update risk parameters."""
    config = load_config()
    config["risk"] = deep_merge(config.get("risk", {}), payload)
    save_config(config)
    return {"status": "ok", "risk": config["risk"]}
```

- [ ] **Step 2: Register router in app.py**

In `dashboard/web/backend/app.py`, add after the existing router imports:

```python
from dashboard.web.backend.routes.trading import router as trading_router
```

And in the `app` setup, add:

```python
app.include_router(trading_router)
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/web/backend/routes/trading.py dashboard/web/backend/app.py
git commit -m "feat: add /api/trading/* endpoints for monitor page"
```

---

## Task 2: Frontend — HaltSwitch Component

**Files:**
- Create: `dashboard/web/frontend/src/components/HaltSwitch.jsx`

- [ ] **Step 1: Create the component**

```jsx
// dashboard/web/frontend/src/components/HaltSwitch.jsx
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

## Task 3: Frontend — BiasControl Component

**Files:**
- Create: `dashboard/web/frontend/src/components/BiasControl.jsx`

- [ ] **Step 1: Create the component**

```jsx
// dashboard/web/frontend/src/components/BiasControl.jsx
import { useState } from 'react';
import { api } from '../hooks/useApi';

const DIRECTIONS = ['bullish', 'neutral', 'bearish'];
const CONFIDENCES = ['low', 'medium', 'high'];

const DIRECTION_STYLES = {
  bullish: { color: 'var(--success)', bg: 'color-mix(in srgb, var(--success) 15%, transparent)' },
  neutral: { color: 'var(--text-secondary)', bg: 'color-mix(in srgb, var(--text-secondary) 10%, transparent)' },
  bearish: { color: 'var(--danger)', bg: 'color-mix(in srgb, var(--danger) 15%, transparent)' },
};

export default function BiasControl({ bias, onUpdate }) {
  const [reason, setReason] = useState(bias?.reason || '');
  const [saving, setSaving] = useState(false);

  const handleDirectionChange = async (direction) => {
    setSaving(true);
    try {
      const result = await api('/api/trading/bias', {
        method: 'PUT',
        body: { direction, reason, confidence: bias?.confidence || 'medium' },
      });
      onUpdate(result.bias);
    } catch (err) {
      console.error('Bias update failed:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleConfidenceChange = async (confidence) => {
    setSaving(true);
    try {
      const result = await api('/api/trading/bias', {
        method: 'PUT',
        body: { direction: bias?.direction || 'neutral', reason, confidence },
      });
      onUpdate(result.bias);
    } catch (err) {
      console.error('Bias update failed:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleReasonSave = async () => {
    setSaving(true);
    try {
      const result = await api('/api/trading/bias', {
        method: 'PUT',
        body: { direction: bias?.direction || 'neutral', reason, confidence: bias?.confidence || 'medium' },
      });
      onUpdate(result.bias);
    } catch (err) {
      console.error('Bias update failed:', err);
    } finally {
      setSaving(false);
    }
  };

  const currentDir = bias?.direction || 'neutral';
  const style = DIRECTION_STYLES[currentDir] || DIRECTION_STYLES.neutral;

  return (
    <div className="space-y-3">
      {/* Direction buttons */}
      <div className="flex gap-2">
        {DIRECTIONS.map((dir) => {
          const s = DIRECTION_STYLES[dir];
          const active = currentDir === dir;
          return (
            <button
              key={dir}
              onClick={() => handleDirectionChange(dir)}
              disabled={saving}
              className="flex-1 py-2 px-3 rounded-lg text-sm font-semibold transition-all capitalize"
              style={{
                backgroundColor: active ? s.bg : 'transparent',
                color: active ? s.color : 'var(--text-secondary)',
                border: `1.5px solid ${active ? s.color : 'var(--border)'}`,
                opacity: saving ? 0.5 : 1,
              }}
            >
              {dir}
            </button>
          );
        })}
      </div>

      {/* Confidence */}
      <div className="flex gap-2 items-center">
        <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>Confidence:</span>
        {CONFIDENCES.map((c) => (
          <button
            key={c}
            onClick={() => handleConfidenceChange(c)}
            disabled={saving}
            className="px-2 py-0.5 rounded text-xs font-medium transition-all capitalize"
            style={{
              backgroundColor: bias?.confidence === c ? style.bg : 'transparent',
              color: bias?.confidence === c ? style.color : 'var(--text-secondary)',
              border: `1px solid ${bias?.confidence === c ? style.color : 'var(--border)'}`,
            }}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Reason */}
      <div className="flex gap-2">
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          onBlur={handleReasonSave}
          onKeyDown={(e) => e.key === 'Enter' && handleReasonSave()}
          placeholder="Bias reason (e.g. NQ displacement above midnight open)"
          className="flex-1 px-3 py-1.5 rounded-lg text-sm border outline-none transition-colors focus:ring-2"
          style={{
            backgroundColor: 'var(--bg-secondary)',
            borderColor: 'var(--border)',
            color: 'var(--text-primary)',
          }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/web/frontend/src/components/BiasControl.jsx
git commit -m "feat: add BiasControl component with direction/confidence/reason"
```

---

## Task 4: Frontend — WatchlistPanel Component

**Files:**
- Create: `dashboard/web/frontend/src/components/WatchlistPanel.jsx`

- [ ] **Step 1: Create the component**

```jsx
// dashboard/web/frontend/src/components/WatchlistPanel.jsx
import { useState } from 'react';
import { api } from '../hooks/useApi';
import SignalBadge from './SignalBadge';

export default function WatchlistPanel({ watchlist, onUpdate }) {
  const [newTicker, setNewTicker] = useState('');

  const handleAdd = async () => {
    if (!newTicker.trim()) return;
    try {
      const result = await api('/api/trading/watchlist', {
        method: 'PUT',
        body: { action: 'add', ticker: newTicker.trim() },
      });
      onUpdate(result.watchlist);
      setNewTicker('');
    } catch (err) {
      console.error('Add ticker failed:', err);
    }
  };

  const handleRemove = async (ticker) => {
    try {
      const result = await api('/api/trading/watchlist', {
        method: 'PUT',
        body: { action: 'remove', ticker },
      });
      onUpdate(result.watchlist);
    } catch (err) {
      console.error('Remove ticker failed:', err);
    }
  };

  return (
    <div>
      {/* Add ticker input */}
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="Add ticker (e.g. NVDA)"
          className="flex-1 px-3 py-1.5 rounded-lg text-sm border outline-none focus:ring-2"
          style={{
            backgroundColor: 'var(--bg-secondary)',
            borderColor: 'var(--border)',
            color: 'var(--text-primary)',
          }}
        />
        <button
          onClick={handleAdd}
          className="px-3 py-1.5 rounded-lg text-sm font-semibold text-white"
          style={{ backgroundColor: 'var(--accent)' }}
        >
          Add
        </button>
      </div>

      {/* Watchlist table */}
      {(!watchlist || watchlist.length === 0) ? (
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No tickers in watchlist</p>
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
                <td className="py-2 font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {item.ticker}
                </td>
                <td className="py-2">
                  {item.signal ? <SignalBadge signal={item.signal} /> : <span style={{ color: 'var(--text-secondary)' }}>—</span>}
                </td>
                <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{item.date || '—'}</td>
                <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{item.status || '—'}</td>
                <td className="py-2 text-center">
                  {item.correct === true ? '✓' : item.correct === false ? '✗' : '—'}
                </td>
                <td className="py-2 text-right">
                  <button
                    onClick={() => handleRemove(item.ticker)}
                    className="text-xs px-2 py-0.5 rounded"
                    style={{ color: 'var(--danger)' }}
                  >
                    Remove
                  </button>
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
git commit -m "feat: add WatchlistPanel component with add/remove/signals"
```

---

## Task 5: Frontend — PipelineStatus and RiskPanel Components

**Files:**
- Create: `dashboard/web/frontend/src/components/PipelineStatus.jsx`
- Create: `dashboard/web/frontend/src/components/RiskPanel.jsx`

- [ ] **Step 1: Create PipelineStatus**

```jsx
// dashboard/web/frontend/src/components/PipelineStatus.jsx
export default function PipelineStatus({ analysis, strategy }) {
  const analysts = analysis?.analysts || ['market', 'social', 'news', 'fundamentals'];
  const debateRounds = analysis?.max_debate_rounds || 1;
  const riskRounds = analysis?.max_risk_discuss_rounds || 1;

  const tiers = [
    { label: 'Tier 1: Analysts', detail: analysts.join(', '), color: 'var(--accent)' },
    { label: 'Tier 2: Bull/Bear Debate', detail: `${debateRounds} round${debateRounds > 1 ? 's' : ''}`, color: 'var(--success)' },
    { label: 'Tier 3: Judge + Trader + Risk', detail: `${riskRounds} round${riskRounds > 1 ? 's' : ''} (agg → cons → neutral)`, color: 'var(--warning)' },
    { label: 'Tier 4: Portfolio Manager', detail: 'Final BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL', color: 'var(--danger)' },
  ];

  return (
    <div className="space-y-2">
      {tiers.map((tier, i) => (
        <div
          key={i}
          className="flex items-center gap-3 px-3 py-2 rounded-lg"
          style={{ backgroundColor: 'var(--bg-secondary)' }}
        >
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: tier.color }}
          />
          <div>
            <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {tier.label}
            </div>
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {tier.detail}
            </div>
          </div>
        </div>
      ))}
      <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
        Strategy: <strong>{strategy || 'default'}</strong> | Timeout: {analysis?.agent_timeout_seconds || 300}s per agent
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create RiskPanel**

```jsx
// dashboard/web/frontend/src/components/RiskPanel.jsx
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

## Task 6: Frontend — TradingMonitor Page

**Files:**
- Create: `dashboard/web/frontend/src/pages/TradingMonitor.jsx`

- [ ] **Step 1: Create the main page**

```jsx
// dashboard/web/frontend/src/pages/TradingMonitor.jsx
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
    <div
      className="rounded-xl border p-5"
      style={{ backgroundColor: 'var(--bg-primary)', borderColor: 'var(--border)' }}
    >
      {title && (
        <h3 className="text-base font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}

const PHASE_LABELS = {
  pre: 'Pre-Session',
  open: 'Market Open',
  midday: 'Midday',
  close: 'Near Close',
  post: 'Post-Session',
  closed: 'Market Closed',
};

export default function TradingMonitor() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api('/api/trading/status');
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // refresh every 30s
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p style={{ color: 'var(--text-secondary)' }}>Loading trading status...</p>
      </div>
    );
  }

  const s = status || {};
  const phase = PHASE_LABELS[s.market_phase] || s.market_phase || 'Unknown';
  const halted = s.state === 'halted';

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
            Trading Monitor
          </h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            {s.strategy?.toUpperCase()} strategy | Market: {phase}
          </p>
        </div>
        <HaltSwitch halted={halted} onToggle={() => fetchStatus()} />
      </div>

      {error && <ErrorBanner message={error} type="error" onDismiss={() => setError(null)} />}

      {/* Top row: Bias + Last Run */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Market Bias">
          <BiasControl
            bias={s.bias}
            onUpdate={(bias) => setStatus((prev) => ({ ...prev, bias }))}
          />
        </Card>

        <Card title="Last Run">
          {s.last_run ? (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {s.last_run.ticker}
                </span>
                {s.last_run.signal && <SignalBadge signal={s.last_run.signal} />}
              </div>
              <div className="text-xs space-y-0.5" style={{ color: 'var(--text-secondary)' }}>
                <div>Date: {s.last_run.trade_date}</div>
                <div>Strategy: {s.last_run.strategy}</div>
                <div>Duration: {s.last_run.duration_seconds?.toFixed(1)}s</div>
                <div>Status: {s.last_run.status}</div>
              </div>
            </div>
          ) : (
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>No runs yet</p>
          )}
        </Card>
      </div>

      {/* Watchlist */}
      <Card title="Watchlist">
        <WatchlistPanel
          watchlist={s.watchlist}
          onUpdate={(wl) => {
            // Refetch full status to get signal data for new tickers
            fetchStatus();
          }}
        />
      </Card>

      {/* Bottom row: Pipeline + Risk */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Pipeline Configuration">
          <PipelineStatus analysis={s.analysis} strategy={s.strategy} />
        </Card>

        <Card title="Risk Parameters">
          <RiskPanel risk={s.risk} jadecap={s.jadecap} />
        </Card>
      </div>

      {/* Memory stats */}
      {s.memory_stats && s.memory_stats.length > 0 && (
        <Card title="Memory Stats">
          <div className="flex flex-wrap gap-3">
            {s.memory_stats.map(({ agent, count }) => (
              <div
                key={agent}
                className="px-3 py-1.5 rounded-lg text-xs"
                style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
              >
                <span className="font-medium">{agent}</span>
                <span style={{ color: 'var(--text-secondary)' }}> ({count})</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* LLM Config summary */}
      <Card title="LLM Configuration">
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Default</div>
            <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{s.llm?.default || 'gpt-4o'}</div>
          </div>
          <div className="px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Deep Think</div>
            <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{s.llm?.deep_think || 'claude-opus-4-6'}</div>
          </div>
          <div className="px-3 py-2 rounded-lg" style={{ backgroundColor: 'var(--bg-secondary)' }}>
            <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>Quick Think</div>
            <div className="font-medium" style={{ color: 'var(--text-primary)' }}>{s.llm?.quick_think || 'gpt-4o-mini'}</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/web/frontend/src/pages/TradingMonitor.jsx
git commit -m "feat: add TradingMonitor page with full trading dashboard"
```

---

## Task 7: Wire Into App — Route + Navigation

**Files:**
- Modify: `dashboard/web/frontend/src/App.jsx`
- Modify: `dashboard/web/frontend/src/components/Layout.jsx`

- [ ] **Step 1: Add route in App.jsx**

Change `App.jsx` to:

```jsx
import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import LiveRun from './pages/LiveRun';
import RunDetails from './pages/RunDetails';
import CompareView from './pages/CompareView';
import Memories from './pages/Memories';
import Settings from './pages/Settings';
import TradingMonitor from './pages/TradingMonitor';

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

- [ ] **Step 2: Add nav link in Layout.jsx**

Change `navLinks` to:

```jsx
const navLinks = [
  { to: '/', label: 'Dashboard' },
  { to: '/trading', label: 'Trading' },
  { to: '/memories', label: 'Memories' },
  { to: '/settings', label: 'Settings' },
];
```

Also change the header title from `TradingAgents` to `OpenClaw`:

```jsx
<h1 className="text-lg font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
  OpenClaw
</h1>
```

- [ ] **Step 3: Rebuild frontend**

```bash
cd dashboard/web/frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/web/frontend/src/App.jsx dashboard/web/frontend/src/components/Layout.jsx dashboard/web/frontend/dist/
git commit -m "feat: wire TradingMonitor page into navigation + rebuild"
```

---

## Task 8: Update Plan Document

**Files:**
- Modify: `docs/superpowers/plans/2026-03-27-openclaw-tradingagents-merge.md`

- [ ] **Step 1: Add Phase 10 section** to the plan covering all new files and functions:

Append to the plan:

```markdown
## Phase 10: WebUI Trading Monitor (added 2026-03-29)

### New Files
- `dashboard/web/backend/routes/trading.py` — 5 endpoints:
  - `GET /api/trading/status` — full trading state (config + DB + market phase)
  - `PUT /api/trading/bias` — update bias direction/reason/confidence
  - `PUT /api/trading/halt` — toggle halt state
  - `PUT /api/trading/watchlist` — add/remove/set tickers
  - `PUT /api/trading/risk` — update risk parameters
- `dashboard/web/frontend/src/pages/TradingMonitor.jsx` — main page with 7 cards
- `dashboard/web/frontend/src/components/HaltSwitch.jsx` — halt/resume toggle button
- `dashboard/web/frontend/src/components/BiasControl.jsx` — bias direction/confidence/reason
- `dashboard/web/frontend/src/components/WatchlistPanel.jsx` — ticker table with signals
- `dashboard/web/frontend/src/components/PipelineStatus.jsx` — 4-tier pipeline visualization
- `dashboard/web/frontend/src/components/RiskPanel.jsx` — risk parameters grid

### Modified Files
- `dashboard/web/frontend/src/App.jsx` — add /trading route
- `dashboard/web/frontend/src/components/Layout.jsx` — add "Trading" nav link, rename to "OpenClaw"
- `dashboard/web/backend/app.py` — register trading router
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-03-27-openclaw-tradingagents-merge.md
git commit -m "docs: add Phase 10 (WebUI Trading Monitor) to plan"
```

---

## Summary

| Task | Creates | Modifies |
|------|---------|----------|
| 1. Backend endpoints | `routes/trading.py` | `app.py` |
| 2. HaltSwitch | `HaltSwitch.jsx` | — |
| 3. BiasControl | `BiasControl.jsx` | — |
| 4. WatchlistPanel | `WatchlistPanel.jsx` | — |
| 5. Pipeline + Risk | `PipelineStatus.jsx`, `RiskPanel.jsx` | — |
| 6. TradingMonitor page | `TradingMonitor.jsx` | — |
| 7. Wire route + nav | — | `App.jsx`, `Layout.jsx` |
| 8. Update plan | — | plan .md |
| **Total** | **7 new files** | **4 modified files** |
