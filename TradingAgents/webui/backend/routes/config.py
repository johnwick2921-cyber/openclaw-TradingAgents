import json
import logging
import os
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter

from webui.backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ── Provider / model data (mirrored from cli/utils.py) ──────────────────────

PROVIDERS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/",
    "google": "https://generativelanguage.googleapis.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "xai": "https://api.x.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
}

DEEP_MODELS: Dict[str, list] = {
    "openai": [
        {"label": "GPT-5.4 - Latest frontier, 1M context", "value": "gpt-5.4"},
        {"label": "GPT-5.2 - Strong reasoning, cost-effective", "value": "gpt-5.2"},
        {"label": "GPT-5 Mini - Balanced speed, cost, and capability", "value": "gpt-5-mini"},
        {"label": "GPT-5.4 Pro - Most capable, expensive ($30/$180 per 1M tokens)", "value": "gpt-5.4-pro"},
    ],
    "anthropic": [
        {"label": "Claude Opus 4.6 - Most intelligent, agents and coding", "value": "claude-opus-4-6"},
        {"label": "Claude Opus 4.5 - Premium, max intelligence", "value": "claude-opus-4-5"},
        {"label": "Claude Sonnet 4.6 - Best speed and intelligence balance", "value": "claude-sonnet-4-6"},
        {"label": "Claude Sonnet 4.5 - Agents and coding", "value": "claude-sonnet-4-5"},
    ],
    "google": [
        {"label": "Gemini 3.1 Pro - Reasoning-first, complex workflows", "value": "gemini-3.1-pro-preview"},
        {"label": "Gemini 3 Flash - Next-gen fast", "value": "gemini-3-flash-preview"},
        {"label": "Gemini 2.5 Pro - Stable pro model", "value": "gemini-2.5-pro"},
        {"label": "Gemini 2.5 Flash - Balanced, stable", "value": "gemini-2.5-flash"},
    ],
    "xai": [
        {"label": "Grok 4 - Flagship model", "value": "grok-4-0709"},
        {"label": "Grok 4.1 Fast (Reasoning) - High-performance, 2M ctx", "value": "grok-4-1-fast-reasoning"},
        {"label": "Grok 4 Fast (Reasoning) - High-performance", "value": "grok-4-fast-reasoning"},
        {"label": "Grok 4.1 Fast (Non-Reasoning) - Speed optimized, 2M ctx", "value": "grok-4-1-fast-non-reasoning"},
    ],
    "deepseek": [
        {"label": "DeepSeek R1 - Best reasoning (671B MoE)", "value": "deepseek-reasoner"},
        {"label": "DeepSeek V3 - Fast, balanced (685B MoE)", "value": "deepseek-chat"},
    ],
    "openrouter": [
        {"label": "Z.AI GLM 4.5 Air (free)", "value": "z-ai/glm-4.5-air:free"},
        {"label": "NVIDIA Nemotron 3 Nano 30B (free)", "value": "nvidia/nemotron-3-nano-30b-a3b:free"},
    ],
    "ollama": [],  # populated dynamically from local Ollama
}

QUICK_MODELS: Dict[str, list] = {
    "openai": [
        {"label": "GPT-5 Mini - Balanced speed, cost, and capability", "value": "gpt-5-mini"},
        {"label": "GPT-5 Nano - High-throughput, simple tasks", "value": "gpt-5-nano"},
        {"label": "GPT-5.4 - Latest frontier, 1M context", "value": "gpt-5.4"},
        {"label": "GPT-4.1 - Smartest non-reasoning model", "value": "gpt-4.1"},
    ],
    "anthropic": [
        {"label": "Claude Sonnet 4.6 - Best speed and intelligence balance", "value": "claude-sonnet-4-6"},
        {"label": "Claude Haiku 4.5 - Fast, near-instant responses", "value": "claude-haiku-4-5"},
        {"label": "Claude Sonnet 4.5 - Agents and coding", "value": "claude-sonnet-4-5"},
    ],
    "google": [
        {"label": "Gemini 3 Flash - Next-gen fast", "value": "gemini-3-flash-preview"},
        {"label": "Gemini 2.5 Flash - Balanced, stable", "value": "gemini-2.5-flash"},
        {"label": "Gemini 3.1 Flash Lite - Most cost-efficient", "value": "gemini-3.1-flash-lite-preview"},
        {"label": "Gemini 2.5 Flash Lite - Fast, low-cost", "value": "gemini-2.5-flash-lite"},
    ],
    "xai": [
        {"label": "Grok 4.1 Fast (Non-Reasoning) - Speed optimized, 2M ctx", "value": "grok-4-1-fast-non-reasoning"},
        {"label": "Grok 4 Fast (Non-Reasoning) - Speed optimized", "value": "grok-4-fast-non-reasoning"},
        {"label": "Grok 4.1 Fast (Reasoning) - High-performance, 2M ctx", "value": "grok-4-1-fast-reasoning"},
    ],
    "deepseek": [
        {"label": "DeepSeek V3 - Fast, balanced (685B MoE)", "value": "deepseek-chat"},
        {"label": "DeepSeek R1 - Best reasoning (671B MoE)", "value": "deepseek-reasoner"},
    ],
    "openrouter": [
        {"label": "NVIDIA Nemotron 3 Nano 30B (free)", "value": "nvidia/nemotron-3-nano-30b-a3b:free"},
        {"label": "Z.AI GLM 4.5 Air (free)", "value": "z-ai/glm-4.5-air:free"},
    ],
    "ollama": [],  # populated dynamically from local Ollama
}

ANALYST_TYPES = [
    {"value": "market", "label": "Market Analyst"},
    {"value": "social", "label": "Social Media Analyst"},
    {"value": "news", "label": "News Analyst"},
    {"value": "fundamentals", "label": "Fundamentals Analyst"},
]

# Keys we track for /api/keys/status
_TRACKED_API_KEYS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "DATABENTO_API_KEY",
]


async def _get_ollama_models() -> List[Dict[str, str]]:
    """Fetch locally available models from Ollama API."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                size_bytes = m.get("size", 0)
                size_gb = f"{size_bytes / 1e9:.1f}GB" if size_bytes else ""
                param_size = m.get("details", {}).get("parameter_size", "")
                label = f"{name} ({param_size}, {size_gb})" if param_size else f"{name} ({size_gb})"
                models.append({"label": label, "value": name})
            return models
    except Exception as e:
        logger.debug("Could not fetch Ollama models: %s", e)
        return [{"label": "Ollama not running — start it first", "value": ""}]


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_config() -> dict:
    """Return available providers, models per provider, and analyst types."""
    # Fetch Ollama models dynamically
    ollama_models = await _get_ollama_models()

    deep = {**DEEP_MODELS, "ollama": ollama_models}
    quick = {**QUICK_MODELS, "ollama": ollama_models}

    return {
        "providers": PROVIDERS,
        "deep_models": deep,
        "quick_models": quick,
        "analyst_types": ANALYST_TYPES,
    }


@router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    """Read all settings from the settings table and return as a dict."""
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
    result = {}
    for row in rows:
        try:
            result[row["key"]] = json.loads(row["value"])
        except (ValueError, TypeError):
            result[row["key"]] = row["value"]
    return result


@router.put("/settings")
async def put_settings(payload: Dict[str, Any]) -> dict:
    """Upsert each key/value pair into the settings table."""
    async with get_db() as db:
        for key, value in payload.items():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )
        await db.commit()
    return {"status": "ok", "updated": list(payload.keys())}


@router.put("/keys")
async def put_keys(payload: Dict[str, str]) -> dict:
    """Write API key name/value pairs to a .env file in the project root.

    Creates the file if it does not exist; updates existing keys in place.
    Keys are never stored in SQLite.
    """
    env_path = os.path.join(_PROJECT_ROOT, ".env")

    # Read existing .env lines (if any)
    existing_lines: list[str] = []
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as fh:
            existing_lines = fh.readlines()

    # Build a map of KEY -> line-index for existing entries
    key_line_map: Dict[str, int] = {}
    for idx, line in enumerate(existing_lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            key_line_map[k] = idx

    # Update existing keys or append new ones
    for key, value in payload.items():
        new_line = f"{key}={value}\n"
        if key in key_line_map:
            existing_lines[key_line_map[key]] = new_line
        else:
            existing_lines.append(new_line)

    with open(env_path, "w", encoding="utf-8") as fh:
        fh.writelines(existing_lines)

    # Also set in current process so they take effect immediately
    for key, value in payload.items():
        os.environ[key] = value

    return {"status": "ok", "updated": list(payload.keys())}


@router.get("/keys/status")
async def get_keys_status() -> Dict[str, bool]:
    """Check which API keys are currently set in the environment."""
    return {name: bool(os.environ.get(name)) for name in _TRACKED_API_KEYS}
