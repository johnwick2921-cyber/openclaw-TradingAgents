"""Brave Web Search tool — pre-fetches web headlines for trading agents.

Uses OpenClaw's built-in Brave Search API key from openclaw.json.
Registered as 'brave_search' in the tool registry.
"""

import json
import os
import logging
import requests

logger = logging.getLogger(__name__)

# Read Brave API key from OpenClaw config
_BRAVE_API_KEY = ""
try:
    oc_path = os.path.join(
        os.environ.get("HOME", "/home/hoang"),
        ".openclaw", "openclaw.json",
    )
    with open(oc_path) as f:
        oc = json.load(f)
    _BRAVE_API_KEY = oc.get("plugins", {}).get("entries", {}).get("brave", {}).get("config", {}).get("webSearch", {}).get("apiKey", "")
except Exception:
    pass


def brave_search(query: str, count: int = 10) -> str:
    """Search the web using Brave Search API.

    Args:
        query: Search query string
        count: Number of results (max 20)

    Returns:
        Formatted string with search results (title, description, URL)
    """
    if not _BRAVE_API_KEY:
        return f"Brave Search unavailable — API key not configured"

    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(count, 20)},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": _BRAVE_API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("web", {}).get("results", [])
        if not results:
            return f"No results found for: {query}"

        lines = [f"## Web Search: {query}\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            desc = r.get("description", "")
            url = r.get("url", "")
            age = r.get("age", "")
            lines.append(f"### {i}. {title}")
            if age:
                lines.append(f"*{age}*")
            if desc:
                lines.append(desc)
            if url:
                lines.append(f"Source: {url}")
            lines.append("")

        return "\n".join(lines)

    except requests.exceptions.Timeout:
        return f"Brave Search timed out for: {query}"
    except Exception as e:
        return f"Brave Search error: {e}"


def brave_news_search(ticker: str, date: str, config: dict = None) -> str:
    """Search for multi-source news headlines about a ticker.

    Searches multiple angles for headline dispute:
    1. Ticker-specific news
    2. Sector/market news
    3. Macro/economic news

    Returns combined results for the news-analyst to cross-reference.
    """
    futures = {"NQ", "MNQ", "ES", "MES", "YM", "RTY"}
    clean = ticker.upper().replace("=F", "").strip()
    is_futures = clean in futures

    queries = []
    if is_futures:
        name_map = {"NQ": "Nasdaq", "ES": "S&P 500", "MNQ": "Nasdaq", "MES": "S&P 500", "YM": "Dow", "RTY": "Russell"}
        name = name_map.get(clean, clean)
        queries = [
            f"{name} futures today {date}",
            f"stock market news today",
            f"Federal Reserve economic news today",
        ]
    else:
        queries = [
            f"{ticker} stock news today {date}",
            f"{ticker} earnings analyst rating",
            f"stock market {ticker} sentiment",
        ]

    all_results = []
    for q in queries:
        result = brave_search(q, count=5)
        all_results.append(result)

    return "\n\n".join(all_results)


def brave_social_search(ticker: str, date: str, config: dict = None) -> str:
    """Search for social media sentiment about a ticker.

    Searches Reddit, Twitter/X, and retail trader forums.
    """
    clean = ticker.upper().replace("=F", "").strip()
    futures = {"NQ", "MNQ", "ES", "MES", "YM", "RTY"}
    is_futures = clean in futures

    if is_futures:
        name_map = {"NQ": "Nasdaq NQ", "ES": "S&P ES", "MNQ": "Nasdaq", "MES": "S&P"}
        name = name_map.get(clean, clean)
        queries = [
            f"{name} futures reddit wallstreetbets today",
            f"{name} futures trader sentiment twitter",
        ]
    else:
        queries = [
            f"{ticker} stock reddit wallstreetbets sentiment",
            f"{ticker} stock twitter sentiment retail traders",
        ]

    all_results = []
    for q in queries:
        result = brave_search(q, count=5)
        all_results.append(result)

    return "\n\n".join(all_results)
