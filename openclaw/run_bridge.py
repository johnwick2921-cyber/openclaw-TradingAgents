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


def openclaw_dispatch(agent_name: str, prompt: str, model: str) -> str:
    """Dispatch an agent prompt through OpenClaw's gateway.

    Flow: RunEngine → OpenClaw gateway (18789) → 9router (20128) → AI provider
    OpenClaw is the brain — handles auth, model routing, session tracking.
    """
    port, token = _get_gateway_auth()
    url = GATEWAY_URL.format(port=port)

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Add 9router/ prefix so OpenClaw routes through the 9router provider
    full_model = f"9router/{model}" if not model.startswith("9router/") else model

    payload = {
        "model": full_model,
        "messages": [
            {"role": "system", "content": f"You are {agent_name}, a specialized trading analysis agent."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to OpenClaw gateway at {url}. "
            "Is the gateway running? (systemctl --user status openclaw-gateway)"
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Agent '{agent_name}' timed out after 300s")
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
