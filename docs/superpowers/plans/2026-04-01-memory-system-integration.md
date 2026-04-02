# Memory System Integration — Agents Learn Over Time

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each of the 12 trading agents learns from past analyses and gets smarter over time. Integrate the existing BM25 memory system with OpenClaw's memory infrastructure so memories persist, compound, and flow into future agent prompts.

**Architecture:** Three-layer memory system: (1) BM25 in-memory for fast retrieval during runs, (2) SQLite for persistence across restarts, (3) per-agent markdown MEMORY.md files in each agent's workspace for OpenClaw session context. After each run, the engine writes lessons learned to the agent's MEMORY.md. On next run, the agent's system prompt includes its memory file.

**Tech Stack:** Python (BM25, SQLite), Markdown (MEMORY.md per agent), OpenClaw session-memory hook

---

## Current Memory State

### What EXISTS:
1. **5 BM25 stores** (bull, bear, trader, judge, portfolio) — in-memory during run
2. **SQLite memories table** — 10 entries persisted, survives restarts
3. **Memory hydration** — loads from SQLite on engine init
4. **Memory injection** — `_get_memory_context()` injects top-3 BM25 matches into prompts for 5 agents
5. **Daily markdown** — `memory/2026-04-01.md` with human-readable run summaries
6. **Outcome tracking** — reflect() compares signal vs actual, stores correct/incorrect
7. **OpenClaw session-memory hook** — saves session context to `memory/` on /new or /reset

### What's MISSING:
1. **Only 5 of 12 agents have memory** — market-analyst, news-analyst, social-analyst, fundamentals-analyst, aggressive-risk, conservative-risk, neutral-risk have NO memory
2. **No per-agent MEMORY.md** — agents don't have long-term curated memory in their workspace
3. **No outcome-to-memory feedback loop** — when a signal is right/wrong, that lesson doesn't flow back to the specific agents who contributed
4. **No cross-run learning** — bull-researcher doesn't know what bull-researcher said last time about the same ticker
5. **Memory names inconsistent** — DB has "bull", "bear", "trader" but also "bull-researcher", "market-analyst" (mixed naming from different runs)
6. **Stub memories polluting DB** — 5 entries from dry runs with "[Stub response from...]"

---

## Three-Layer Memory Architecture

```
Layer 1: BM25 (runtime)
├── Fast in-memory retrieval during run
├── Top-3 matches injected into prompt as "past_memory_str"
├── Rebuilt from SQLite on each engine init
└── One store PER AGENT (12 stores, not 5)

Layer 2: SQLite (persistence)
├── memories table: agent_name, situation, recommendation, run_id, created_at
├── outcomes table: signal, correct, actual_change_pct
├── Survives restarts, grows over time
└── Source of truth for BM25 hydration

Layer 3: MEMORY.md (per-agent workspace)
├── agents/trading/{name}/MEMORY.md
├── Curated long-term lessons (not raw data)
├── Read by run_bridge.py as part of system prompt
├── Updated after each run with new lessons
└── Human-editable — trader can review and curate
```

---

## File Structure

```
Modified files:
├── openclaw/engine.py          ← expand from 5 to 12 memory stores
├── openclaw/memory_persistence.py  ← handle 12 stores + cleanup stubs
├── openclaw/run_bridge.py      ← read MEMORY.md in system prompt
├── openclaw/callbacks.py       ← add MemoryWriterCallback

New files:
├── agents/trading/*/MEMORY.md  ← 12 per-agent memory files (one per agent)
```

---

### Task 1: Expand BM25 from 5 to 12 memory stores

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/engine.py`

- [ ] **Step 1: Expand memory stores in __init__**

Change the memory initialization from 5 stores to 12 — one per agent:

```python
        self.memories = {
            "market-analyst": FinancialSituationMemory("market-analyst"),
            "news-analyst": FinancialSituationMemory("news-analyst"),
            "social-analyst": FinancialSituationMemory("social-analyst"),
            "fundamentals-analyst": FinancialSituationMemory("fundamentals-analyst"),
            "bull-researcher": FinancialSituationMemory("bull-researcher"),
            "bear-researcher": FinancialSituationMemory("bear-researcher"),
            "research-manager": FinancialSituationMemory("research-manager"),
            "trader": FinancialSituationMemory("trader"),
            "aggressive-risk": FinancialSituationMemory("aggressive-risk"),
            "conservative-risk": FinancialSituationMemory("conservative-risk"),
            "neutral-risk": FinancialSituationMemory("neutral-risk"),
            "portfolio-manager": FinancialSituationMemory("portfolio-manager"),
        }
```

- [ ] **Step 2: Update _get_memory_context to use agent name directly**

Change all `_get_memory_context("bull_memory", ...)` calls to use the agent name:
- `_get_memory_context("bull-researcher", ...)`
- `_get_memory_context("bear-researcher", ...)`
- etc.

Also update the frontmatter `memory` field references in the prompt builders to use agent names.

- [ ] **Step 3: Update memory persistence to use agent names**

In `memory_persistence.py`, the `persist_memories` and `hydrate_memories` functions use the dict keys as `agent_name`. Since keys are now agent names, the SQLite `agent_name` column will store "market-analyst", "bull-researcher", etc.

- [ ] **Step 4: Clean up stub memories from DB**

```python
# In engine.py __init__, after hydration:
from openclaw.database import get_db
with get_db(db_path) as conn:
    conn.execute("DELETE FROM memories WHERE situation LIKE '%Stub response%'")
    conn.commit()
```

- [ ] **Step 5: Test**

```bash
cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.engine import RunEngine
engine = RunEngine('trading-config.json')
print(f'Memory stores: {len(engine.memories)}')
for name in engine.memories:
    print(f'  {name}: {len(engine.memories[name].documents)} docs')
print('PASS')
"
```

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: expand BM25 from 5 to 12 memory stores — one per agent"
```

---

### Task 2: Inject memory into ALL 12 agent prompts

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/engine.py`

Currently only 5 agents get memory injected. Add memory to all 12.

- [ ] **Step 1: Add memory to _build_analyst_prompt**

After building the prompt, inject memory for the analyst:

```python
        # Inject agent's past memory
        memory_str = self._get_memory_context(agent_name, ticker, date)
        if memory_str:
            data_sections += f"\n\n=== PAST ANALYSIS MEMORY ===\n{memory_str}\n"
```

- [ ] **Step 2: Add memory to _build_researcher_prompt**

Use the agent name (bull-researcher, bear-researcher) instead of "bull_memory":

```python
        past_memory_str = self._get_memory_context(agent_name, ticker, date)
```

- [ ] **Step 3: Add memory to _build_prompt_with_context**

Add memory to the context for ALL Tier 3-4 agents:

```python
        base_context["past_memory_str"] = self._get_memory_context(agent_name, ticker, date)
```

This means research-manager, trader, ALL 3 risk agents, and portfolio-manager all get their own memory.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: inject BM25 memory into all 12 agent prompts"
```

---

### Task 3: Create per-agent MEMORY.md files

**Files:**
- Create: `/home/hoang/.openclaw/workspace/agents/trading/*/MEMORY.md` (12 files)

- [ ] **Step 1: Create initial MEMORY.md for each agent**

Each starts empty but with a header explaining its purpose:

```bash
cd /home/hoang/.openclaw/workspace/agents/trading
for agent in market-analyst news-analyst social-analyst fundamentals-analyst \
             bull-researcher bear-researcher research-manager trader \
             aggressive-risk conservative-risk neutral-risk portfolio-manager; do
cat > "$agent/MEMORY.md" << EOF
# Memory — $agent

Curated long-term lessons from past analyses. Updated after each run.
Read this before every analysis — learn from history, don't repeat mistakes.

## Lessons Learned
_(none yet — will populate after first run with outcomes)_
EOF
done
```

- [ ] **Step 2: Update run_bridge.py to read MEMORY.md in system prompt**

In `_build_system_prompt()`, after reading the 7 core files, also read MEMORY.md:

```python
    memory = _read_file(agent_dir, "MEMORY.md")

    # ... existing parts building ...
    if memory:
        parts.append(memory)
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: create per-agent MEMORY.md and include in system prompt"
```

---

### Task 4: Write lessons back to MEMORY.md after each run

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/engine.py`

After a run completes, write a summary lesson to each agent's MEMORY.md.

- [ ] **Step 1: Add _write_agent_memories method to RunEngine**

```python
    def _write_agent_memories(self, result, agents_dir: str):
        """Write run lessons to each agent's MEMORY.md file."""
        import os
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d")
        summary = f"\n## {result.ticker} — {result.date} → {result.signal}\n"
        summary += f"Duration: {result.duration_seconds:.0f}s\n\n"

        # Write to each agent that has BM25 memories from this run
        for agent_name, mem in self.memories.items():
            if not mem.documents:
                continue

            memory_file = os.path.join(agents_dir, agent_name, "MEMORY.md")
            if not os.path.exists(os.path.dirname(memory_file)):
                continue

            # Get the latest memory entry for this agent
            latest_situation = mem.documents[-1] if mem.documents else ""
            latest_recommendation = mem.recommendations[-1] if mem.recommendations else ""

            entry = f"### {date_str}: {result.ticker} → {result.signal}\n"
            entry += f"- Situation: {latest_situation[:200]}\n"
            entry += f"- Lesson: {latest_recommendation[:200]}\n\n"

            try:
                with open(memory_file, "a") as f:
                    f.write(entry)
            except Exception as exc:
                logger.warning("Failed to write memory for %s: %s", agent_name, exc)
```

- [ ] **Step 2: Call it after run completes**

In `run()`, after `persist_memories()`, add:

```python
            try:
                self._write_agent_memories(result, agents_dir)
            except Exception as exc:
                logger.warning("Failed to write agent memories: %s", exc)
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: write run lessons to per-agent MEMORY.md after each run"
```

---

### Task 5: Write outcome lessons after reflect()

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/engine.py`

When `reflect()` compares signal vs actual, write the outcome to the agents' memory.

- [ ] **Step 1: Add outcome writing to reflect()**

After the outcome is computed and saved to DB, write it to agent memories:

```python
        # Write outcome lesson to agent memories
        outcome_lesson = f"Signal was {signal}, actual change was {actual_change_pct:.2f}%."
        if correct is True:
            outcome_lesson += " Signal was CORRECT."
        elif correct is False:
            outcome_lesson += " Signal was WRONG."
        else:
            outcome_lesson += " Signal was neutral (HOLD/OVERWEIGHT/UNDERWEIGHT — correctness N/A)."

        agents_dir = self._resolve_path(self.config["paths"]["agents_dir"])
        for agent_name in self.memories:
            memory_file = os.path.join(agents_dir, agent_name, "MEMORY.md")
            if os.path.exists(memory_file):
                try:
                    entry = f"\n### Outcome: {ticker} {date} — {'✅ CORRECT' if correct else '❌ WRONG' if correct is False else '— N/A'}\n"
                    entry += f"- Signal: {signal}, Actual change: {actual_change_pct:.2f}%\n"
                    entry += f"- Lesson: {outcome_lesson}\n\n"
                    with open(memory_file, "a") as f:
                        f.write(entry)
                except Exception:
                    pass

        # Also add to BM25 memory for future retrieval
        for agent_name, mem in self.memories.items():
            mem.add_situations([{
                "situation": f"Outcome for {ticker} on {date}: signal={signal}, change={actual_change_pct:.2f}%",
                "recommendation": outcome_lesson,
            }])
```

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: write outcome lessons to agent MEMORY.md after reflect()"
```

---

### Task 6: Fix inconsistent memory names in DB

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/memory_persistence.py`

- [ ] **Step 1: Add migration to normalize agent names**

```python
# Add to hydrate_memories():
# Normalize old names to new agent names
NAME_MAP = {
    "bull_memory": "bull-researcher",
    "bear_memory": "bear-researcher",
    "trader_memory": "trader",
    "invest_judge_memory": "research-manager",
    "portfolio_manager_memory": "portfolio-manager",
    "bull": "bull-researcher",
    "bear": "bear-researcher",
    "invest_judge": "research-manager",
    "portfolio_manager": "portfolio-manager",
}

def _normalize_agent_name(name: str) -> str:
    return NAME_MAP.get(name, name)
```

Apply this in both `hydrate_memories` (when reading) and `persist_memories` (when writing).

- [ ] **Step 2: Run migration on existing DB**

```python
# One-time migration
with get_db(db_path) as conn:
    for old, new in NAME_MAP.items():
        conn.execute("UPDATE memories SET agent_name = ? WHERE agent_name = ?", (new, old))
    conn.execute("DELETE FROM memories WHERE situation LIKE '%Stub response%'")
    conn.commit()
```

- [ ] **Step 3: Commit**

```bash
git commit -m "fix: normalize memory agent names + clean stub entries"
```

---

### Task 7: Verify end-to-end memory flow

- [ ] **Step 1: Check all 12 agents have MEMORY.md**

```bash
for agent in market-analyst news-analyst social-analyst fundamentals-analyst \
             bull-researcher bear-researcher research-manager trader \
             aggressive-risk conservative-risk neutral-risk portfolio-manager; do
    [ -f "agents/trading/$agent/MEMORY.md" ] && echo "✅ $agent" || echo "❌ $agent"
done
```

- [ ] **Step 2: Verify memory injection in prompts**

```bash
cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.engine import RunEngine
engine = RunEngine('trading-config.json')

# Check all 12 stores exist
assert len(engine.memories) == 12, f'Expected 12, got {len(engine.memories)}'
print(f'12 memory stores: PASS')

# Check memory context generation
for agent in ['market-analyst', 'bull-researcher', 'portfolio-manager']:
    ctx = engine._get_memory_context(agent, 'NQ', '2026-04-01')
    print(f'{agent} memory: {len(ctx)} chars')
print('PASS')
"
```

- [ ] **Step 3: Verify MEMORY.md is in system prompt**

```bash
python3 -c "
from openclaw.run_bridge import _build_system_prompt
prompt = _build_system_prompt('portfolio-manager')
assert 'Memory' in prompt or 'memory' in prompt or 'Lessons' in prompt
print(f'MEMORY.md in system prompt: PASS ({len(prompt)} chars)')
"
```

- [ ] **Step 4: Commit and push**

```bash
git add -A
git commit -m "feat: complete memory system — 12 stores, per-agent MEMORY.md, outcome learning"
git push
```

---

## How It Works After Implementation

```
RUN 1: Analyze NQ
  → 12 agents run, each gets empty MEMORY.md in system prompt
  → BM25 stores empty (first run)
  → Signal: HOLD
  → Engine writes lessons to each agent's MEMORY.md
  → Engine persists BM25 to SQLite

REFLECT: Compare HOLD vs actual NQ close
  → Actual: +0.93% → HOLD was WRONG (missed the move)
  → Outcome written to every agent's MEMORY.md:
    "❌ WRONG: HOLD but NQ moved +0.93%"
  → Added to BM25 stores

RUN 2: Analyze NQ (next day)
  → MEMORY.md in system prompt: "Last time HOLD was wrong, missed +0.93%"
  → BM25 retrieves: "When SFP was confirmed but A+ score was marginal,
    the trade worked anyway. Consider reducing A+ threshold."
  → Agents adjust: more weight to confirmed SFP even with borderline A+
  → Signal: BUY (learned from past mistake)

RUN 10+: Pattern emerges
  → MEMORY.md accumulates lessons:
    "When trader bias is bullish and market-analyst sees SFP,
     go with it even if A+ score is only 5/10"
  → BM25 retrieves most relevant past situations for current analysis
  → Agents get smarter — fewer missed moves, better calibration
```

## Summary

| Component | Before | After |
|-----------|--------|-------|
| BM25 stores | 5 agents | **12 agents** (all have memory) |
| Memory in prompts | 5 agents | **12 agents** |
| MEMORY.md per agent | None | **12 files** (curated lessons) |
| Outcome learning | Only BM25 | **BM25 + MEMORY.md + SQLite** |
| Cross-run learning | Partial | **Full** — every run adds to every agent's memory |
| Memory in system prompt | None | **MEMORY.md included** for every agent |
| Stub cleanup | Polluting DB | **Cleaned** + migration for old names |
