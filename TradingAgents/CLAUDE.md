# CLAUDE.md — TradingAgents

## What This Is

Multi-agent LLM financial trading framework. Specialized agents (analysts, researchers, risk debaters, trader) collaborate via LangGraph to produce BUY/HOLD/SELL decisions. Two strategies: Default (stocks) and JadeCap ICT (futures).

## Quick Commands

```bash
# Install
pip install .                    # core
pip install ".[webui]"           # with web UI

# Run CLI
tradingagents                    # installed entry point
python -m cli.main               # from source

# Run Web UI
python run_webui.py              # serves http://localhost:8000
WEBUI_RELOAD=true python run_webui.py  # hot reload

# Frontend (separate terminal for dev)
cd webui/frontend && npm install && npm run build   # production
cd webui/frontend && npm run dev                     # dev server

# Tests
python -m pytest tests/

# Python usage
python main.py
```

## Environment Variables

```bash
OPENAI_API_KEY=          # OpenAI (GPT)
ANTHROPIC_API_KEY=       # Anthropic (Claude)
GOOGLE_API_KEY=          # Google (Gemini)
XAI_API_KEY=             # xAI (Grok)
DEEPSEEK_API_KEY=        # DeepSeek
OPENROUTER_API_KEY=      # OpenRouter
ALPHA_VANTAGE_API_KEY=   # Alpha Vantage data
DATABENTO_API_KEY=       # Databento futures data
```

Copy `.env.example` to `.env` and fill in keys.

## Architecture

### 4-Tier Agent Pipeline

```
Tier 1: ANALYSTS (data collection, parallel)
  ├── Market Analyst     → market_report    (OHLCV + technical indicators)
  ├── News Analyst       → news_report      (company + macro news)
  ├── Fundamentals       → fundamentals_report (financial statements)
  └── Social Media       → sentiment_report (social sentiment)

Tier 2: RESEARCHERS (debate, sequential rounds)
  ├── Bull Researcher    → bullish case + memory
  └── Bear Researcher    → bearish case + memory

Tier 3: MANAGERS + RISK
  ├── Research Manager   → investment_plan (judges bull/bear debate)
  ├── Risk Debaters      → risk assessment (aggressive/conservative/neutral)
  └── Portfolio Manager  → final_trade_decision (approves/rejects)

Tier 4: TRADER
  └── Trader             → BUY/HOLD/SELL with position sizing
```

### Two Strategies

- **Default** — general stock analysis, standard indicators
- **JadeCap ICT** — futures (NQ/ES), 23 ICT indicators, kill zones, SFP detection, A+ scoring, hard rules from Kyle Ng's playbook. Config in `tradingagents/jadecap_config.py`

### State Flow (LangGraph)

`AgentState` (TypedDict) carries all data through the graph:
- `company_of_interest`, `trade_date`
- `market_report`, `sentiment_report`, `news_report`, `fundamentals_report`
- `investment_debate_state` (InvestDebateState — bull/bear history + judge_decision)
- `risk_debate_state` (RiskDebateState — aggressive/conservative/neutral history)
- `investment_plan`, `trader_investment_plan`, `final_trade_decision`

Routing logic in `graph/conditional_logic.py` — checks tool_calls for analysts, debate count for researchers, round-robin for risk debaters.

## Project Layout

```
tradingagents/
├── default_config.py              # DEFAULT_CONFIG dict — all settings
├── jadecap_config.py              # 27-section JadeCap/ICT config
├── __init__.py                    # UTF-8 init
├── graph/
│   ├── trading_graph.py           # TradingAgentsGraph — main orchestrator
│   ├── setup.py                   # GraphSetup — compiles LangGraph StateGraph
│   ├── propagation.py             # Propagator — initial state + graph args
│   ├── conditional_logic.py       # ConditionalLogic — routing decisions
│   ├── reflection.py              # Reflector — post-trade learning
│   └── signal_processing.py       # SignalProcessor — extract BUY/HOLD/SELL
├── agents/
│   ├── utils/
│   │   ├── agent_states.py        # TypedDicts: AgentState, InvestDebateState, RiskDebateState
│   │   ├── agent_utils.py         # Helpers + tool re-exports
│   │   ├── memory.py              # FinancialSituationMemory (BM25-based)
│   │   ├── core_stock_tools.py    # @tool get_stock_data
│   │   ├── technical_indicators_tools.py  # @tool get_indicators
│   │   ├── fundamental_data_tools.py      # @tool get_fundamentals/balance_sheet/cashflow/income
│   │   ├── news_data_tools.py     # @tool get_news/global_news/insider_transactions
│   │   └── ict_tools.py           # JadeCap ICT tools (lazy-loaded)
│   ├── analysts/
│   │   ├── market_analyst.py      # Technical analysis (+ _jadecap variant)
│   │   ├── news_analyst.py        # News analysis (+ _jadecap variant)
│   │   ├── fundamentals_analyst.py
│   │   └── social_media_analyst.py
│   ├── researchers/
│   │   ├── bull_researcher.py     # Bullish debate (+ _jadecap variant)
│   │   └── bear_researcher.py     # Bearish debate (+ _jadecap variant)
│   ├── managers/
│   │   ├── research_manager.py    # Debate judge (+ _jadecap variant)
│   │   └── portfolio_manager.py   # Final approver (+ _jadecap variant)
│   ├── risk_mgmt/
│   │   ├── aggressive_debator.py  # High-risk view (+ _jadecap variant)
│   │   ├── conservative_debator.py # Low-risk view (+ _jadecap variant)
│   │   └── neutral_debator.py     # Balanced view (+ _jadecap variant)
│   └── trader/
│       ├── trader.py              # General trader (+ _jadecap variant)
│       └── trader_jadecap.py      # ICT trader with position sizing
├── llm_clients/
│   ├── factory.py                 # create_llm_client() — provider router
│   ├── base_client.py             # BaseLLMClient + normalize_content()
│   ├── openai_client.py           # OpenAI/xAI/Ollama/OpenRouter
│   ├── anthropic_client.py        # Claude
│   ├── google_client.py           # Gemini
│   └── validators.py              # VALID_MODELS per provider
├── dataflows/
│   ├── interface.py               # route_to_vendor() — vendor abstraction
│   ├── config.py                  # Thread-safe config singleton
│   ├── y_finance.py               # yfinance (default, no API key)
│   ├── yfinance_news.py           # yfinance news
│   ├── alpha_vantage*.py          # Alpha Vantage (5 files)
│   ├── databento_nq.py            # Databento futures
│   ├── ict_indicators.py          # ICT indicator calculations
│   ├── stockstats_utils.py        # stockstats wrappers
│   └── utils.py                   # Ticker mapping, date utils
cli/
├── main.py                        # Typer + Rich CLI with live progress
├── config.py                      # CLI config management
├── models.py                      # Pydantic models (AnalystType enum)
├── utils.py                       # Display utilities
├── stats_handler.py               # Token/tool usage callback
└── announcements.py               # Version announcements
webui/
├── backend/
│   ├── app.py                     # FastAPI app, CORS, SPA catch-all
│   ├── database.py                # SQLite schema (runs/reports/debates/memories/settings)
│   ├── runner.py                  # Background analysis thread
│   ├── memory_bridge.py           # SQLite ↔ BM25 Memory sync
│   ├── ws.py                      # WebSocket streaming
│   └── routes/
│       ├── runs.py                # POST/GET /api/runs
│       ├── config.py              # GET /api/config (providers, models)
│       ├── memories.py            # CRUD /api/memories
│       ├── cache.py               # Cache management
│       └── prices.py              # Price data + WebSocket
└── frontend/                      # React 19 + Vite + Tailwind
```

## Key Patterns

- **JadeCap variants**: Most agents have a `_jadecap.py` counterpart selected via `config["strategy"]`
- **Tool routing**: `dataflows/interface.py` routes tool calls to configured vendor (yfinance/alpha_vantage/databento) per category
- **Memory**: BM25 lexical similarity (no external APIs) — agents store (situation, recommendation) pairs and retrieve relevant past lessons
- **LLM normalization**: All providers return normalized string content via `normalize_content()` in base_client.py — handles OpenAI Responses API, Gemini thinking blocks, Claude extended thinking
- **Config propagation**: `default_config.py` → passed to `TradingAgentsGraph` → pushed to `dataflows/config.py` singleton (thread-safe)
- **Signal extraction**: 5-tier scale: BUY, OVERWEIGHT, HOLD, UNDERWEIGHT, SELL (via `signal_processing.py`)

## Dependencies

- Python 3.10+, langchain/langgraph, yfinance, stockstats, pandas, rich, typer, questionary
- WebUI extra: fastapi, uvicorn, websockets, aiosqlite, smartmoneyconcepts, databento
- Frontend: React 19, Vite, Tailwind CSS

## LLM Providers

| Provider | Configured via | Key models |
|----------|---------------|------------|
| OpenAI | `openai` | gpt-5.4-pro, gpt-5-mini, gpt-4.1 |
| Anthropic | `anthropic` | claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5 |
| Google | `google` | gemini-3.1-pro, gemini-3-flash, gemini-2.5-pro |
| xAI | `xai` | grok-4.1-fast-reasoning, grok-4-0709 |
| DeepSeek | `deepseek` | deepseek-chat, deepseek-reasoner |
| Ollama | `ollama` | any local model |
| OpenRouter | `openrouter` | any model |
