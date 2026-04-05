# Pipeline Speed Optimization Plan

**Date:** 2026-04-03
**Goal:** Reduce full NQ analysis from ~23 minutes to ~12 minutes using Opus 4.6 for ALL agents
**Strategy:** Trim system prompts (22K -> 7K tokens), optimize bear input, add token logging

## Current Timing Breakdown

| Tier | Agents | Duration | Notes |
|------|--------|----------|-------|
| Prefetch | data fetchers | 24s | Already fast |
| Tier 1 | market + news (parallel) | 168s | Already parallel |
| Tier 2 | bull 164s + bear 445s | 609s | Bear is bottleneck |
| Tier 3 | research-mgr + trader + risk | 436s | Risk agents now parallel |
| Tier 4 | portfolio-manager | 165s | Sequential, required |
| **TOTAL** | | **~1400s** | **~23 minutes** |

## Expected After Optimization

| Tier | Before | After | Savings |
|------|--------|-------|---------|
| Tier 1 | 168s | 100s | -68s (smaller system prompt) |
| Tier 2 | 609s | 280s | -329s (trimmed prompts + bear input trim) |
| Tier 3 | 436s | 260s | -176s (trimmed prompts + parallel risk) |
| Tier 4 | 165s | 100s | -65s (trimmed prompt) |
| **TOTAL** | **1400s** | **~740s** | **~660s saved (~47%)** |

---

## Feature 1: Trim System Prompts -- Remove Non-Trading Content

Each trading agent currently gets ~22K tokens of system prompt built from 7 core files. Most of this content (group chat rules, heartbeat email checks, Discord reactions, memory maintenance, bootstrap protocol) is irrelevant to a trading subagent that exists for a single dispatch call.

### Step 1.1: Create AGENTS_TRADING.md template

- [ ] Create `/home/hoang/.openclaw/workspace/agents/trading/_templates/AGENTS_TRADING.md`

This replaces the 248-line AGENTS.md with a ~50-line trading-only version for all 12 trading agents.

```markdown
# AGENTS.md - Trading Subagent Protocol

## Your Role

You are a specialized trading subagent in OpenClaw's 12-agent pipeline.
You receive data, apply your analysis, and produce structured output.
You exist for ONE dispatch call -- no session continuity, no memory files, no heartbeats.

## Pipeline

```
Tier 1: Analysts (parallel)     -> market, news, social, fundamentals
Tier 2: Bull/Bear Debate        -> N rounds, each counters the prior
Tier 3: Judge + Trader + Risk   -> research-manager -> trader -> 3 risk agents (parallel)
Tier 4: Portfolio Manager       -> BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL
```

## How You Operate

1. Receive pre-fetched tool data and prior tier reports in your prompt
2. Apply your analysis methodology (defined in PROMPT.md)
3. Factor in trader's pre-session bias and confluence context
4. Output your analysis in the specified format
5. Your output flows to the next tier in the pipeline

## Red Lines

- Never fabricate data. If a tool failed, say "data unavailable."
- Never contradict the hard rules in TRADING.md.
- Analysis only -- never suggest order execution.
- If uncertain, lean toward HOLD / caution / reduced size.
- Never hide uncertainty behind confident language.
- Don't exfiltrate private data. Ever.

## Output Rules

- Be specific: use exact price levels, not vague ranges
- Be concise: quality analysis, not volume
- Be honest: if the data doesn't support a thesis, say so
- Follow the output format in your PROMPT.md exactly
```

### Step 1.2: Create TOOLS_TRADING.md template

- [ ] Create `/home/hoang/.openclaw/workspace/agents/trading/_templates/TOOLS_TRADING.md`

This replaces the 96-line TOOLS.md (with camera, SSH, TTS info) with a ~30-line trading-only version.

```markdown
# TOOLS.md - Trading Tools

## Dispatch Flow

RunEngine -> OpenClaw Gateway (18789) -> 9router (20128) -> AI Provider

## Available Data Tools

| Tool | Description |
|------|-------------|
| `get_stock_data` | OHLCV price data via yfinance |
| `get_indicators` | 13 stockstats indicators (RSI, MACD, BB, SMA, EMA, ATR) |
| `get_ict_levels` | 17 ICT/SMC indicators (FVG, OB, BOS, CHoCH, liquidity) |
| `get_fundamentals` | Company fundamentals overview |
| `get_news` | Ticker-specific news |
| `get_global_news` | Macro/global market news |
| `fetch_live_price` | Current live price (Databento -> yfinance fallback) |
| `get_killzone_status_tool` | Current ICT kill zone status |

## Note

You do not call tools directly. The RunEngine prefetches all data
and injects it into your prompt. Tool names in your frontmatter
tell the engine WHAT to fetch for you.
```

### Step 1.3: Create HEARTBEAT_TRADING.md template

- [ ] Create `/home/hoang/.openclaw/workspace/agents/trading/_templates/HEARTBEAT_TRADING.md`

Replaces the 28-line HEARTBEAT.md with a ~5-line stub.

```markdown
# HEARTBEAT.md

Trading subagents do not run heartbeats.
Heartbeats are handled by the main OpenClaw agent only.
```

### Step 1.4: Deploy trimmed files to all 12 agent directories

- [ ] Run deployment script

```bash
#!/bin/bash
# Deploy trimmed system prompt files to all 12 trading agents
AGENTS_DIR="/home/hoang/.openclaw/workspace/agents/trading"
TEMPLATES_DIR="$AGENTS_DIR/_templates"

for agent in market-analyst news-analyst social-analyst fundamentals-analyst \
             bull-researcher bear-researcher research-manager trader \
             aggressive-risk conservative-risk neutral-risk portfolio-manager; do
    # Backup originals
    cp "$AGENTS_DIR/$agent/AGENTS.md" "$AGENTS_DIR/$agent/AGENTS.md.bak"
    cp "$AGENTS_DIR/$agent/TOOLS.md" "$AGENTS_DIR/$agent/TOOLS.md.bak"
    cp "$AGENTS_DIR/$agent/HEARTBEAT.md" "$AGENTS_DIR/$agent/HEARTBEAT.md.bak"

    # Deploy trimmed versions
    cp "$TEMPLATES_DIR/AGENTS_TRADING.md" "$AGENTS_DIR/$agent/AGENTS.md"
    cp "$TEMPLATES_DIR/TOOLS_TRADING.md" "$AGENTS_DIR/$agent/TOOLS.md"
    cp "$TEMPLATES_DIR/HEARTBEAT_TRADING.md" "$AGENTS_DIR/$agent/HEARTBEAT.md"

    echo "Deployed to $agent"
done
```

### Step 1.5: Preserve per-agent protocol sections

Each agent's current AGENTS.md has a custom `## Protocol -- {agent-name}` section at the bottom. This section MUST be preserved.

- [ ] For each agent, extract the `## Protocol -- {agent-name}` section from the `.bak` file and append it to the new AGENTS.md

```bash
#!/bin/bash
AGENTS_DIR="/home/hoang/.openclaw/workspace/agents/trading"

for agent in market-analyst news-analyst social-analyst fundamentals-analyst \
             bull-researcher bear-researcher research-manager trader \
             aggressive-risk conservative-risk neutral-risk portfolio-manager; do
    BAK="$AGENTS_DIR/$agent/AGENTS.md.bak"
    TARGET="$AGENTS_DIR/$agent/AGENTS.md"

    if [ -f "$BAK" ]; then
        # Extract everything from "## Protocol" onward
        PROTOCOL=$(sed -n '/^## Protocol/,$p' "$BAK")
        if [ -n "$PROTOCOL" ]; then
            echo "" >> "$TARGET"
            echo "$PROTOCOL" >> "$TARGET"
        fi
    fi
done
```

### Verification

```bash
# Count lines in each agent's system prompt files (should be ~90 total, down from ~600)
for agent in market-analyst bear-researcher portfolio-manager; do
    echo "=== $agent ==="
    wc -l /home/hoang/.openclaw/workspace/agents/trading/$agent/{IDENTITY,SOUL,USER,AGENTS,TOOLS,HEARTBEAT,TRADING}.md
done
```

---

## Feature 2: Optimize _build_system_prompt

No code changes needed to the function itself -- it already reads from the agent directories. The token reduction comes entirely from the smaller files deployed in Feature 1.

However, we should add an optimization: skip empty/stub files entirely.

### Step 2.1: Skip stub files in _build_system_prompt

- [ ] Edit `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py`

In `_build_system_prompt`, after reading HEARTBEAT.md, skip it if it's a stub:

```python
# In _build_system_prompt, after line 113:
    heartbeat = _read_file(agent_dir, "HEARTBEAT.md")

# ADD: Skip stub heartbeat content
    if heartbeat and len(heartbeat) < 100:
        heartbeat = ""  # Don't waste tokens on stub heartbeat
```

**Find (line 113):**
```python
    heartbeat = _read_file(agent_dir, "HEARTBEAT.md")
```

**Replace with:**
```python
    heartbeat = _read_file(agent_dir, "HEARTBEAT.md")
    # Skip stub heartbeat (trading subagents don't use heartbeats)
    if heartbeat and "do not run heartbeats" in heartbeat.lower():
        heartbeat = ""
```

### Step 2.2: Log system prompt token count

- [ ] Edit `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py`

Add token estimation to `_build_system_prompt` return.

**Find (line 190):**
```python
    return "\n".join(parts)
```

**Replace with:**
```python
    result = "\n".join(parts)
    # Log system prompt size for optimization tracking
    token_est = len(result) // 4  # rough: 1 token ~ 4 chars
    logger.debug("System prompt for %s: ~%d tokens (%d chars)", agent_name, token_est, len(result))
    return result
```

Also add logger import at top of file. **Find (line 16):**
```python
from datetime import datetime, timezone
```

**Replace with:**
```python
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
```

### Verification

```bash
# Run a test dispatch and check log output
cd /home/hoang/.openclaw/workspace
PYTHONPATH=. python3 -c "
from openclaw.run_bridge import _build_system_prompt
import os
os.environ['OPENCLAW_WORKSPACE'] = '/home/hoang/.openclaw/workspace'
for agent in ['market-analyst', 'bear-researcher', 'portfolio-manager']:
    sp = _build_system_prompt(agent)
    tokens = len(sp) // 4
    print(f'{agent}: {tokens} tokens ({len(sp)} chars)')
"
# Expected: ~1750 tokens each (down from ~5500)
```

---

## Feature 3: Measure and Log Token Usage Per Agent

### Step 3.1: Add timing and token logging to openclaw_dispatch

- [ ] Edit `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py`

**Find (lines 193-246, the entire `openclaw_dispatch` function):**
```python
def openclaw_dispatch(agent_name: str, prompt: str, model: str) -> str:
    """Dispatch an agent prompt through OpenClaw's gateway.

    ALL agents go through OpenClaw (18789) → 9router (20128) → AI.
    Each agent gets a rich system prompt built from all 7 core files.
    """
    port, token = _get_gateway_auth()
    url = GATEWAY_URL.format(port=port)

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    full_model = f"9router/{model}" if not model.startswith("9router/") else model

    system_prompt = _build_system_prompt(agent_name)

    payload = {
        "model": full_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    import time as _time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=600)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
```

**Replace with:**
```python
# Module-level: track per-agent stats for summary
_dispatch_stats: list = []  # list of dicts: {agent, sys_tokens, user_tokens, resp_tokens, duration_s}


def openclaw_dispatch(agent_name: str, prompt: str, model: str) -> str:
    """Dispatch an agent prompt through OpenClaw's gateway.

    ALL agents go through OpenClaw (18789) -> 9router (20128) -> AI.
    Each agent gets a rich system prompt built from all 7 core files.
    Logs token usage and timing for each dispatch.
    """
    port, token = _get_gateway_auth()
    url = GATEWAY_URL.format(port=port)

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    full_model = f"9router/{model}" if not model.startswith("9router/") else model

    system_prompt = _build_system_prompt(agent_name)

    payload = {
        "model": full_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    import time as _time
    t0 = _time.monotonic()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=600)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Extract token usage from response (OpenAI-compatible format)
            usage = data.get("usage", {})
            sys_tokens = len(system_prompt) // 4  # estimate if not in usage
            user_tokens = len(prompt) // 4
            resp_tokens = usage.get("completion_tokens", len(content) // 4)
            prompt_tokens = usage.get("prompt_tokens", sys_tokens + user_tokens)
            duration_s = _time.monotonic() - t0

            stat = {
                "agent": agent_name,
                "model": full_model,
                "prompt_tokens": prompt_tokens,
                "sys_tokens_est": sys_tokens,
                "user_tokens_est": user_tokens,
                "resp_tokens": resp_tokens,
                "total_tokens": prompt_tokens + resp_tokens,
                "duration_s": round(duration_s, 1),
            }
            _dispatch_stats.append(stat)
            logger.info(
                "[%s] %s | prompt=%d resp=%d total=%d | %.1fs",
                agent_name, full_model, prompt_tokens, resp_tokens,
                prompt_tokens + resp_tokens, duration_s,
            )

            return content
```

### Step 3.2: Add summary printer

- [ ] Add to `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py` after the `openclaw_dispatch_parallel` function (after line 265):

```python
def print_dispatch_summary():
    """Print a summary of all dispatches in this run.

    Call this after engine.run() completes to see per-agent token usage and timing.
    """
    if not _dispatch_stats:
        print("No dispatch stats recorded.")
        return

    # Opus 4.6 pricing: $15/M input, $75/M output (as of 2026-04)
    INPUT_COST_PER_M = 15.0
    OUTPUT_COST_PER_M = 75.0

    total_prompt = 0
    total_resp = 0
    total_duration = 0.0

    print("\n" + "=" * 80)
    print(f"{'AGENT':<25} {'MODEL':<30} {'IN':>7} {'OUT':>7} {'TOTAL':>7} {'TIME':>7} {'COST':>7}")
    print("-" * 80)

    for s in _dispatch_stats:
        cost = (s["prompt_tokens"] / 1_000_000 * INPUT_COST_PER_M +
                s["resp_tokens"] / 1_000_000 * OUTPUT_COST_PER_M)
        print(f"{s['agent']:<25} {s['model']:<30} {s['prompt_tokens']:>7} {s['resp_tokens']:>7} "
              f"{s['total_tokens']:>7} {s['duration_s']:>6.1f}s ${cost:>5.3f}")
        total_prompt += s["prompt_tokens"]
        total_resp += s["resp_tokens"]
        total_duration += s["duration_s"]

    total_cost = (total_prompt / 1_000_000 * INPUT_COST_PER_M +
                  total_resp / 1_000_000 * OUTPUT_COST_PER_M)
    print("-" * 80)
    print(f"{'TOTAL':<25} {'':<30} {total_prompt:>7} {total_resp:>7} "
          f"{total_prompt + total_resp:>7} {total_duration:>6.1f}s ${total_cost:>5.3f}")
    print("=" * 80)
    print(f"Note: some agents ran in parallel, so wall time < sum of durations.")
    print(f"Pricing: Opus 4.6 @ ${INPUT_COST_PER_M}/M input, ${OUTPUT_COST_PER_M}/M output\n")


def clear_dispatch_stats():
    """Clear dispatch stats for a new run."""
    _dispatch_stats.clear()
```

### Step 3.3: Wire summary into run_bridge main

- [ ] Edit `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py`

**Find (lines 341-348):**
```python
        result = engine.run(
            ticker=args.ticker,
            date=args.date,
            dispatch_fn=openclaw_dispatch,
            dispatch_parallel_fn=openclaw_dispatch_parallel,
            callbacks=[jl_cb, print_cb],
            run_id=args.run_id,
        )
```

**Replace with:**
```python
        clear_dispatch_stats()
        result = engine.run(
            ticker=args.ticker,
            date=args.date,
            dispatch_fn=openclaw_dispatch,
            dispatch_parallel_fn=openclaw_dispatch_parallel,
            callbacks=[jl_cb, print_cb],
            run_id=args.run_id,
        )
        print_dispatch_summary()
```

### Step 3.4: Write stats to progress file

- [ ] Edit `JsonLinesCallback.on_run_complete` in `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py`

**Find (lines 295-304):**
```python
    def on_run_complete(self, result):
        if self._f.closed:
            return
        self._write({
            "event": "complete",
            "run_id": result.run_id,
            "signal": result.signal,
            "duration": result.duration_seconds,
        })
        self._f.close()
```

**Replace with:**
```python
    def on_run_complete(self, result):
        if self._f.closed:
            return
        self._write({
            "event": "complete",
            "run_id": result.run_id,
            "signal": result.signal,
            "duration": result.duration_seconds,
            "dispatch_stats": _dispatch_stats.copy() if _dispatch_stats else [],
        })
        self._f.close()
```

### Verification

```bash
# After a run, check the progress file for stats
tail -1 /tmp/run-*.jsonl | python3 -m json.tool | grep -A5 dispatch_stats
```

---

## Feature 4: Optimize Bear Researcher Input (445s -> ~200s)

The bear researcher is the slowest agent at 445s. Root cause: it receives ALL 4 analyst reports plus the full bull argument plus the full PROMPT.md (JadeCap prompt alone is ~275 lines). Total input is ~60K+ tokens.

### Step 4.1: Trim reports sent to bear (jadecap strategy)

In jadecap strategy, bear only needs market_report and news_report. Social and fundamentals are not relevant to futures ICT analysis.

- [ ] Edit `/home/hoang/.openclaw/workspace/openclaw/engine.py`

**Find (line 274, inside `_run_debate`):**
```python
        reports_context = self._format_reports(reports)
```

**Replace with:**
```python
        reports_context = self._format_reports(reports)
        # For jadecap strategy, trim reports for debate agents -- they only need market + news
        if strategy == "jadecap":
            debate_reports = {k: v for k, v in reports.items()
                             if k in ("market_report", "news_report")}
            debate_reports_context = self._format_reports(debate_reports)
        else:
            debate_reports_context = reports_context
```

Then update the two calls to `_build_researcher_prompt` to use `debate_reports_context`:

**Find (line 276):**
```python
            bull_prompt = self._build_researcher_prompt(agents_dir, "bull-researcher", strategy, ticker, date, reports_context, debate, "bull", reports=reports)
```

**Replace with:**
```python
            bull_prompt = self._build_researcher_prompt(agents_dir, "bull-researcher", strategy, ticker, date, debate_reports_context, debate, "bull", reports=reports)
```

**Find (line 289):**
```python
            bear_prompt = self._build_researcher_prompt(agents_dir, "bear-researcher", strategy, ticker, date, reports_context, debate, "bear", reports=reports)
```

**Replace with:**
```python
            bear_prompt = self._build_researcher_prompt(agents_dir, "bear-researcher", strategy, ticker, date, debate_reports_context, debate, "bear", reports=reports)
```

### Step 4.2: Trim opponent argument length for bear

Currently the bear sees `opponent_history[-2000:]` (last 2000 chars of bull argument). The same data is ALSO injected via `{current_response}` in the prompt template AND appended at the bottom as "Opponent's Last Argument". This is duplicate data.

- [ ] Edit `/home/hoang/.openclaw/workspace/openclaw/engine.py`

**Find (line 643, inside `_build_researcher_prompt`):**
```python
            "current_response": opponent_history[-2000:] if opponent_history else "",
```

**Replace with:**
```python
            "current_response": opponent_history[-1000:] if opponent_history else "",
```

**Find (line 664):**
```python
Opponent's Last Argument:
{opponent_history[-2000:] if opponent_history else 'No argument yet — you go first.'}
```

**Replace with:**
```python
Opponent's Last Argument (summary):
{opponent_history[-1000:] if opponent_history else 'No argument yet -- you go first.'}
```

### Step 4.3: Trim debate history injection

The full debate history grows with each round. For single-round debates (the default), this is manageable. But the `reports_context` is also appended at the bottom of the researcher prompt, duplicating what's already in `{market_report}`, `{news_report}`, etc. placeholders.

- [ ] Edit `/home/hoang/.openclaw/workspace/openclaw/engine.py`

In `_build_researcher_prompt`, the formatted prompt already contains the reports via placeholder substitution. The `reports_context` block at the end duplicates them. For jadecap strategy, skip the reports_context appendage since the template already embeds them.

**Find (lines 652-665):**
```python
        return f"""{prompt_text}
{user_bias}
{confluence}
Company/Instrument: {ticker}
Trade Date: {date}

{reports_context}

Debate History:
{debate['history']}

Opponent's Last Argument:
{opponent_history[-2000:] if opponent_history else 'No argument yet — you go first.'}
"""
```

**Replace with:**
```python
        # For jadecap, reports are already embedded in the prompt template via placeholders
        # Skip duplicating them in the suffix to reduce token count
        if strategy == "jadecap":
            reports_block = ""
        else:
            reports_block = f"\n{reports_context}\n"

        # Trim debate history to last 3000 chars to avoid token bloat
        trimmed_history = debate['history'][-3000:] if len(debate.get('history', '')) > 3000 else debate.get('history', '')

        return f"""{prompt_text}
{user_bias}
{confluence}
Company/Instrument: {ticker}
Trade Date: {date}
{reports_block}
Debate History:
{trimmed_history}

Opponent's Last Argument (summary):
{opponent_history[-1000:] if opponent_history else 'No argument yet -- you go first.'}
"""
```

### Step 4.4: Also pass trimmed reports dict for jadecap bear/bull

The `reports=reports` kwarg in `_build_researcher_prompt` is used for placeholder substitution. For jadecap, we should pass only market + news to avoid injecting unused report text.

- [ ] Edit `/home/hoang/.openclaw/workspace/openclaw/engine.py`

**Find (the bull_prompt line updated in 4.1):**
```python
            bull_prompt = self._build_researcher_prompt(agents_dir, "bull-researcher", strategy, ticker, date, debate_reports_context, debate, "bull", reports=reports)
```

**Replace with:**
```python
            debate_reports_dict = debate_reports if strategy == "jadecap" else reports
            bull_prompt = self._build_researcher_prompt(agents_dir, "bull-researcher", strategy, ticker, date, debate_reports_context, debate, "bull", reports=debate_reports_dict)
```

**Find (the bear_prompt line updated in 4.1):**
```python
            bear_prompt = self._build_researcher_prompt(agents_dir, "bear-researcher", strategy, ticker, date, debate_reports_context, debate, "bear", reports=reports)
```

**Replace with:**
```python
            bear_prompt = self._build_researcher_prompt(agents_dir, "bear-researcher", strategy, ticker, date, debate_reports_context, debate, "bear", reports=debate_reports_dict)
```

### Verification

```bash
# Run a jadecap analysis and check bear timing vs baseline
cd /home/hoang/.openclaw/workspace
python3 -m openclaw.run_bridge --ticker NQ --date 2026-04-03 --progress-file /tmp/run-speed-test.jsonl

# Check the dispatch summary for bear-researcher duration
# Expected: bear-researcher should be ~200s (down from 445s)
```

---

## Testing Checklist

### Unit Tests

- [ ] Verify `_build_system_prompt` produces ~7K tokens (not ~22K)
```bash
cd /home/hoang/.openclaw/workspace
PYTHONPATH=. python3 -c "
from openclaw.run_bridge import _build_system_prompt
import os
os.environ['OPENCLAW_WORKSPACE'] = '/home/hoang/.openclaw/workspace'
for agent in ['market-analyst', 'bear-researcher', 'portfolio-manager',
              'bull-researcher', 'trader', 'aggressive-risk']:
    sp = _build_system_prompt(agent)
    tokens = len(sp) // 4
    chars = len(sp)
    status = 'OK' if tokens < 3000 else 'TOO BIG'
    print(f'{agent}: {tokens} tokens ({chars} chars) [{status}]')
"
```

- [ ] Verify protocol sections preserved in AGENTS.md
```bash
for agent in market-analyst bear-researcher portfolio-manager; do
    echo "=== $agent ==="
    grep -c "Protocol" /home/hoang/.openclaw/workspace/agents/trading/$agent/AGENTS.md
done
# Expected: 1 match per agent (the Protocol section)
```

- [ ] Verify dispatch stats work
```bash
cd /home/hoang/.openclaw/workspace
PYTHONPATH=. python3 -c "
from openclaw.run_bridge import _dispatch_stats, print_dispatch_summary
_dispatch_stats.append({
    'agent': 'test-agent', 'model': '9router/cc/claude-opus-4-6',
    'prompt_tokens': 5000, 'sys_tokens_est': 1750, 'user_tokens_est': 3250,
    'resp_tokens': 2000, 'total_tokens': 7000, 'duration_s': 45.2
})
print_dispatch_summary()
"
```

### Integration Test

- [ ] Run full NQ analysis and compare timings
```bash
# Before optimization: save baseline
# After optimization: run and compare

cd /home/hoang/.openclaw/workspace
python3 -m openclaw.run_bridge --ticker NQ --date 2026-04-03 --progress-file /tmp/run-speed-test.jsonl

# Check results
python3 -c "
import json
with open('/tmp/run-speed-test.jsonl') as f:
    for line in f:
        event = json.loads(line)
        if event.get('event') == 'complete':
            print(f'Duration: {event[\"duration\"]:.0f}s')
            if 'dispatch_stats' in event:
                for s in event['dispatch_stats']:
                    print(f'  {s[\"agent\"]}: {s[\"duration_s\"]}s ({s[\"prompt_tokens\"]} in / {s[\"resp_tokens\"]} out)')
"
```

### Rollback

If anything breaks, restore original files:

```bash
AGENTS_DIR="/home/hoang/.openclaw/workspace/agents/trading"
for agent in market-analyst news-analyst social-analyst fundamentals-analyst \
             bull-researcher bear-researcher research-manager trader \
             aggressive-risk conservative-risk neutral-risk portfolio-manager; do
    for f in AGENTS.md TOOLS.md HEARTBEAT.md; do
        if [ -f "$AGENTS_DIR/$agent/$f.bak" ]; then
            cp "$AGENTS_DIR/$agent/$f.bak" "$AGENTS_DIR/$agent/$f"
        fi
    done
done
echo "Rolled back all agent files to originals"
```

For run_bridge.py and engine.py, use git:

```bash
cd /home/hoang/.openclaw/workspace
git diff openclaw/run_bridge.py openclaw/engine.py
git checkout openclaw/run_bridge.py openclaw/engine.py  # only if needed
```

---

## Implementation Order

1. **Feature 1** (Steps 1.1-1.5) -- Create templates, deploy, verify line counts
2. **Feature 2** (Steps 2.1-2.2) -- Edit run_bridge.py for stub skip + logging
3. **Feature 3** (Steps 3.1-3.4) -- Add dispatch stats, summary printer, wire into main
4. **Feature 4** (Steps 4.1-4.4) -- Trim bear input in engine.py
5. **Integration test** -- Full NQ run, compare to baseline

## Files Modified

| File | Changes |
|------|---------|
| `/home/hoang/.openclaw/workspace/agents/trading/_templates/AGENTS_TRADING.md` | NEW -- trimmed AGENTS template |
| `/home/hoang/.openclaw/workspace/agents/trading/_templates/TOOLS_TRADING.md` | NEW -- trimmed TOOLS template |
| `/home/hoang/.openclaw/workspace/agents/trading/_templates/HEARTBEAT_TRADING.md` | NEW -- stub HEARTBEAT template |
| `/home/hoang/.openclaw/workspace/agents/trading/*/AGENTS.md` | REPLACED -- trimmed + protocol section |
| `/home/hoang/.openclaw/workspace/agents/trading/*/TOOLS.md` | REPLACED -- trading-only tools |
| `/home/hoang/.openclaw/workspace/agents/trading/*/HEARTBEAT.md` | REPLACED -- stub |
| `/home/hoang/.openclaw/workspace/openclaw/run_bridge.py` | EDITED -- stub skip, logger, dispatch stats, summary printer |
| `/home/hoang/.openclaw/workspace/openclaw/engine.py` | EDITED -- debate report trimming, opponent arg trim, history trim |

## Risk Assessment

- **Low risk:** Features 2, 3 (logging only, no behavior change)
- **Medium risk:** Feature 1 (file replacement -- backups created, rollback documented)
- **Medium risk:** Feature 4 (input trimming -- could miss context, but reports are duplicated anyway)
- **No risk of model change:** All agents remain on Opus 4.6 throughout
