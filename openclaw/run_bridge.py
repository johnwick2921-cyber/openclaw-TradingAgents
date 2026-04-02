"""Subprocess entry point for running trading analysis from the gateway.

Usage:
    python3 -m openclaw.run_bridge --ticker NVDA --date 2026-03-31 --progress-file /tmp/run-abc.jsonl

Dispatches AI calls through OpenClaw's gateway (port 18789) using its
OpenAI-compatible /v1/chat/completions endpoint. No separate API keys needed —
uses OpenClaw's configured auth and model routing.
"""

import argparse
import json
import os
import sys
import requests
from datetime import datetime, timezone


# OpenClaw gateway endpoint — all AI calls go through OpenClaw
GATEWAY_URL = "http://127.0.0.1:{port}/v1/chat/completions"


def _get_gateway_auth() -> tuple[int, str]:
    """Get OpenClaw gateway port and auth token."""
    port = int(os.environ.get("OPENCLAW_GATEWAY_PORT", "18789"))
    token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

    if not token:
        try:
            oc_path = os.path.join(
                os.environ.get("HOME", "/home/hoang"),
                ".openclaw", "openclaw.json",
            )
            with open(oc_path) as f:
                oc = json.load(f)
            token = oc.get("gateway", {}).get("auth", {}).get("token", "")
        except Exception:
            pass

    return port, token


# Agent role descriptions
AGENT_ROLES = {
    "market-analyst": "Primary ICT analysis engine. Runs the full 10-step JadeCap playbook. Produces the market report all other agents depend on.",
    "news-analyst": "Macro news researcher. Pulls multi-source headlines (Brave + yfinance), assesses Kill Zone risk, determines risk-on/risk-off macro bias.",
    "social-analyst": "Social media and retail sentiment researcher. Searches Reddit, Twitter/X for sentiment data.",
    "fundamentals-analyst": "Financial fundamentals researcher. Earnings, balance sheets, cash flow.",
    "bull-researcher": "Bull case advocate. Builds strongest LONG argument using ICT evidence. Has BM25 memory of past bullish analyses.",
    "bear-researcher": "Bear case advocate. Builds strongest SHORT argument. Counters bull points. Has BM25 memory of past bearish analyses.",
    "research-manager": "Investment judge. Evaluates bull/bear debate, resolves conflicts, validates checklist, produces investment plan. Deep-think model.",
    "trader": "Trade execution planner. Validates entry, calculates ATR stops, sizes contracts, enforces set-and-forget rules.",
    "aggressive-risk": "Aggressive risk perspective. Argues for full size when setup quality is high. Challenges conservative over-caution.",
    "conservative-risk": "Conservative risk perspective. Protects prop firm account. Challenges marginal setups ruthlessly. Last defense against overtrading.",
    "neutral-risk": "Balanced risk arbiter. Synthesizes aggressive and conservative views. Final risk-adjusted sizing recommendation.",
    "portfolio-manager": "Final decision authority. Applies 5-tier ICT rating, verifies hard rules, outputs BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL. Deep-think model.",
}

# Cache for system prompts — built once per run
_system_prompt_cache: dict = {}


def _read_file(workspace: str, filename: str) -> str:
    try:
        with open(os.path.join(workspace, filename)) as f:
            return f.read().strip()
    except Exception:
        return ""


def _extract_section(text: str, heading: str) -> str:
    """Extract a ## section from markdown."""
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


def _build_system_prompt(agent_name: str) -> str:
    """Build system prompt from the agent's own 7 core files.

    Each agent has its own directory at agents/trading/{name}/ with:
    IDENTITY.md, SOUL.md, USER.md, AGENTS.md, TOOLS.md, HEARTBEAT.md, TRADING.md

    These are tailored per agent — not shared workspace files.
    """
    if agent_name in _system_prompt_cache:
        return _system_prompt_cache[agent_name]

    workspace = os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace")
    agent_dir = os.path.join(workspace, "agents", "trading", agent_name)

    # Read this agent's 7 core files
    identity = _read_file(agent_dir, "IDENTITY.md")
    soul = _read_file(agent_dir, "SOUL.md")
    user = _read_file(agent_dir, "USER.md")
    agents_md = _read_file(agent_dir, "AGENTS.md")
    tools = _read_file(agent_dir, "TOOLS.md")
    heartbeat = _read_file(agent_dir, "HEARTBEAT.md")
    trading = _read_file(agent_dir, "TRADING.md")
    memory_md = _read_file(agent_dir, "MEMORY.md")

    # Fallback to workspace root if agent dir files don't exist yet
    if not identity:
        identity = f"You are {agent_name}, part of OpenClaw."
        role_desc = AGENT_ROLES.get(agent_name, "")
        if role_desc:
            identity += f"\n{role_desc}"

    parts = []
    if identity:
        parts.append(identity)
        parts.append("")
    if soul:
        parts.append(soul)
        parts.append("")
    if user:
        parts.append(user)
        parts.append("")
    if agents_md:
        parts.append(agents_md)
        parts.append("")
    if tools:
        parts.append(tools)
        parts.append("")
    if heartbeat:
        parts.append(heartbeat)
        parts.append("")
    if trading:
        parts.append(trading)
    if memory_md:
        parts.append(memory_md)

    result = "\n".join(parts)
    _system_prompt_cache[agent_name] = result
    return result


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
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                _time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(
                f"Cannot connect to OpenClaw gateway at {url}. "
                "Is the gateway running? (systemctl --user status openclaw-gateway)"
            )
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                _time.sleep(5 * (attempt + 1))
                continue
            raise TimeoutError(f"Agent '{agent_name}' timed out after 600s")
        except requests.exceptions.HTTPError as exc:
            if resp.status_code in (502, 503, 429) and attempt < max_retries - 1:
                _time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"Dispatch failed for {agent_name}: {exc}")
        except Exception as exc:
            raise RuntimeError(f"Dispatch failed for {agent_name}: {exc}")


def openclaw_dispatch_parallel(tasks: list) -> list:
    """Dispatch multiple agents in parallel through OpenClaw.

    Args:
        tasks: List of (agent_name, prompt, model) tuples.

    Returns:
        List of response strings in the same order.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _call(args):
        agent_name, prompt, model = args
        return openclaw_dispatch(agent_name, prompt, model)

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        return list(pool.map(_call, tasks))


class JsonLinesCallback:
    """RunCallback that writes JSON lines to a file for the gateway to poll."""

    def __init__(self, progress_path: str):
        self.progress_path = progress_path
        self._f = open(progress_path, "a")

    def _write(self, obj: dict):
        obj["ts"] = datetime.now(timezone.utc).isoformat()
        self._f.write(json.dumps(obj) + "\n")
        self._f.flush()

    def on_run_start(self, ticker, date):
        self._write({"event": "run_start", "ticker": ticker, "date": date})

    def on_agent_status(self, agent, status):
        self._write({"event": "agent_status", "agent": agent, "status": status})

    def on_report_section(self, name, content):
        self._write({"event": "report", "name": name, "length": len(content)})

    def on_debate_turn(self, speaker, argument):
        self._write({"event": "debate", "speaker": speaker, "length": len(argument)})

    def on_signal(self, signal):
        self._write({"event": "signal", "signal": signal})

    def on_run_complete(self, result):
        self._write({
            "event": "complete",
            "run_id": result.run_id,
            "signal": result.signal,
            "duration": result.duration_seconds,
        })
        self._f.close()

    def on_error(self, error):
        self._write({"event": "error", "message": str(error)})
        self._f.close()


def main():
    parser = argparse.ArgumentParser(description="Run trading analysis via RunEngine")
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g. NVDA)")
    parser.add_argument("--date", required=True, help="Trade date YYYY-MM-DD")
    parser.add_argument("--progress-file", required=True, help="Path to JSON-lines progress file")
    parser.add_argument("--config", default=None, help="Path to trading-config.json")
    args = parser.parse_args()

    config_path = args.config or os.path.join(
        os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace"),
        "trading-config.json",
    )

    from openclaw.engine import RunEngine
    from openclaw.callbacks import PrintCallback

    engine = RunEngine(config_path)
    jl_cb = JsonLinesCallback(args.progress_file)
    print_cb = PrintCallback()

    try:
        result = engine.run(
            ticker=args.ticker,
            date=args.date,
            dispatch_fn=openclaw_dispatch,
            dispatch_parallel_fn=openclaw_dispatch_parallel,
            callbacks=[jl_cb, print_cb],
        )
        print(json.dumps({
            "ok": True,
            "run_id": result.run_id,
            "signal": result.signal,
            "duration": result.duration_seconds,
        }))
    except Exception as exc:
        jl_cb.on_error(exc)
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
