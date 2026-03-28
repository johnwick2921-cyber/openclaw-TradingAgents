# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Trading Module

Config: `trading-config.json`
Database: `trading.db`
Agent definitions: `agents/trading/*.md`
Daily memory: `memory/YYYY-MM-DD.md`

### How It Works
OpenClaw dispatches 12 trading subagents in a 4-tier pipeline:
1. Analysts (market, social, news, fundamentals) → produce reports
2. Bull/Bear debate → argue for/against the trade
3. Research Manager + Trader + Risk debate → validate and size the trade
4. Portfolio Manager → final BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL

### Strategies
- **default**: Stock analysis with standard indicators (4 analysts)
- **jadecap**: ICT futures analysis with 23 ICT indicators (market + news only)

### Config Quick Reference
- Change strategy: edit `trading-config.json` → `"strategy": "jadecap"`
- Add to watchlist: edit `trading-config.json` → `"watchlist": ["NVDA", "AAPL"]`
- Halt analysis: set `"halt": true` in config
- Per-agent model: set `"llm.per_agent.market-analyst": "gpt-4o"` in config
