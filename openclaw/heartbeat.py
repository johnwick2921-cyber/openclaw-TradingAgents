# openclaw/heartbeat.py
"""Market phase detection and heartbeat state management."""

import json
import os
from datetime import datetime
from typing import Optional

import pytz


def get_market_phase(config: dict) -> str:
    """Return current market phase based on config timezone and market hours.
    Returns: 'pre' | 'open' | 'midday' | 'close' | 'post' | 'closed'
    """
    schedule = config.get("schedule", {})
    hours = schedule.get("market_hours", {})
    tz_name = hours.get("timezone", "US/Eastern")
    strategy = config.get("strategy", "default")

    # Pick stock or futures hours based on strategy
    use = hours.get("use", "auto")
    if use == "auto":
        market_type = "futures" if strategy == "jadecap" else "stock"
    else:
        market_type = use

    market = hours.get(market_type, {"open": "09:30", "close": "16:00"})

    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    current_hm = now.strftime("%H:%M")

    open_time = market["open"]
    close_time = market["close"]

    # Handle futures (overnight: open 18:00, close 17:00)
    if market_type == "futures":
        # Futures are open from 18:00 to 17:00 next day (23h)
        if current_hm >= "18:00" or current_hm < "17:00":
            if current_hm >= "18:00" or current_hm < "09:30":
                return "pre"  # overnight session before NY open
            elif "11:30" <= current_hm < "13:00":
                return "midday"
            elif "15:45" <= current_hm < "17:00":
                return "close"
            else:
                return "open"
        else:
            return "closed"  # 17:00-18:00 daily maintenance

    # Stock market hours
    if current_hm < open_time:
        return "pre"
    elif current_hm >= close_time:
        return "post"
    elif "11:30" <= current_hm < "13:00":
        return "midday"
    elif current_hm >= "15:45":
        return "close"
    else:
        return "open"


def should_run_phase(config: dict, heartbeat_state: dict, phase: str) -> tuple:
    """Check if a heartbeat phase should run now.

    Args:
        config: Loaded trading config
        heartbeat_state: Current heartbeat state from JSON
        phase: 'pre_session' | 'during_session' | 'post_session'

    Returns:
        (should_run: bool, reason: str)
    """
    if config.get("halt"):
        return False, "Analysis halted"

    schedule = config.get("schedule", {})
    market_phase = get_market_phase(config)

    if phase == "pre_session":
        if not schedule.get("pre_session_analysis"):
            return False, "pre_session_analysis disabled in config"
        if market_phase != "pre":
            return False, f"Not in pre-session (current: {market_phase})"
        last = heartbeat_state.get("lastPreSession")
        if last:
            # Only run once per day
            today = datetime.now().strftime("%Y-%m-%d")
            if last.startswith(today):
                return False, "Already ran pre-session today"
        return True, "Pre-session analysis due"

    elif phase == "during_session":
        if market_phase not in ("open", "midday"):
            return False, f"Market not open (current: {market_phase})"
        last = heartbeat_state.get("lastMonitor")
        if last:
            interval = schedule.get("monitor_interval_min", 30)
            # Check minutes since last monitor
            try:
                last_dt = datetime.fromisoformat(last)
                elapsed = (datetime.now() - last_dt).total_seconds() / 60
                if elapsed < interval:
                    return False, f"Last check {elapsed:.0f}m ago (interval: {interval}m)"
            except (ValueError, TypeError):
                pass
        return True, "Monitor check due"

    elif phase == "post_session":
        if not schedule.get("post_session_reflect"):
            return False, "post_session_reflect disabled in config"
        if market_phase != "post":
            return False, f"Not in post-session (current: {market_phase})"
        last = heartbeat_state.get("lastPostSession")
        if last:
            today = datetime.now().strftime("%Y-%m-%d")
            if last.startswith(today):
                return False, "Already ran post-session today"
        return True, "Post-session reflection due"

    return False, f"Unknown phase: {phase}"


def load_heartbeat_state(path: str = "heartbeat-state.json") -> dict:
    """Load heartbeat state from JSON file."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def update_heartbeat_state(path: str, phase: str, result: dict = None) -> dict:
    """Update heartbeat state with latest check timestamp."""
    state = load_heartbeat_state(path)
    now = datetime.now().isoformat()

    phase_keys = {
        "pre_session": "lastPreSession",
        "during_session": "lastMonitor",
        "post_session": "lastPostSession",
    }

    key = phase_keys.get(phase)
    if key:
        state[key] = now

    if result:
        if "todaySignals" not in state:
            state["todaySignals"] = {}
        state["todaySignals"].update(result)

    with open(path, "w") as f:
        json.dump(state, f, indent=2)

    return state
