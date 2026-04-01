# User Bias + Confluence Scoring in Trading Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make user bias and confluence scoring affect every stage of the trading pipeline — not just Tier 1 analysts. The portfolio-manager's final decision must account for whether the trader agrees or disagrees with the agents.

**Architecture:** Inject user bias context into ALL 12 agent prompts (not just analysts). Compute a real-time confluence checklist that the portfolio-manager uses as a scoring factor. Add a pre-trade checklist section to the portfolio-manager prompt that includes bias alignment as a pass/fail gate.

**Tech Stack:** Python (engine.py prompt builders), Markdown (agent .md files)

---

## Current State (what's broken)

| Component | Status | Problem |
|-----------|--------|---------|
| User bias in config | ✅ Works | `bias.direction`, `bias.confidence`, `bias.reason` in trading-config.json |
| User bias in Tier 1 | ✅ Works | `_get_user_bias_context()` injected into `_build_analyst_prompt()` |
| User bias in Tier 2-4 | ❌ Missing | Bull/bear/judge/trader/risk/PM never see user bias |
| Confluence score | ✅ Computed | But only AFTER run completes — PM never sees it during the run |
| Pre-trade checklist | ❌ Missing | No checklist combining user bias + agent findings |
| Bias affects final signal | ❌ No | PM rates purely on ICT confluence — ignores trader's conviction |

## Target State

| Component | Change |
|-----------|--------|
| ALL 12 agents | See user bias in their prompt context |
| Bull/Bear researchers | Factor user bias into argument strength |
| Research manager | Note if analysis aligns/conflicts with user bias |
| Trader | Check if entry direction matches user bias |
| Risk agents | Flag if trade contradicts user's pre-session conviction |
| Portfolio manager | New "BIAS ALIGNMENT" section in decision — counts as checklist item |
| Portfolio manager | Compute pre-decision confluence and use it as scoring factor |

## Confluence Scoring (how it affects the trade)

```
User Bias Score:
  bullish/high = +3, bullish/medium = +2, bullish/low = +1
  neutral = 0
  bearish/low = -1, bearish/medium = -2, bearish/high = -3

Agent Direction Score (from current tier analysis):
  Strong bullish evidence = +3, moderate = +2, weak = +1
  Neutral = 0
  Weak bearish = -1, moderate = -2, strong = -3

Confluence Total = User + Agent (-6 to +6)

Impact on final decision:
  |Total| >= 5: STRONG confluence → full confidence in direction
  |Total| >= 3: MODERATE → standard confidence
  |Total| >= 1: WEAK → reduce position size by 25%
  Total = 0:    NEUTRAL → reduce by 50% or HOLD
  CONFLICT (signs differ): WARNING — reduce by 50% minimum
```

The portfolio-manager adds this as a **checklist item**:
- ✅ PASS: confluence >= +3 (or <= -3) and aligned → full size
- ⚠️ CAUTION: weak confluence (1-2) → reduce 25%
- ❌ FAIL: conflict (user says bullish, agents say bearish) → reduce 50% minimum or HOLD

---

## File Structure

```
Modified files:
├── /home/hoang/.openclaw/workspace/openclaw/engine.py                    ← inject bias into ALL tiers
├── /home/hoang/.openclaw/workspace/agents/trading/bull-researcher.md     ← add bias awareness
├── /home/hoang/.openclaw/workspace/agents/trading/bear-researcher.md     ← add bias awareness
├── /home/hoang/.openclaw/workspace/agents/trading/research-manager.md    ← add bias alignment check
├── /home/hoang/.openclaw/workspace/agents/trading/trader.md              ← add bias direction check
├── /home/hoang/.openclaw/workspace/agents/trading/aggressive-risk.md     ← add conflict warning
├── /home/hoang/.openclaw/workspace/agents/trading/conservative-risk.md   ← add conflict warning
├── /home/hoang/.openclaw/workspace/agents/trading/neutral-risk.md        ← add conflict warning
├── /home/hoang/.openclaw/workspace/agents/trading/portfolio-manager.md   ← add BIAS ALIGNMENT checklist
```

---

### Task 1: Inject user bias into ALL prompt builders (not just analysts)

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/openclaw/engine.py`

- [ ] **Step 1: Add user bias to `_build_researcher_prompt()`**

In `_build_researcher_prompt()` (line ~527), add user bias before the return statement. Find:

```python
        return f"""{prompt_text}

Company/Instrument: {ticker}
```

Add user bias before it:

```python
        user_bias = self._get_user_bias_context()

        return f"""{prompt_text}
{user_bias}
Company/Instrument: {ticker}
```

- [ ] **Step 2: Add user bias to `_build_prompt_with_context()`**

This method builds prompts for research-manager, trader, risk agents, and portfolio-manager. In `_build_prompt_with_context()` (line ~540), add `user_bias` and `confluence_context` to the context dict before placeholder substitution:

```python
    def _build_prompt_with_context(self, agents_dir, agent_name, strategy, **context):
        md_path = os.path.join(agents_dir, f"{agent_name}.md")
        prompt_text = self._read_strategy_prompt(md_path, strategy)
        base_context = context.copy()

        # Inject user bias and confluence into context for all Tier 2-4 agents
        base_context["user_bias_context"] = self._get_user_bias_context()
        base_context["confluence_context"] = self._get_confluence_context()

        if strategy == "jadecap":
```

- [ ] **Step 3: Add `_get_confluence_context()` method**

Add this method after `_get_user_bias_context()`:

```python
    def _get_confluence_context(self) -> str:
        """Format confluence score as context for agent prompts.

        Computes a LIVE confluence score based on current user bias
        and the direction implied by the analysis so far.
        """
        bias = self.config.get("bias", {})
        direction = bias.get("direction", "neutral")
        confidence = bias.get("confidence", "medium")
        reason = bias.get("reason", "")

        # Also include last agent bias if available (from previous run)
        agent_bias = self.config.get("agent_bias", {})
        agent_dir = agent_bias.get("direction", "")
        agent_signal = agent_bias.get("signal", "")

        parts = []
        parts.append("\n══ BIAS & CONFLUENCE CONTEXT ══")
        parts.append(f"Trader's Pre-Session Bias: {direction.upper()} (confidence: {confidence})")
        if reason:
            parts.append(f"Bias Reason: {reason}")
        if agent_dir:
            parts.append(f"Last Run Agent Bias: {agent_dir.upper()} (signal: {agent_signal})")

        # Confluence assessment
        if direction != "neutral" and agent_dir:
            aligned = (direction == "bullish" and agent_dir == "bullish") or \
                      (direction == "bearish" and agent_dir == "bearish")
            if aligned:
                parts.append(f"Confluence: ALIGNED — trader and agents agree ({direction})")
            elif agent_dir == "neutral":
                parts.append(f"Confluence: MIXED — trader is {direction} but agents are neutral")
            else:
                parts.append(f"Confluence: CONFLICT — trader is {direction} but agents say {agent_dir}")
                parts.append("⚠ When trader and agents disagree, proceed with caution. Reduce size or wait.")

        parts.append("══════════════════════════════\n")
        return "\n".join(parts)
```

- [ ] **Step 4: Handle first-run case (no prior agent_bias)**

In `_get_confluence_context()`, when `agent_bias` is empty (first run), output:

```python
        if not agent_dir:
            parts.append("No prior analysis available — this is the first run or no previous signal.")
            parts.append("Confluence cannot be computed yet. Decide based on trader bias + current evidence.")
```

- [ ] **Step 5: Verify bias injection works for all tiers**

Run:
```bash
cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.engine import RunEngine
engine = RunEngine('trading-config.json')
engine.config['bias'] = {'direction': 'bullish', 'confidence': 'high', 'reason': 'NQ above midnight open'}

# Test Tier 2
prompt = engine._build_researcher_prompt('agents/trading', 'bull-researcher', 'jadecap', 'NQ', '2026-04-01', '', {'history':'','bull_history':'','bear_history':'','count':0}, 'bull')
assert 'BULLISH' in prompt, 'Bias not in researcher prompt'
print('Tier 2: PASS')

# Test Tier 3 (research-manager)
prompt = engine._build_prompt_with_context('agents/trading', 'research-manager', 'jadecap', ticker='NQ', date='2026-04-01')
assert 'BULLISH' in prompt, 'Bias not in manager prompt'
assert 'CONFLUENCE' in prompt.upper(), 'Confluence not in manager prompt'
print('Tier 3: PASS')

# Test Tier 4 (portfolio-manager)
prompt = engine._build_prompt_with_context('agents/trading', 'portfolio-manager', 'jadecap', ticker='NQ', date='2026-04-01')
assert 'BULLISH' in prompt, 'Bias not in PM prompt'
print('Tier 4: PASS')

print('All tiers have user bias + confluence')
"
```
Expected: All 3 tiers PASS.

- [ ] **Step 5: Commit**

```bash
git add openclaw/engine.py
git commit -m "feat: inject user bias + confluence into all pipeline tiers"
```

---

### Task 2: Update bull/bear researcher prompts with bias awareness

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/agents/trading/bull-researcher.md`
- Modify: `/home/hoang/.openclaw/workspace/agents/trading/bear-researcher.md`

- [ ] **Step 1: Add TRADER CONVICTION section to bull-researcher JadeCap prompt**

Find the section that starts with `YOUR BULLISH CASE MUST COVER:` and add this as a new numbered item at the end of the list (matching the existing numbered format):

```markdown
N. TRADER CONVICTION ALIGNMENT
   {user_bias_context}
   - If trader bias is BULLISH → your case has EXTRA weight. The trader's pre-session
     conviction supports your thesis. Reference this: "Trader conviction aligns with
     bullish case — {bias_reason}"
   - If trader bias is BEARISH → you are arguing AGAINST the trader's own conviction.
     Your evidence must be exceptionally strong. Acknowledge: "Note: trader entered
     session with bearish conviction. Bullish case must overcome this."
   - If trader bias is NEUTRAL → no conviction factor. Argue purely on evidence.
   Include in your conclusion: "Trader Conviction: [SUPPORTS / OPPOSES / NEUTRAL]"
```

- [ ] **Step 2: Same pattern for bull-researcher Default prompt**

Add matching section at the end of the argument instructions.

- [ ] **Step 3: Add TRADER CONVICTION section to bear-researcher JadeCap prompt**

Same pattern but inverted — bearish conviction supports bear case:

```markdown
N. TRADER CONVICTION ALIGNMENT
   {user_bias_context}
   - If trader bias is BEARISH → your case has EXTRA weight. The trader's pre-session
     conviction supports your thesis. Reference this: "Trader conviction aligns with
     bearish case — {bias_reason}"
   - If trader bias is BULLISH → you are arguing AGAINST the trader's own conviction.
     Your evidence must be exceptionally strong. Acknowledge: "Note: trader entered
     session with bullish conviction. Bearish case must overcome this."
   - If trader bias is NEUTRAL → no conviction factor. Argue purely on evidence.
   Include in your conclusion: "Trader Conviction: [SUPPORTS / OPPOSES / NEUTRAL]"
```

- [ ] **Step 4: Same for bear-researcher Default prompt**

- [ ] **Step 5: Commit**

```bash
git add agents/trading/bull-researcher.md agents/trading/bear-researcher.md
git commit -m "feat: add trader conviction alignment to bull/bear researchers"
```

---

### Task 3: Update research-manager with bias alignment check

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/agents/trading/research-manager.md`

- [ ] **Step 1: Add bias alignment section to Default prompt**

After the `> **OpenClaw Tools:**` line, add:

```markdown
> **Bias Alignment Check:** After judging the bull/bear debate, compare your investment plan direction with the trader's pre-session bias (provided in context). In your output, include a "BIAS ALIGNMENT" section:
> - ALIGNED: your plan agrees with trader's bias → proceed with confidence
> - CONFLICTING: your plan disagrees with trader's bias → explain why the evidence overrides the trader's conviction
> - NEUTRAL: trader has no strong bias → decide purely on evidence
```

- [ ] **Step 2: Same for JadeCap prompt**

Add the same instruction after the JadeCap `> **OpenClaw Tools:**` line.

- [ ] **Step 3: Commit**

```bash
git add agents/trading/research-manager.md
git commit -m "feat: add bias alignment check to research manager"
```

---

### Task 4: Update trader prompt with bias direction check

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/agents/trading/trader.md`

- [ ] **Step 1: Add bias direction check to Default prompt**

After the `> **OpenClaw Tools:**` line, add:

```markdown
> **Trader Bias Check:** Before finalizing your trade plan, verify the trade direction aligns with the trader's pre-session bias. If they conflict (e.g., your plan is LONG but trader bias is BEARISH), you MUST note this conflict and explain why you're going against the trader's conviction. This conflict should reduce position size by at least 25%.
```

- [ ] **Step 2: Same for JadeCap prompt**

- [ ] **Step 3: Commit**

```bash
git add agents/trading/trader.md
git commit -m "feat: add bias direction check to trader"
```

---

### Task 5: Update risk agents with conviction/conflict assessment

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/agents/trading/aggressive-risk.md`
- Modify: `/home/hoang/.openclaw/workspace/agents/trading/conservative-risk.md`
- Modify: `/home/hoang/.openclaw/workspace/agents/trading/neutral-risk.md`

- [ ] **Step 1: Add CONVICTION RISK section to aggressive-risk JadeCap prompt**

Find `YOUR ICT-SPECIFIC RISK ASSESSMENT MUST COVER:` and add a new numbered section at the end:

```markdown
N. TRADER CONVICTION RISK
   {user_bias_context}
   {confluence_context}
   - ALIGNED (trader agrees with trade direction):
     → Execution risk LOW. Trader will hold through pullbacks with conviction.
     → From aggressive stance: full size justified. Conviction = commitment.
   - CONFLICTING (trader opposes trade direction):
     → Execution risk ELEVATED. Even aggressive traders second-guess when
       fighting their own pre-session read. Early exits, missed entries.
     → From aggressive stance: acknowledge the conflict but if ICT setup is
       A+ with all checklist items passing, the setup overrides conviction.
     → Recommendation: reduce by 1 contract minimum when conflicting.
   - NEUTRAL: no conviction factor — assess purely on setup quality.
   State in your output: "Conviction Risk: [LOW / ELEVATED / NEUTRAL]"
```

- [ ] **Step 2: Same for aggressive-risk Default prompt**

- [ ] **Step 3: Add CONVICTION RISK section to conservative-risk JadeCap prompt**

Find `YOUR ICT-SPECIFIC RISK ASSESSMENT MUST COVER:` and add:

```markdown
N. TRADER CONVICTION RISK — CRITICAL FOR CONSERVATIVE STANCE
   {user_bias_context}
   {confluence_context}
   - ALIGNED (trader agrees with trade direction):
     → Standard position sizing. Trader will execute with discipline.
   - CONFLICTING (trader opposes trade direction):
     → THIS IS A MAJOR RED FLAG. A trader going against their own pre-session
       conviction has historically poor execution:
       • Enters late (hesitation)
       • Exits early (fear of being wrong about being wrong)
       • Widens stops (trying to give the trade "room" they don't believe in)
       • Overrides stop when it gets close ("maybe I was right originally")
     → RECOMMENDATION: REDUCE SIZE 50% minimum.
     → If setup is borderline (any checklist item marginal): NO TRADE.
     → The $4.5M JadeCap edge comes from PASSING on trades that don't feel right.
       If the trader themselves doesn't believe in the direction, pass.
   - NEUTRAL: assess normally, no conviction adjustment needed.
   State in your output: "Conviction Risk: [ACCEPTABLE / HIGH — REDUCE / CRITICAL — NO TRADE]"
```

- [ ] **Step 4: Same for conservative-risk Default prompt**

- [ ] **Step 5: Add CONVICTION RISK section to neutral-risk JadeCap prompt**

Find the assessment section and add:

```markdown
N. TRADER CONVICTION FACTOR
   {user_bias_context}
   {confluence_context}
   Balance the conviction factor against the technical setup:
   - ALIGNED conviction + strong setup = FULL SIZE (both factors support)
   - ALIGNED conviction + weak setup = REDUCE 25% (setup concerns remain)
   - CONFLICTING conviction + strong setup = REDUCE 25-50% (setup is good
     but execution risk exists — trader may not hold through drawdown)
   - CONFLICTING conviction + weak setup = NO TRADE (neither factor supports)
   - NEUTRAL conviction = ignore this factor, decide on technicals alone
   State in your output: "Conviction Assessment: [direction] | Size Adjustment: [none / -25% / -50% / NO TRADE]"
```

- [ ] **Step 6: Same for neutral-risk Default prompt**

- [ ] **Step 7: Commit**

```bash
git add agents/trading/aggressive-risk.md agents/trading/conservative-risk.md agents/trading/neutral-risk.md
git commit -m "feat: add detailed conviction risk assessment to all 3 risk agents"
```

---

### Task 6: Add BIAS ALIGNMENT checklist to portfolio-manager

**Files:**
- Modify: `/home/hoang/.openclaw/workspace/agents/trading/portfolio-manager.md`

- [ ] **Step 1: Add STEP 3B to portfolio-manager JadeCap prompt**

Find `STEP 4: VERIFY HARD RULES` (line ~128) and insert this NEW step before it, matching the exact `══` formatting style:

```markdown
══════════════════════════════════════════════════════════════════
STEP 3B: TRADER CONVICTION & CONFLUENCE GATE
══════════════════════════════════════════════════════════════════

{user_bias_context}
{confluence_context}

The trader set a pre-session bias BEFORE seeing any analysis.
This represents their independent market read — compare it to what the agents found.

CONVICTION ALIGNMENT CHECK:
1. What is the trader's pre-session bias? [BULLISH / BEARISH / NEUTRAL]
2. What direction does YOUR analysis support? [LONG / SHORT / NO TRADE]
3. Do they agree?

SCORING TABLE:
| Trader Bias | Your Signal | Alignment | Contract Adjustment |
|-------------|-------------|-----------|---------------------|
| BULLISH high | BUY/OVERWEIGHT | ✅ STRONG ALIGNED | Full contracts |
| BULLISH med  | BUY/OVERWEIGHT | ✅ ALIGNED | Full contracts |
| BULLISH low  | BUY/OVERWEIGHT | ✅ WEAK ALIGNED | Standard (no boost) |
| BULLISH any  | HOLD | ⚠ TRADER WANTS LONG | Standard — setup not there |
| BULLISH high | SELL/UNDERWEIGHT | ❌ STRONG CONFLICT | REDUCE 50% minimum |
| BULLISH med  | SELL/UNDERWEIGHT | ❌ CONFLICT | REDUCE 25% minimum |
| BEARISH high | SELL/UNDERWEIGHT | ✅ STRONG ALIGNED | Full contracts |
| BEARISH any  | BUY/OVERWEIGHT | ❌ STRONG CONFLICT | REDUCE 50% minimum |
| NEUTRAL      | any | — NO FACTOR | Standard — decide on evidence |

CONFLICT OVERRIDE RULES:
- If STRONG CONFLICT + any checklist item is borderline → override to HOLD.
  Reason: trader won't execute a trade they fundamentally disagree with.
- If STRONG CONFLICT + ALL checklist items PASS with no borderline calls →
  allow the trade but REDUCE SIZE 50%. Note: "Setup overrides conviction."
- If CONFLICT + risk debate had no consensus → override to HOLD.
  Reason: both the trader AND the risk analysts are unsure.

CONVICTION AFFECTS EXECUTION:
- ALIGNED trader holds through pullbacks → more likely to reach targets
- CONFLICTING trader exits early → targets less likely to hit
- Factor this into your R:R assessment — a conflicting trader effectively
  has a tighter "mental stop" even if the real stop is correct.

ADD TO YOUR FINAL OUTPUT:
══════════════════════════
Trader Conviction: [BULLISH/BEARISH/NEUTRAL] ([HIGH/MEDIUM/LOW])
Analysis Direction: [LONG/SHORT/HOLD]
Conviction Alignment: [STRONG ALIGNED / ALIGNED / NEUTRAL / CONFLICT / STRONG CONFLICT]
Confluence Score: [user_score] + [agent_score] = [total] / 6
Contract Adjustment: [FULL / -25% / -50% / OVERRIDE HOLD]
══════════════════════════
```

- [ ] **Step 2: Add STEP 3B to Default strategy prompt**

Add the same step in the Default Strategy Prompt section, adapted for stocks (remove contract adjustment references, keep the alignment scoring table and conflict override rules). Place it before the final rating step.

- [ ] **Step 3: Verify the placeholder variables are available**

The placeholders `{user_bias_context}` and `{confluence_context}` will be injected by `_build_prompt_with_context()` from Task 1. Verify they resolve:

Run:
```bash
cd /home/hoang/.openclaw/workspace && python3 -c "
from openclaw.engine import RunEngine
engine = RunEngine('trading-config.json')
engine.config['bias'] = {'direction': 'bullish', 'confidence': 'high', 'reason': 'test'}
prompt = engine._build_prompt_with_context('agents/trading', 'portfolio-manager', 'jadecap', ticker='NQ', date='2026-04-01')
assert 'BIAS ALIGNMENT' in prompt
assert 'CONFLUENCE' in prompt
assert 'BULLISH' in prompt
print('PASS — PM sees bias, confluence, and alignment checklist')
"
```

- [ ] **Step 4: Commit**

```bash
git add agents/trading/portfolio-manager.md
git commit -m "feat: add BIAS ALIGNMENT checklist to portfolio manager decision"
```

---

### Task 7: Verify end-to-end with dry run

- [ ] **Step 1: Run dry pipeline with bullish bias**

```bash
cd /home/hoang/.openclaw/workspace && python3 -c "
import json, tempfile
from openclaw.config import load_config
from openclaw.engine import RunEngine
from openclaw.callbacks import CollectorCallback

config = load_config('trading-config.json')
config['bias'] = {'direction': 'bullish', 'confidence': 'high', 'reason': 'NQ above midnight open'}
config['analysis'] = {'analysts': ['market'], 'max_debate_rounds': 1, 'max_risk_discuss_rounds': 1, 'agent_timeout_seconds': 30}
config['halt'] = False
config['paths'] = {'database': '/tmp/bias_test.db', 'agents_dir': 'agents/trading', 'memory_dir': '/tmp/bm', 'results_dir': '/tmp/br', 'data_cache_dir': '/tmp/bc'}

tf = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
json.dump(config, tf); tf.close()

col = CollectorCallback()
engine = RunEngine(tf.name)
result = engine.run('NQ', '2026-04-01', callbacks=[col])
print(f'Signal: {result.signal}')
print(f'Confluence in config: {json.load(open(tf.name)).get(\"confluence\", {})}')

# Verify bias was in all agent prompts
agent_events = [e for e in col.events if e[0] == 'agent_status']
print(f'Agents dispatched: {len(agent_events)}')
print('PASS')
"
```

- [ ] **Step 2: Commit all changes**

```bash
git add -A
git commit -m "feat: user bias + confluence scoring affects entire trading pipeline"
```

---

## Summary

| Agent | What changes |
|-------|-------------|
| **All 12** | See `user_bias_context` and `confluence_context` in prompt |
| **market/social/news/fundamentals** | Already had bias (Tier 1) |
| **bull-researcher** | Notes if user bias supports/opposes bullish case |
| **bear-researcher** | Notes if user bias supports/opposes bearish case |
| **research-manager** | Outputs BIAS ALIGNMENT section (aligned/conflicting/neutral) |
| **trader** | Checks trade direction vs user bias, reduces size on conflict |
| **aggressive-risk** | Factors conviction risk into aggressive assessment |
| **conservative-risk** | Flags conflict as MAJOR risk, recommends no-trade |
| **neutral-risk** | Balances conviction alignment into overall risk |
| **portfolio-manager** | NEW Step 3B: BIAS ALIGNMENT & CONFLUENCE CHECK — pass/fail gate that can reduce size or override to HOLD |

**After implementation:** When you set bias to BULLISH with high confidence and the agents conclude SELL, the portfolio-manager will see:
```
BIAS ALIGNMENT: CONFLICT
CONFLUENCE ADJUSTMENT: REDUCE SIZE 50% minimum
```
And the conservative-risk agent will have flagged: "Trader going against own conviction — recommend NO TRADE."
