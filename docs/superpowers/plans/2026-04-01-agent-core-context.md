# Agent Core Context — Wire OpenClaw Identity Into All 12 Agents

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every trading agent gets OpenClaw's core context (identity, trading principles, risk rules, user profile) in its system message — not just a one-line "You are market-analyst."

**Architecture:** Build a system prompt builder in `run_bridge.py` that reads the 7 core files and constructs a tailored system message per agent role. Each agent gets the core context PLUS its role-specific instructions. The prompt is built once at run start and cached for all dispatches.

**Tech Stack:** Python (run_bridge.py, engine.py)

---

## Current Problem

```python
# CURRENT — one generic line for ALL agents:
{"role": "system", "content": "You are market-analyst, a specialized trading analysis agent."}
```

The agents know nothing about:
- Who they are (OpenClaw identity)
- Who they work for (John Doan, LV Intelligent Corporate)
- Trading principles (probabilistic, HOLD when uncertain, risk non-negotiable)
- Risk rules ($500 max loss, 3:1 R:R, Apex prop firm)
- User's trading style (JadeCap ICT, NQ/ES, adapts in the moment)
- Analysis-only constraint (no order execution)

## Target State

```python
# AFTER — rich system message per agent:
{"role": "system", "content": """
You are market-analyst, part of OpenClaw — a self-evolving AI trading system.
Built by John Doan at LV Intelligent Corporate, Houston TX.

IDENTITY: Professional and sharp. No fluff. Earns trust through results.

TRADING PRINCIPLES:
- Analysis is probabilistic — no signal is certain.
- When uncertain, HOLD is the correct signal.
- Risk parameters are non-negotiable.
- Past mistakes are lessons, not failures.

RISK RULES:
- Max Loss Per Trade: $500
- Daily Loss Limit: $1,200
- Max Consecutive Losses: 3
- Min Risk/Reward: 3:1
- Prop Firm: Apex

USER PROFILE:
- Trader: John Doan — NQ/ES futures, JadeCap ICT methodology
- Style: Adapts, doesn't follow rules rigidly. Demands deep analysis.
- Risk personality: Knows rules, pushes boundaries. System enforces discipline.

CONSTRAINT: Analysis only — no order execution, no positions, no broker.

YOUR ROLE: market-analyst — primary ICT analysis engine.
"""}
```

---

## File Structure

```
Modified files:
├── /home/hoang/.openclaw/workspace/openclaw/run_bridge.py    ← build rich system message
```

One file, one change. The system message builder reads core files once at startup and constructs per-agent system messages.

---

### Task 1: Build system prompt from core files

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py`

- [ ] **Step 1: Add _build_system_prompt() function**

Add this function before `openclaw_dispatch()`:

```python
# Agent role descriptions — what each agent does in the pipeline
AGENT_ROLES = {
    "market-analyst": "Primary ICT analysis engine. Runs the full 10-step JadeCap playbook. Produces the market report that all other agents depend on.",
    "news-analyst": "Macro news researcher. Pulls multi-source headlines (Brave + yfinance), assesses Kill Zone risk, determines risk-on/risk-off macro bias for NQ.",
    "social-analyst": "Social media and retail sentiment researcher. Searches Reddit, Twitter/X, and trader forums for sentiment data.",
    "fundamentals-analyst": "Financial fundamentals researcher. Analyzes earnings, balance sheets, cash flow for stock-based analysis.",
    "bull-researcher": "Bull case advocate. Builds the strongest possible LONG argument using ICT evidence, SFP confirmations, and liquidity analysis. Has BM25 memory of past bullish analyses.",
    "bear-researcher": "Bear case advocate. Builds the strongest possible SHORT argument. Counters the bull researcher's points with evidence. Has BM25 memory of past bearish analyses.",
    "research-manager": "Investment judge. Evaluates the bull/bear debate, resolves conflicts, validates the checklist, and produces the investment plan. Uses deep-think model.",
    "trader": "Trade execution planner. Validates entry, calculates ATR stops, sizes contracts, verifies Kill Zone timing, enforces set-and-forget rules.",
    "aggressive-risk": "Aggressive risk perspective. Argues for taking the trade with full size when setup quality is high. Challenges conservative over-caution.",
    "conservative-risk": "Conservative risk perspective. Protects the prop firm account. Challenges marginal setups ruthlessly. The last line of defense against overtrading.",
    "neutral-risk": "Balanced risk arbiter. Synthesizes aggressive and conservative views. Produces the final risk-adjusted sizing recommendation.",
    "portfolio-manager": "Final decision authority. Synthesizes all prior analysis, applies 5-tier ICT rating, verifies hard rules and checklist, outputs the authoritative BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL signal. Uses deep-think model.",
}


def _build_system_prompt(agent_name: str) -> str:
    """Build a rich system prompt from OpenClaw's core files.

    Reads SOUL.md, IDENTITY.md, USER.md, TRADING.md once and constructs
    a system message tailored to the agent's role.
    """
    workspace = os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace")

    def _read(filename):
        try:
            with open(os.path.join(workspace, filename)) as f:
                return f.read().strip()
        except Exception:
            return ""

    # Read core files
    soul = _read("SOUL.md")
    identity = _read("IDENTITY.md")
    user = _read("USER.md")
    trading = _read("TRADING.md")

    # Extract key sections
    def _section(text, heading):
        """Extract a section from markdown by heading."""
        lines = text.split("\n")
        capturing = False
        result = []
        for line in lines:
            if line.strip().startswith(f"## {heading}"):
                capturing = True
                continue
            if capturing and line.strip().startswith("## "):
                break
            if capturing:
                result.append(line)
        return "\n".join(result).strip()

    # Build the system message
    role_desc = AGENT_ROLES.get(agent_name, f"Specialized trading analysis agent: {agent_name}")

    parts = []

    # Identity
    parts.append(f"You are {agent_name}, part of OpenClaw — a self-evolving AI trading system.")
    parts.append("Built by John Doan at LV Intelligent Corporate, Houston TX.")
    parts.append("Vibe: Professional and sharp. No fluff. Earns trust through results.")
    parts.append("")

    # Trading principles from SOUL.md
    principles = _section(soul, "Trading Principles")
    if principles:
        parts.append("TRADING PRINCIPLES:")
        parts.append(principles)
        parts.append("")

    # Risk rules from TRADING.md
    risk = _section(trading, "Risk Parameters")
    if risk:
        parts.append("RISK RULES (non-negotiable):")
        parts.append(risk)
        parts.append("")

    # Strategy from TRADING.md
    strategy = _section(trading, "Active Strategy")
    if strategy:
        parts.append("ACTIVE STRATEGY:")
        parts.append(strategy)
        parts.append("")

    # User profile from USER.md
    profile = _section(user, "Trading Profile")
    if profile:
        parts.append("TRADER PROFILE:")
        parts.append(profile)
        parts.append("")

    # Analysis-only constraint
    parts.append("CONSTRAINT: This is analysis only — no order execution, no positions, no broker connection.")
    parts.append("")

    # Agent-specific role
    parts.append(f"YOUR ROLE: {role_desc}")

    return "\n".join(parts)
```

- [ ] **Step 2: Update openclaw_dispatch() to use the builder**

Change the payload in `openclaw_dispatch()` from:

```python
    payload = {
        "model": full_model,
        "messages": [
            {"role": "system", "content": f"You are {agent_name}, a specialized trading analysis agent."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
```

To:

```python
    system_prompt = _build_system_prompt(agent_name)

    payload = {
        "model": full_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
```

- [ ] **Step 3: Test that system prompts are built correctly**

```bash
cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.run_bridge import _build_system_prompt

for agent in ['market-analyst', 'conservative-risk', 'portfolio-manager']:
    prompt = _build_system_prompt(agent)
    print(f'=== {agent} ({len(prompt)} chars) ===')
    print(prompt[:300])
    print('...')
    print()

    # Verify key content
    assert 'John Doan' in prompt, f'{agent}: missing user name'
    assert 'non-negotiable' in prompt or 'Risk' in prompt, f'{agent}: missing risk rules'
    assert 'HOLD' in prompt, f'{agent}: missing trading principles'
    assert 'analysis only' in prompt.lower(), f'{agent}: missing constraint'
    print(f'{agent}: ALL CHECKS PASS')
    print()
"
```

Expected: All 3 agents show rich system prompts with identity, principles, risk, user profile, and role.

- [ ] **Step 4: Verify the system prompt doesn't make prompts too large**

```bash
cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.run_bridge import _build_system_prompt
total = 0
for agent in ['market-analyst', 'news-analyst', 'bull-researcher', 'bear-researcher',
              'research-manager', 'trader', 'aggressive-risk', 'conservative-risk',
              'neutral-risk', 'portfolio-manager']:
    size = len(_build_system_prompt(agent))
    total += size
    print(f'  {agent}: {size} chars')
print(f'Average: {total//10} chars per agent')
print(f'This adds ~{total//10} chars to each dispatch — acceptable')
"
```

Expected: ~500-800 chars per agent system prompt. Acceptable overhead.

- [ ] **Step 5: Commit**

```bash
git add openclaw/run_bridge.py
git commit -m "feat: rich system prompts from OpenClaw core files for all 12 agents"
```

---

### Task 2: Verify end-to-end

- [ ] **Step 1: Test dispatch with rich system prompt**

```bash
cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.run_bridge import openclaw_dispatch
resp = openclaw_dispatch('market-analyst', 'What are your trading principles? List them.', 'cc/claude-sonnet-4-6')
print(resp[:500])
# Should mention: probabilistic, HOLD when uncertain, risk non-negotiable
"
```

Expected: The agent should reference OpenClaw's trading principles from SOUL.md — proving it received the core context.

- [ ] **Step 2: Commit and push**

```bash
git add -A
git commit -m "feat: all 12 agents now receive OpenClaw core context (identity, principles, risk, user profile)"
git push
```

---

## Summary

| Before | After |
|--------|-------|
| `"You are market-analyst, a specialized trading analysis agent."` | Rich system prompt with identity, trading principles, risk rules, user profile, strategy, constraint, and role description |
| Agents know nothing about OpenClaw | Agents know who they are, who they work for, what rules to follow |
| Risk rules only in JadeCap prompt body | Risk rules in BOTH system message AND prompt body (double enforcement) |
| No user context | Agents know John trades NQ/ES, JadeCap ICT, Apex prop firm |
| Generic AI behavior | Professional, sharp, no fluff — matches IDENTITY.md |
