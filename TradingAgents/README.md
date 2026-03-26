<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles. This ensures the system achieves a robust, scalable approach to market analysis and decision-making.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Analyzes social media and public sentiment using sentiment scoring algorithms to gauge short-term market mood.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions. It determines the timing and magnitude of trades based on comprehensive market insights.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.13
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export DEEPSEEK_API_KEY=...        # DeepSeek
export XAI_API_KEY=...             # xAI (Grok)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage (data)
export DATABENTO_API_KEY=...       # Databento (NQ/ES futures data)
```

For local models, configure Ollama with `llm_provider: "ollama"` in your config.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more.

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Web UI

TradingAgents also includes a browser-based dashboard as an alternative to the CLI. It provides live streaming progress, run history, memory exploration, and error resilience.

**Prerequisites:** Node.js 18+ and npm

**Install and run:**
```bash
# Install backend dependencies
pip install ".[webui]"

# Build the frontend (one-time)
cd webui/frontend
npm install
npm run build
cd ../..

# Start the server
python run_webui.py
```

Opens `http://localhost:8000` in your browser.

**Features:**
- Configure and run analysis from the browser (ticker, date, provider, models, research depth, analysts)
- Live NQ futures price ticker on dashboard (Databento + yfinance fallback, auto-refreshes every 30s)
- Live WebSocket streaming of agent progress as each step completes
- View full reports, research debates, risk debates, and final decisions
- Run history with search, filter, sort, and comparison
- BM25 memory explorer — view and manage what each agent has learned
- Settings page for default config, API keys, data providers, and theme (dark/light)
- Data provider selection: yfinance, Alpha Vantage, or Databento (for NQ/ES futures)
- Export/import runs and memories as JSON
- Error resilience — rate limits and API errors are handled gracefully instead of crashing

### Databento Integration (NQ Futures)

For professional futures data (NQ, ES, CL, GC, etc.), set your Databento API key:

```bash
# Add to .env
DATABENTO_API_KEY=your-key-here
```

Then in Settings → Data Providers, select **Databento** for Stock Price Data and Technical Indicators. Databento provides institutional-quality OHLCV data from CME Globex. News and fundamentals fall back to yfinance (futures don't have earnings/balance sheets).

### ICT / Smart Money Concepts

The framework includes the `smartmoneyconcepts` library for ICT-based analysis:
- Fair Value Gaps (FVG)
- Order Blocks (OB)
- Break of Structure / Change of Character (BOS/CHoCH)
- Liquidity levels (equal highs/lows)
- Breaker Blocks
- Swing highs and lows

**For development (hot reload):**
```bash
# Terminal 1: Backend with auto-reload
WEBUI_RELOAD=true python run_webui.py

# Terminal 2: Frontend dev server
cd webui/frontend && npm run dev
```

---

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, OpenRouter, and Ollama.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # openai, google, anthropic, xai, openrouter, ollama
config["deep_think_llm"] = "gpt-5.2"     # Model for complex reasoning
config["quick_think_llm"] = "gpt-5-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

## Contributing

We welcome contributions from the community! Whether it's fixing a bug, improving documentation, or suggesting a new feature, your input helps make this project better. If you are interested in this line of research, please consider joining our open-source financial AI research community [Tauric Research](https://tauric.ai/).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

---

## Web UI

A browser-based dashboard that replaces the CLI with live streaming, run history, and strategy configuration.

### Quick Start

```bash
# 1. Install dependencies
pip install -e ".[webui]"

# 2. Build frontend
cd webui/frontend && npm install && npm run build && cd ../..

# 3. Start server
python run_webui.py
```

Open `http://localhost:8000` in your browser.

### Features

- **Dashboard** — Configure and launch analysis runs, view history, live price ticker (any futures/stocks)
- **Live Run** — Real-time WebSocket streaming of agent progress, messages, and all reports as they complete
- **Run Details** — View all analyst reports, research debates, trader proposal, and final decision with tabs
- **Memories** — Browse and manage BM25 agent memories from past trades (auto-saved after each run)
- **Settings** — Strategy config (JadeCap ICT or Default), LLM providers, API keys, data providers, Kill Zone toggles
- **Dark/Light Mode** — Toggle or follow system preference

### JadeCap ICT Strategy

When "JadeCap ICT" strategy is selected, the system uses:

- **7 specialized agents** with full ICT methodology prompts based on Kyle Ng's JadeCap playbook
- **23 ICT indicators** via smartmoneyconcepts + stockstats (FVG, OB, SFP, MSS/CHoCH, session levels, NDOG/NWOG, etc.)
- **Databento live price** streaming for NQ/MNQ/ES and any futures via WebSocket
- **Live price in agent prompts** — Market Analyst calls `get_live_price()` before every analysis
- **A+ Scoring** (7 criteria) for setup quality and position sizing (7/7=full, 5-6=half, <5=skip)
- **Daily Sweep / SFP** — Swing Failure Pattern detection on 1H as the #1 entry strategy
- **Silver Bullet** rules — first FVG only, sweep required, cancel at window close
- **Draw on Liquidity + IPDA** — 5-question framework + 20/40/60-day institutional delivery
- **20 hard rules** from the JadeCap playbook, injected into every agent prompt
- **14-item pre-trade checklist** validated before any entry
- **6 entry models** — SFP (Entry 0), FVG, Order Block, Liquidity Raid, Breaker Block, OTE Fibonacci
- **Kill Zone timing** with toggleable windows (AM, Silver Bullet AM, PM, Silver Bullet PM)
- **Holiday rules** — SFP reliability warnings on low-volume days
- **Midday avoidance** — 11:30 AM - 1:00 PM chop zone blocking
- **Auto-memory save** — memories generated after every completed run without manual reflect
- **Data provider routing** — Settings control which provider (Databento/yfinance/Alpha Vantage) is used per category
- **Futures ticker mapping** — NQ auto-maps to NQ=F for yfinance, NQ.c.0 for Databento

### Supported LLM Providers

| Provider | Quick Model | Deep Model |
|----------|------------|------------|
| Anthropic | claude-haiku-4-5 | claude-sonnet-4-6 |
| OpenAI | gpt-4.1-mini | gpt-4.1 |
| DeepSeek | deepseek-chat | deepseek-reasoner |
| Google | gemini-2.5-flash | gemini-2.5-pro |
| xAI | grok-3-mini | grok-3 |
| Ollama | any local model | any local model |
| OpenRouter | any model | any model |

### API Keys

Set in `.env` or via the Settings page:

| Key | Required For |
|-----|-------------|
| `ANTHROPIC_API_KEY` | Claude models (recommended for JadeCap) |
| `OPENAI_API_KEY` | GPT models |
| `DEEPSEEK_API_KEY` | DeepSeek models |
| `GOOGLE_API_KEY` | Gemini models |
| `DATABENTO_API_KEY` | Live futures price + OHLCV data (NQ, ES, etc.) |
| `ALPHA_VANTAGE_API_KEY` | Alternative data provider |
| `XAI_API_KEY` | Grok models |
| `OPENROUTER_API_KEY` | OpenRouter models |

### Development

```bash
# Backend with hot reload
WEBUI_RELOAD=true python run_webui.py

# Frontend dev server (separate terminal)
cd webui/frontend && npm run dev
```

### Dependencies

Python packages (installed via `pip install -e ".[webui]"`):
- `fastapi`, `uvicorn`, `websockets`, `aiosqlite` — Web UI backend
- `smartmoneyconcepts` — ICT indicators (FVG, OB, sessions, liquidity, BOS/CHoCH)
- `databento` — Live futures data and OHLCV
- `langchain`, `langgraph` — Agent framework
- `yfinance`, `stockstats` — Stock data and technical indicators

Frontend (installed via `npm install` in `webui/frontend/`):
- React 19, Vite, Tailwind CSS, React Router, react-markdown

---

## Citation

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
