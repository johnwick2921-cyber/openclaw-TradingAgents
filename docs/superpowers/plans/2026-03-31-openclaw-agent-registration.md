# OpenClaw Agent Registration — Wire 12 Trading Agents Through OpenClaw

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register all 12 trading agents in OpenClaw's agent system so they're dispatched through OpenClaw (not bypassing it). OpenClaw is the brain — RunEngine orchestrates, OpenClaw dispatches.

**Architecture:** Register 12 agents in `openclaw.json`. Change `run_bridge.py` dispatch to call OpenClaw's `/v1/chat/completions` endpoint (port 18789) instead of 9router directly (port 20128). OpenClaw's gateway already routes to 9router via the `9router` model provider. This makes OpenClaw the single dispatch point — auth, model routing, session management, and logging all go through OpenClaw.

**Tech Stack:** JSON config (openclaw.json), Python (run_bridge.py)

---

## Current State

```
UI → Gateway (18789) → Python subprocess → 9router (20128) → AI
                                           ↑ BYPASS — skips OpenClaw
```

## Target State

```
UI → Gateway (18789) → Python subprocess → OpenClaw Gateway (18789) → 9router (20128) → AI
                                           ↑ OpenClaw is the dispatcher
```

The RunEngine's `dispatch_fn` calls OpenClaw's `/v1/chat/completions` on port 18789. OpenClaw uses the `9router` model provider config to route to 9router. All 12 agents are registered in openclaw.json so OpenClaw tracks them.

---

## File Structure

```
Modified files:
├── /home/hoang/.openclaw/openclaw.json                         ← register 12 agents
├── /home/hoang/.openclaw/workspace/openclaw/run_bridge.py      ← dispatch via OpenClaw gateway
```

---

## Task 1: Register 12 trading agents in openclaw.json

**Files:**
- Modify: `/home/hoang/.openclaw/openclaw.json`

- [ ] **Step 1: Add all 12 trading agents to agents.list**

In `openclaw.json`, the `agents.list` array currently has 2 entries (`main`, `trading-monitor`). Add 12 more entries — one per trading subagent. Each agent gets:
- `id`: matches the .md filename (e.g. `market-analyst`)
- `model`: the model tier from frontmatter — `9router/cc/claude-sonnet-4-6` for `tier: quick`, `9router/cc/claude-opus-4-6` for `tier: deep`
- `tools.profile`: `"trading"` (or `"full"` if trading profile doesn't exist)

The full agents.list should be:

```json
"list": [
  {
    "id": "main",
    "model": "9router/cc/claude-opus-4-6",
    "tools": { "profile": "full" }
  },
  {
    "id": "trading-monitor",
    "model": "9router/cc/claude-opus-4-6",
    "tools": { "profile": "full" }
  },
  { "id": "market-analyst", "tools": { "profile": "full" } },
  { "id": "social-analyst", "tools": { "profile": "full" } },
  { "id": "news-analyst", "tools": { "profile": "full" } },
  { "id": "fundamentals-analyst", "tools": { "profile": "full" } },
  { "id": "bull-researcher", "tools": { "profile": "full" } },
  { "id": "bear-researcher", "tools": { "profile": "full" } },
  { "id": "research-manager", "model": "9router/cc/claude-opus-4-6", "tools": { "profile": "full" } },
  { "id": "trader", "tools": { "profile": "full" } },
  { "id": "aggressive-risk", "tools": { "profile": "full" } },
  { "id": "conservative-risk", "tools": { "profile": "full" } },
  { "id": "neutral-risk", "tools": { "profile": "full" } },
  { "id": "portfolio-manager", "model": "9router/cc/claude-opus-4-6", "tools": { "profile": "full" } }
]
```

Note: Agents without an explicit `model` inherit from `agents.defaults.model.primary`. Only `research-manager` and `portfolio-manager` get explicit deep-think model overrides (they use `tier: deep` in their frontmatter).

- [ ] **Step 2: Verify openclaw.json is valid JSON**

Run: `python3 -c "import json; json.load(open('/home/hoang/.openclaw/openclaw.json')); print('VALID')"`
Expected: `VALID`

- [ ] **Step 3: Restart gateway to pick up new agent list**

Run: `systemctl --user restart openclaw-gateway && sleep 2 && systemctl --user status openclaw-gateway | head -3`
Expected: `active (running)`

- [ ] **Step 4: Verify agents are visible**

Run: Open http://127.0.0.1:18789/ → Agent Settings. Should see 14 agents (main + trading-monitor + 12 trading).

- [ ] **Step 5: Commit**

```bash
cd /home/hoang/.openclaw
git add openclaw.json
git commit -m "feat: register 12 trading agents in OpenClaw agent system"
```

---

## Task 2: Rewire run_bridge.py dispatch through OpenClaw gateway

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py`

- [ ] **Step 1: Change ROUTER_URL to point at OpenClaw gateway instead of 9router**

Replace the dispatch function to call OpenClaw's `/v1/chat/completions` on port 18789 instead of 9router on port 20128. OpenClaw's gateway already has the `9router` provider configured — it will route the model ID `cc/claude-sonnet-4-6` through `9router` automatically.

Change `ROUTER_URL` from:
```python
ROUTER_URL = "http://127.0.0.1:{port}/v1/chat/completions"
```

And in `openclaw_dispatch`, change:
```python
port = int(os.environ.get("NINE_ROUTER_PORT", "20128"))
api_key = os.environ.get("NINE_ROUTER_API_KEY", "")
# ... .env loading for NINE_ROUTER_API_KEY ...
```

To:
```python
port = int(os.environ.get("OPENCLAW_GATEWAY_PORT", "18789"))
token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

# Read token from openclaw.json if not in env
if not token:
    try:
        oc_path = os.path.join(
            os.environ.get("HOME", "/home/hoang"),
            ".openclaw", "openclaw.json",
        )
        with open(oc_path) as f:
            oc = json.load(f)
        token = oc.get("gateway", {}).get("auth", {}).get("token", "")
    except Exception:
        pass
```

And the model ID needs the `9router/` prefix when calling OpenClaw:
```python
payload = {
    "model": f"9router/{model}" if not model.startswith("9router/") else model,
    "messages": [
        {"role": "system", "content": f"You are {agent_name}, a specialized trading analysis agent."},
        {"role": "user", "content": prompt},
    ],
    "stream": False,
}
```

And the error message:
```python
except requests.exceptions.ConnectionError:
    raise RuntimeError(
        f"Cannot connect to OpenClaw gateway at {url}. "
        "Is the gateway running? (systemctl --user status openclaw-gateway)"
    )
```

- [ ] **Step 2: Test the dispatch works through OpenClaw**

Run: `cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.run_bridge import openclaw_dispatch
resp = openclaw_dispatch('test', 'Reply OPENCLAW_OK only', 'cc/claude-sonnet-4-6')
print('Response:', resp[:50])
assert 'OPENCLAW_OK' in resp or len(resp) > 0
print('PASS')
"`
Expected: AI response through OpenClaw gateway.

- [ ] **Step 3: Commit**

```bash
cd /home/hoang/.openclaw/workspace
git add openclaw/run_bridge.py
git commit -m "feat: route trading dispatch through OpenClaw gateway instead of direct 9router"
```

---

## Task 3: Verify end-to-end flow

- [ ] **Step 1: Verify the full chain**

Run: `cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.run_bridge import openclaw_dispatch
# This should go: Python → OpenClaw (18789) → 9router (20128) → Claude
resp = openclaw_dispatch('market-analyst', 'Analyze NVDA. Reply with: FLOW_OK', 'cc/claude-sonnet-4-6')
print('Chain: Python → OpenClaw → 9router → Claude')
print('Response:', resp[:80])
print('PASS' if len(resp) > 0 else 'FAIL')
"`

- [ ] **Step 2: Verify agent list in UI**

Open http://127.0.0.1:18789/ → check that Agent Settings shows all 14 agents.

- [ ] **Step 3: Verify trading models dropdown**

Open Trading tab → LLM Config → verify dropdowns show 9router models.

---

## Summary

| Before | After |
|--------|-------|
| 2 agents in openclaw.json | 14 agents (2 + 12 trading) |
| run_bridge → 9router directly | run_bridge → OpenClaw gateway → 9router |
| OpenClaw is a UI shell | OpenClaw is the dispatcher |
| Trading bypasses OpenClaw | Trading goes through OpenClaw |

**After completion:** Every AI call from the trading pipeline flows through OpenClaw's gateway. OpenClaw tracks all 12 agents. Model routing, auth, and logging are unified. OpenClaw is the brain.
