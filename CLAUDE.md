# CLAUDE.md — OpenClaw Workspace

## What This Is

**OpenClaw** is the main project — a self-evolving AI agent framework. It gives AI assistants persistent identity, memory, personality, and behavioral protocols across sessions. The agent wakes up fresh each time and uses these files as its continuity.

## OpenClaw Framework Files

| File | Purpose |
|------|---------|
| `SOUL.md` | Core personality & behavior rules — the agent's character |
| `IDENTITY.md` | Name, creature type, vibe, emoji, avatar |
| `USER.md` | Profile of the human being helped |
| `AGENTS.md` | Session startup protocol, memory system, heartbeats, group chat rules, red lines |
| `BOOTSTRAP.md` | First-run onboarding — deleted after initial setup |
| `TOOLS.md` | Local environment notes (cameras, SSH, TTS, device names) |
| `HEARTBEAT.md` | Periodic task checklist for proactive background work |
| `.openclaw/` | Internal state (workspace-state.json) |

## Key Concepts

- **Session startup**: Read SOUL.md → USER.md → recent memory files → MEMORY.md (main session only)
- **Memory system**: Daily notes in `memory/YYYY-MM-DD.md` (raw logs), curated long-term in `MEMORY.md`
- **Heartbeats**: Periodic polls where agent can check email, calendar, weather, do background maintenance
- **MEMORY.md security**: Only loaded in direct (main) sessions, never in shared/group contexts
- **Boundaries**: No data exfiltration, `trash` over `rm`, ask before external actions
- **Identity evolution**: Agent fills in IDENTITY.md during first conversation, evolves SOUL.md over time

## Subprojects

- **TradingAgents/** — Multi-agent LLM financial trading framework (v0.2.2) by Tauric Research. Has its own [CLAUDE.md](TradingAgents/CLAUDE.md) with full architecture docs.

## Key Rules

- OpenClaw files are the agent's persistent self — update carefully, tell the user if changing SOUL.md
- BOOTSTRAP.md is meant to be deleted after first onboarding conversation
- Write things down — "mental notes" don't survive session restarts, files do
- Private things stay private. Period.
- Be helpful without being annoying — quality over quantity in interactions
