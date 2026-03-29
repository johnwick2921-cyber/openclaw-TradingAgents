# OpenClaw

Self-evolving AI agent framework with integrated trading analysis module.

## Trading Module

Analysis-only pipeline producing BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL signals through 12 AI subagents in a 4-tier pipeline:

1. **Analysts** (parallel) - Market, Social, News, Fundamentals
2. **Bull/Bear Debate** (sequential) - Argue for/against the trade
3. **Judge + Trader + Risk** (sequential) - Validate and size
4. **Portfolio Manager** - Final signal

### Quick Start

```python
from openclaw.engine import RunEngine

engine = RunEngine("trading-config.json")
result = engine.run("NVDA", "2026-03-28", dispatch_fn=my_ai_dispatch)
print(result.signal)  # BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL
```

### Architecture

- **AI-agnostic**: `dispatch_fn(agent_name, prompt, model) -> str` — bring your own AI
- **12 agent definitions** in `agents/trading/*.md` — works with any LLM
- **Unified config**: `trading-config.json` — single source for strategy, models, vendors, risk
- **Dynamic tool registry**: 30 indicators from stockstats + smartmoneyconcepts, called by name
- **BM25 memory**: learns from past trades, persisted in SQLite
- **Two strategies**: `default` (stocks) and `jadecap` (ICT futures)

### Dashboard

- **Terminal**: `python -m dashboard.terminal.monitor` (Rich signal board)
- **Web**: `python dashboard/web/run.py` (React + FastAPI)

### Install

```bash
pip install -e .                    # core
pip install -e '.[ict]'             # + ICT/JadeCap indicators
pip install -e '.[web]'             # + web dashboard
pip install -e '.[dev]'             # + pytest
```

## License

MIT
