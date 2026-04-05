# JadeCap Rule Alignment — Fix 3 Over-Strict Rules

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the JadeCap trading rules with how JadeCap actually trades — daily bias (not multi-TF), premium/discount as context (not blocker), and accept 45-55% win rate (not 90%+ filtering).

**Architecture:** 3 rule changes propagated across jadecap_config.py (source of truth), 8 agent PROMPT.md files, 6 agent SOUL.md files, engine.py bias injection, and docs. Each task modifies one file completely.

**Tech Stack:** Python, Markdown agent prompts

---

## File Structure

```
Files to MODIFY (16 total):

# Config (source of truth)
openclaw/jadecap_config.py                    — HARD_RULES, BULL_SETUP, BEAR_SETUP, CHECKLIST

# Agent PROMPT.md files (8)
agents/trading/market-analyst/PROMPT.md        — HTF section, A+ scoring, checklist
agents/trading/bull-researcher/PROMPT.md       — premium zone blocker
agents/trading/bear-researcher/PROMPT.md       — discount zone blocker
agents/trading/research-manager/PROMPT.md      — setup verification, checklist
agents/trading/trader/PROMPT.md                — validation step, A+ threshold
agents/trading/conservative-risk/PROMPT.md     — risk checklist
agents/trading/neutral-risk/PROMPT.md          — (no change needed, already uses "grade honestly")
agents/trading/portfolio-manager/PROMPT.md     — signal tiers, hard rules, checklist

# Agent SOUL.md files (6)
agents/trading/market-analyst/SOUL.md          — "HTF non-negotiable"
agents/trading/research-manager/SOUL.md        — "checklist is absolute"
agents/trading/conservative-risk/SOUL.md       — "one failed = NO TRADE"
agents/trading/portfolio-manager/SOUL.md       — "enforce NO TRADE"
agents/trading/neutral-risk/SOUL.md            — A+ scoring reference
agents/trading/trader/SOUL.md                  — (already fixed ATR→structural)

# Engine
openclaw/engine.py                             — bias context formatting

# Docs
docs/JADECAP_AGENTS.md                         — HTF + A+ references
```

---

## Task 1: Update jadecap_config.py — Source of Truth

**Files:**
- Modify: `openclaw/jadecap_config.py:1226,1466-1501,1514-1534,1545-1565,1584-1671`

### Rule 1: HTF → Daily Bias

- [ ] Replace line 1485:
```
OLD: "HTF ALIGNMENT (SCORED -2): Prefer trading WITH Weekly/4H/Daily order flow. If HTF conflicts with LTF, reduce A+ score by 2. OVERRIDE ALLOWED: if BOTH 1H and 15m confirm direction via CHoCH/BOS + SFP, LTF override is valid — note it as counter-trend and reduce size by 50%.",
NEW: "DAILY BIAS: Establish a clear daily bias (BULLISH or BEARISH) from the daily chart — recent MSS, liquidity sweeps, inefficiencies, where price is heading. This is YOUR read for TODAY. If daily bias is unclear or choppy → NO TRADE. You do NOT need Weekly + 4H + Daily all agreeing — just a clear daily direction.",
```

- [ ] Replace BULL_SETUP line 1517:
```
OLD: "HTF structure is bullish — higher highs, higher lows on Weekly/4H/Daily",
NEW: "Daily bias is BULLISH — today's daily chart shows bullish intent (recent MSS buy-side, liquidity swept, price heading higher)",
```

- [ ] Replace BEAR_SETUP line 1548:
```
OLD: "HTF structure is bearish — lower highs, lower lows on Weekly/4H/Daily",
NEW: "Daily bias is BEARISH — today's daily chart shows bearish intent (recent MSS sell-side, liquidity swept, price heading lower)",
```

- [ ] Replace CHECKLIST htf_bias item (line 1586-1590):
```
OLD:
    "id": "htf_bias",
    "description": "HTF Bias Confirmed",
    "detail": "Weekly/Daily structure AND 4H FVG order flow both point same direction",
NEW:
    "id": "daily_bias",
    "description": "Daily Bias Confirmed",
    "detail": "Clear bullish or bearish bias established from daily chart — MSS, liquidity, inefficiencies",
```

### Rule 2: Premium/Discount → Context Not Blocker

- [ ] Replace line 1226:
```
OLD: "Never buy in premium, never sell in discount — hard rule"
NEW: "Premium/discount is CONTEXT for targets — not a trade blocker. Use it to identify draw on liquidity."
```

- [ ] Replace line 1486:
```
OLD: "ZONE DISCIPLINE (SCORED -2): Prefer buying in discount and selling in premium (relative to midnight open). If entering against zone, reduce A+ score by 2. OVERRIDE ALLOWED: if displacement candle + SFP + FVG all confirm entry direction, zone violation is acceptable — note increased risk.",
NEW: "PREMIUM/DISCOUNT CONTEXT: Premium (above 50% of range / above midnight open) = look for shorts. Discount (below 50% / below midnight open) = look for longs. This is CONTEXT for identifying targets and draw on liquidity — NOT a trade blocker. If your daily bias is bullish and you have sweep + FVG confirmation, you CAN buy above midnight open. Do NOT counter-trend — if daily bias is bullish, only take longs. If bearish, only shorts.",
```

- [ ] Replace BULL_SETUP lines 1518-1519:
```
OLD:
    "Price is in DISCOUNT zone — below 50% Fib of HTF range",
    "Price is below Midnight Open — discount confirmed",
NEW:
    "Daily bias is bullish — only take LONG setups today (do NOT counter-trend)",
    "Identify premium/discount zone relative to midnight open — use for target selection, not trade blocking",
```

- [ ] Replace BEAR_SETUP lines 1549-1550:
```
OLD:
    "Price is in PREMIUM zone — above 50% Fib of HTF range",
    "Price is above Midnight Open — premium confirmed",
NEW:
    "Daily bias is bearish — only take SHORT setups today (do NOT counter-trend)",
    "Identify premium/discount zone relative to midnight open — use for target selection, not trade blocking",
```

- [ ] Replace CHECKLIST correct_zone item (line 1592-1597):
```
OLD:
    "id": "correct_zone",
    "description": "Price in Correct Zone",
    "detail": "Discount for longs, premium for shorts — relative to Fib and Midnight Open",
NEW:
    "id": "not_counter_trend",
    "description": "Not Counter-Trend",
    "detail": "Trade direction matches daily bias — longs only if bullish, shorts only if bearish",
```

### Rule 3: Win Rate → Accept Losses, Simplify Sizing

- [ ] Replace lines 1492-1496 (A+ scoring threshold):
```
OLD:
    # ══ A+ SCORING THRESHOLD ══
    "A+ score below 4/10 = NO TRADE. Do not override. Discipline IS the edge.",
    "A+ score 4-5/10 = MARGINAL — reduce size by 50%, tighter stop.",
    "A+ score 6-7/10 = VALID — standard size.",
    "A+ score 8-10/10 = HIGH CONVICTION — full size allowed.",
NEW:
    # ══ TRADE DECISION (simple 3-tier) ══
    "TAKE IT (standard size): Sweep confirmed + displacement confirmed + FVG/OB entry available + inside Kill Zone. This is a valid setup — take it. 40-55% of setups will fail and that is NORMAL. The edge is in R:R (3:1 minimum), not win rate.",
    "REDUCE SIZE (half size): Daily bias is clear but missing ONE confirmation (e.g., no clear sweep but strong displacement, or SFP not yet confirmed on 1H). Flag as reduced-conviction entry.",
    "NO TRADE: No sweep + no displacement, OR outside Kill Zone, OR daily bias unclear, OR max loss/profit limits hit. These are the ONLY reasons to not trade.",
```

- [ ] Replace CHECKLIST a_plus_score item (line 1660-1664):
```
OLD:
    "id": "a_plus_score",
    "description": "A+ Score Calculated",
    "detail": "A+ Score Calculated — minimum 4/10 to proceed, 8+/10 for full size",
NEW:
    "id": "setup_tier",
    "description": "Setup Tier Determined",
    "detail": "TAKE IT (sweep+displacement+FVG) / REDUCE SIZE (missing one) / NO TRADE (no setup)",
```

- [ ] Commit

---

## Task 2: Update market-analyst/PROMPT.md

**Files:**
- Modify: `agents/trading/market-analyst/PROMPT.md`

- [ ] Replace STEP 1 HTF bias section. Change all references from "Weekly/4H/Daily alignment" to "daily bias from daily chart":
```
OLD (line ~80-85 area, STEP 1): References to "4H structure" and "HTF Bias"
NEW: "STEP 1 — DAILY BIAS: Determine today's bias from the daily chart. Recent Market Structure Shift (MSS)? Liquidity swept recently? Where is price heading today? Output: BULLISH / BEARISH / UNCLEAR. If UNCLEAR → NO TRADE."
```

- [ ] Replace STEP 5 order flow check (line 147-148):
```
OLD: "If disagree = reduce A+ score by 2. LTF OVERRIDE: if 1H+15m both confirm via CHoCH/BOS, counter-trend trade is valid at reduced size."
NEW: "If 1H order flow disagrees with your daily bias, note the conflict. If 1H+15m BOTH confirm against your daily bias, your bias may be wrong — reconsider. Do NOT counter-trend."
```

- [ ] Replace A+ SCORING section (lines 195-210) with simplified 3-tier:
```
SETUP TIER — determine which tier this setup qualifies for:

TAKE IT (standard size):
  ✓ Sweep confirmed (PDH/PDL/session level raided)
  ✓ Displacement candle confirmed (60%+ body in direction)
  ✓ FVG or OB entry available on 5m/15m
  ✓ Inside Kill Zone
  → This is a valid ICT setup. Take it.

REDUCE SIZE (half size):
  ✓ Has 3 of the 4 above (missing ONE confirmation)
  ✓ Daily bias is clear
  → Valid but lower conviction. Half size.

NO TRADE:
  ✗ No sweep AND no displacement
  ✗ Outside Kill Zone
  ✗ Daily bias unclear
  ✗ Max loss/profit limits hit
  → Wait for next opportunity.

40-55% of valid setups will fail. That is NORMAL.
The edge is 3:1 R:R, not high win rate. Do not over-filter.
```

- [ ] Commit

---

## Task 3: Update market-analyst/SOUL.md

**Files:**
- Modify: `agents/trading/market-analyst/SOUL.md:50-52`

- [ ] Replace lines 50-52:
```
OLD:
- HTF bias is non-negotiable — never trade against it.
- If the chart is unclear, the answer is HOLD.
- A+ scoring is honest — never inflate to justify a trade.
NEW:
- Daily bias drives direction — determine bullish or bearish for TODAY from the daily chart. Do not counter-trend.
- If daily bias is unclear, the answer is HOLD. But if bias is clear + setup is valid = TAKE IT.
- Setup evaluation is honest — sweep + displacement + FVG = valid trade. Don't over-filter trying for 100% win rate.
```

- [ ] Commit

---

## Task 4: Update bull-researcher/PROMPT.md + bear-researcher/PROMPT.md

**Files:**
- Modify: `agents/trading/bull-researcher/PROMPT.md:95`
- Modify: `agents/trading/bear-researcher/PROMPT.md:95`

- [ ] Bull-researcher line 95:
```
OLD: "- If price is in PREMIUM -> state NO LONG SETUP — never buy premium."
NEW: "- Note if price is in PREMIUM (above midnight open / above 50% of range). Premium = targets are nearby sell-side liquidity below. This is context for target selection, NOT a trade blocker. If daily bias is bullish and sweep + FVG confirm, a long in premium is valid at reduced conviction."
```

- [ ] Bear-researcher line 95:
```
OLD: "- If price is in DISCOUNT -> state NO SHORT SETUP — never sell discount."
NEW: "- Note if price is in DISCOUNT (below midnight open / below 50% of range). Discount = targets are nearby buy-side liquidity above. This is context for target selection, NOT a trade blocker. If daily bias is bearish and sweep + FVG confirm, a short in discount is valid at reduced conviction."
```

- [ ] Commit

---

## Task 5: Update research-manager/SOUL.md + PROMPT.md

**Files:**
- Modify: `agents/trading/research-manager/SOUL.md:49`
- Modify: `agents/trading/research-manager/PROMPT.md:127-130,166-167`

- [ ] SOUL.md line 49:
```
OLD: "The checklist is absolute. Any required item fails = NO TRADE."
NEW: "The checklist guides sizing, not blocking. Sweep + displacement + FVG = valid trade. Missing one confirmation = reduce size. No setup at all = NO TRADE."
```

- [ ] PROMPT.md lines 127-130:
```
OLD:
State PASS or FAIL for each requirement with evidence.
If ANY requirement FAILS -> the winning side is INVALID.
Then check if the OTHER side passes all requirements.
If NEITHER passes -> output NO TRADE.
NEW:
State PASS or FAIL for each requirement with evidence.
Missing requirements reduce conviction — they do NOT automatically invalidate.
If sweep + displacement + FVG are all present → setup is VALID regardless of other items.
If NO sweep AND no displacement → NO TRADE.
```

- [ ] PROMPT.md lines 166-167:
```
OLD:
State PASS or FAIL for each item with one-line evidence.
If ANY item FAILS -> output NO TRADE.
NEW:
State PASS or FAIL for each item with one-line evidence.
Failed absolute rules (kill zone, max loss, hard close) → NO TRADE.
Other failures reduce conviction and size — they do not block the trade.
```

- [ ] Commit

---

## Task 6: Update trader/PROMPT.md

**Files:**
- Modify: `agents/trading/trader/PROMPT.md:64-66`

- [ ] Replace lines 64-66:
```
OLD:
Check EVERY rule against the proposed plan.
ABSOLUTE hard rules violated → override to HOLD immediately.
SCORED rules violated → reduce A+ score and adjust position size. Trade can still proceed if A+ >= 4/10.
NEW:
Check absolute hard rules (kill zone, max loss, stop placement, hard close) against the proposed plan.
If ANY absolute hard rule violated → override to HOLD immediately.
For other rules: if sweep + displacement + FVG are confirmed → trade is VALID. Adjust size based on conviction tier (TAKE IT / REDUCE SIZE).
```

- [ ] Commit

---

## Task 7: Update conservative-risk/SOUL.md + PROMPT.md

**Files:**
- Modify: `agents/trading/conservative-risk/SOUL.md:50`
- Modify: `agents/trading/conservative-risk/PROMPT.md:55-61`

- [ ] SOUL.md line 50:
```
OLD: "One failed checklist item = NO TRADE. No exceptions."
NEW: "Absolute rule failure = NO TRADE. Missing confirmations = reduce size. Protect the account, but don't block every trade."
```

- [ ] PROMPT.md lines 55-61:
```
OLD:
1. CHECKLIST COMPLIANCE — SCORED ASSESSMENT
   - Did all 14 checklist items pass? Which ones failed and by how much?
   - Is the SFP truly confirmed (hourly candle CLOSED back inside)?
   - Is the displacement candle real (60%+ body) or a weak doji?
   - Is the FVG in the correct zone (discount for longs, premium for shorts)?
   - ABSOLUTE rule failures (kill zone, max loss, hard close) = NO TRADE.
   - SCORED rule failures (HTF alignment, zone, sweep) = reduce A+ score and size. Trade still possible if A+ >= 4.
NEW:
1. SETUP QUALITY CHECK
   - Are the 3 core confirmations present? Sweep + Displacement + FVG/OB = VALID TRADE.
   - Is the SFP truly confirmed (hourly candle CLOSED back inside)? If not → reduce size, not block.
   - Is the displacement candle real (60%+ body) or a weak doji? Weak = reduce size.
   - ABSOLUTE rule failures (kill zone, max loss, hard close) = NO TRADE.
   - Missing confirmations = REDUCE SIZE. 40-55% of setups fail — that's normal with 3:1 R:R.
```

- [ ] Commit

---

## Task 8: Update portfolio-manager/SOUL.md + PROMPT.md

**Files:**
- Modify: `agents/trading/portfolio-manager/SOUL.md:51,53`
- Modify: `agents/trading/portfolio-manager/PROMPT.md:115-138,182-195,283-285`

- [ ] SOUL.md lines 51,53:
```
OLD line 51: "HOLD is not failure — it's discipline. The best traders wait."
NEW line 51: "HOLD when there's no setup. But when sweep + displacement + FVG confirm — TAKE the trade. The best traders act on valid setups."

OLD line 53: "If any prior agent said NO TRADE, I enforce it. Period."
NEW line 53: "If prior agents said NO TRADE due to absolute rule failure (kill zone, max loss), I enforce it. But if they said NO TRADE due to missing soft confirmations while core setup exists, I evaluate independently."
```

- [ ] PROMPT.md signal tiers (lines 115-138) — simplify BUY/SELL requirements:
```
OLD: "All checklist items PASS. Stacked FVGs across timeframes. Silver Bullet FVG confirmed. ADX > 25 (strong trend). Multi-TF confluence (4H + 1H + 15m agree)."
NEW: "Daily bias is BULLISH. Sweep confirmed + displacement confirmed + FVG entry available. Inside Kill Zone. Core ICT setup is VALID — take the trade at standard size. 40-55% of setups will fail; the edge is 3:1 R:R."
```
(Mirror for SELL with bearish)

- [ ] PROMPT.md hard rules section (lines 182-195):
```
OLD references to "A+ score >= 4/10" and scored rule violations
NEW: "ABSOLUTE rules (kill zone, max loss, hard close) = HOLD if violated. For everything else: if sweep + displacement + FVG are confirmed, the trade is VALID. Missing one soft confirmation = REDUCE SIZE. No setup at all = HOLD."
```

- [ ] PROMPT.md checklist (line 283-285):
```
OLD: "If ANY required item FAILS -> override to HOLD."
NEW: "If ANY absolute rule fails (kill zone, max loss, hard close) → HOLD. Missing soft confirmations reduce size — they do not block trades."
```

- [ ] Commit

---

## Task 9: Update neutral-risk/SOUL.md

**Files:**
- Modify: `agents/trading/neutral-risk/SOUL.md:49,52`

- [ ] Line 49:
```
OLD: "Grade the setup honestly using the A+ scoring system."
NEW: "Grade the setup honestly: sweep + displacement + FVG = TAKE IT. Missing one = REDUCE SIZE. No setup = NO TRADE."
```

- [ ] Line 52:
```
OLD: "My recommendation must be specific: FULL / -25% / -50% / NO TRADE."
NEW: "My recommendation must be specific: FULL SIZE (core setup confirmed) / HALF SIZE (missing one confirmation) / NO TRADE (no setup or absolute rule failure)."
```

- [ ] Commit

---

## Task 10: Update engine.py bias context

**Files:**
- Modify: `openclaw/engine.py:518-552`

- [ ] Update `_get_user_bias_context()` to say "Daily Bias" instead of "Pre-Session Bias":
```
OLD line 526: parts = [f"\nTrader's Pre-Session Bias: {direction.upper()} (confidence: {confidence})"]
NEW line 526: parts = [f"\nTrader's Daily Bias: {direction.upper()} (confidence: {confidence})"]
```

- [ ] Update `_get_confluence_context()` to use "Daily Bias" language:
```
OLD line 544: parts.append(f"Trader's Pre-Session Bias: {direction.upper()} (confidence: {confidence})")
NEW line 544: parts.append(f"Trader's Daily Bias: {direction.upper()} (confidence: {confidence})")
```

- [ ] Commit

---

## Task 11: Update docs/JADECAP_AGENTS.md

**Files:**
- Modify: `docs/JADECAP_AGENTS.md:173,399`

- [ ] Line 173:
```
OLD: "1. HTF structure bullish (HH/HL on Weekly/4H/Daily)"
NEW: "1. Daily bias is bullish (MSS buy-side on daily chart)"
```

- [ ] Line 399:
```
OLD: "20. A+ score below 4/10 = NO TRADE"
NEW: "20. NO TRADE only when: no sweep + no displacement, outside kill zone, daily bias unclear, or absolute rule failure"
```

- [ ] Commit

---

## Summary

| Task | File | Changes |
|------|------|---------|
| 1 | jadecap_config.py | HARD_RULES, BULL/BEAR_SETUP, CHECKLIST — source of truth for all 3 rules |
| 2 | market-analyst/PROMPT.md | HTF→daily bias, A+→3-tier, checklist language |
| 3 | market-analyst/SOUL.md | "HTF non-negotiable" → "daily bias drives direction" |
| 4 | bull+bear researcher/PROMPT.md | "never buy premium" → "context not blocker" |
| 5 | research-manager/SOUL.md+PROMPT.md | "checklist absolute" → "guides sizing not blocking" |
| 6 | trader/PROMPT.md | A+ threshold → conviction tier |
| 7 | conservative-risk/SOUL.md+PROMPT.md | "one failed = NO TRADE" → "absolute fail = NO TRADE" |
| 8 | portfolio-manager/SOUL.md+PROMPT.md | Signal tiers, enforce logic, checklist |
| 9 | neutral-risk/SOUL.md | A+ scoring → 3-tier |
| 10 | engine.py | "Pre-Session Bias" → "Daily Bias" |
| 11 | docs/JADECAP_AGENTS.md | HTF + A+ references |
