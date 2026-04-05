"""ForexFactory RED events — US high-impact events only.

Fetches from nfs.faireconomy.media JSON API (ForexFactory data feed).
Filters: USD country + High impact only.
Saves to data/forex-calendar.json with exact dates, times, forecasts.

Usage:
    python3 -m openclaw.tools.forex_calendar          # this week
    python3 -m openclaw.tools.forex_calendar --next    # next week

Cron: runs every Sunday 6 PM EST to pre-load the week.
The news-analyst reads via get_forex_calendar() tool.
"""

import json
import os
import sys
from datetime import datetime, timedelta

import requests

WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE", "/home/hoang/.openclaw/workspace")
OUTPUT_PATH = os.path.join(WORKSPACE, "data", "forex-calendar.json")

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def fetch_week(next_week: bool = False) -> dict:
    """Fetch RED US events for this week.

    Note: --next flag is ignored — API only serves current week.
    Run on Sunday to get the upcoming week's events.
    """
    url = CALENDAR_URL
    label = "this week"

    print(f"  Fetching ForexFactory RED events ({label})...")

    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        all_events = resp.json()
    except Exception as exc:
        print(f"  [ERROR] Failed to fetch calendar: {exc}", file=sys.stderr)
        return {"events": [], "error": str(exc)}

    # Filter: USD + High impact only
    red_us = []
    for e in all_events:
        if e.get("country") != "USD" or e.get("impact") != "High":
            continue

        # Parse the ISO date
        date_str = e.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str)
            date_only = dt.strftime("%Y-%m-%d")
            day_name = dt.strftime("%A")
            time_est = dt.strftime("%H:%M")
        except (ValueError, TypeError):
            date_only = "unknown"
            day_name = "unknown"
            time_est = "unknown"

        red_us.append({
            "event": e.get("title", "Unknown"),
            "date": date_only,
            "day": day_name,
            "time_est": time_est,
            "impact": "RED",
            "currency": "USD",
            "forecast": e.get("forecast", ""),
            "previous": e.get("previous", ""),
        })

    # Sort by date + time
    red_us.sort(key=lambda x: f"{x['date']} {x['time_est']}")

    # Determine week range
    dates = [e["date"] for e in red_us if e["date"] != "unknown"]
    week_start = min(dates) if dates else "unknown"
    week_end = max(dates) if dates else "unknown"

    return {
        "week_start": week_start,
        "week_end": week_end,
        "fetched_at": datetime.now().isoformat(),
        "filter": "US RED (high impact) only",
        "source": "nfs.faireconomy.media (ForexFactory data)",
        "events": red_us,
        "no_entry_rule": "Do not enter during the actual news release candle (1 min before to 1 min after). Once the candle closes, trade normally. If already in a position before news, hold — set and forget. REDUCE SIZE 50% on high-impact news days.",
    }


def save_calendar(calendar: dict):
    """Save calendar to JSON file."""
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(calendar, f, indent=2)
    print(f"  Saved {len(calendar['events'])} RED events to {OUTPUT_PATH}")


def load_calendar(auto_refresh: bool = True) -> dict:
    """Load saved calendar. Auto-fetches if stale (>24h) or missing."""
    cal = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH) as f:
            cal = json.load(f)

    # Auto-refresh if stale or missing
    if auto_refresh:
        fetched_at = cal.get("fetched_at", "")
        stale = True
        if fetched_at:
            try:
                fetched_dt = datetime.fromisoformat(fetched_at)
                age_hours = (datetime.now() - fetched_dt).total_seconds() / 3600
                stale = age_hours > 24
            except (ValueError, TypeError):
                stale = True

        if stale or not cal.get("events"):
            print("  [forex-calendar] Data stale or missing — auto-fetching...", flush=True)
            try:
                cal = fetch_week()
                save_calendar(cal)
            except Exception as exc:
                print(f"  [forex-calendar] Auto-fetch failed: {exc}", file=sys.stderr)

    return cal


def get_today_events(date: str = None) -> list:
    """Get RED events for a specific date from saved calendar."""
    cal = load_calendar()
    if not cal or "events" not in cal:
        return []
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    return [e for e in cal["events"] if e.get("date") == date]


def get_no_entry_windows(date: str = None) -> list:
    """Get news blackout windows for a given date.

    Window: 1 min before → 1 min after each RED event (news release candle only).
    Once the candle closes, trade normally.
    Returns list of dicts: {"event", "start_est", "end_est", "forecast", "previous"}
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    events = get_today_events(date)
    windows = []

    for e in events:
        time_str = e.get("time_est", "")
        if not time_str or time_str == "unknown":
            continue

        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1])

            # 1 min before
            start_min = minute - 1
            start_hour = hour
            if start_min < 0:
                start_min = 59
                start_hour -= 1

            # 1 min after
            end_min = minute + 1
            end_hour = hour + (end_min // 60)
            end_min = end_min % 60

            windows.append({
                "event": e["event"],
                "start_est": f"{start_hour:02d}:{start_min:02d}",
                "end_est": f"{end_hour:02d}:{end_min:02d}",
                "forecast": e.get("forecast", ""),
                "previous": e.get("previous", ""),
            })
        except (ValueError, IndexError):
            continue

    return windows


def install_cron_jobs(calendar: dict):
    """Auto-install cron jobs for each RED event.

    For each event:
    - At event_time + 2min: run post-news check (news candle closed)
    Replaces all previous forex-calendar cron entries each time.
    Also installs the weekly Sunday fetch job.
    """
    import subprocess

    # Read existing non-forex cron entries
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    other_lines = [
        line for line in existing.strip().split("\n")
        if line and "forex-calendar" not in line and "forex_calendar" not in line
    ]

    new_lines = []
    new_lines.append("# ── ForexFactory RED events (auto-generated) ──")
    # Weekly fetch: Sunday 6 PM this week, 6:01 PM next week
    venv_py = "/home/hoang/.openclaw/workspace/.venv/bin/python3"
    ws = "/home/hoang/.openclaw/workspace"
    log = f"{ws}/data/forex-calendar.log"
    new_lines.append(f"0 18 * * 0 cd {ws} && {venv_py} -m openclaw.tools.forex_calendar >> {log} 2>&1")
    new_lines.append(f"1 18 * * 0 cd {ws} && {venv_py} -m openclaw.tools.forex_calendar --next >> {log} 2>&1")

    # Per-event scan jobs: 2 min after each RED event (news candle closed)
    events = calendar.get("events", [])
    today = datetime.now().strftime("%Y-%m-%d")
    scan_count = 0

    for e in events:
        date_str = e.get("date", "")
        time_str = e.get("time_est", "")
        event_name = e.get("event", "unknown")
        if not date_str or date_str == "unknown" or not time_str or time_str == "unknown":
            continue

        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue

        # Skip past events
        if dt < datetime.now():
            continue

        # Scan time = event + 2 min (news candle closed, trade normally)
        scan_time = dt + timedelta(minutes=2)
        cron_min = scan_time.minute
        cron_hour = scan_time.hour
        cron_day = scan_time.day
        cron_month = scan_time.month

        # Cron: specific minute, hour, day, month (one-shot)
        scan_cmd = (
            f"{cron_min} {cron_hour} {cron_day} {cron_month} * "
            f"cd {ws} && {venv_py} -c \""
            f"from openclaw.tools.forex_calendar import get_no_entry_windows; "
            f"print('NEWS CANDLE CLOSED: {event_name} at {scan_time.strftime('%H:%M')} EST — trade normally now')"
            f"\" >> {log} 2>&1"
        )
        new_lines.append(f"# {event_name} on {date_str} at {time_str} EST → scan at {scan_time.strftime('%H:%M')}")
        new_lines.append(scan_cmd)
        scan_count += 1

    new_lines.append("# ── end forex-calendar ──")

    # Combine with existing non-forex entries
    all_lines = other_lines + [""] + new_lines
    crontab_content = "\n".join(all_lines) + "\n"

    # Install
    proc = subprocess.run(
        ["crontab", "-"],
        input=crontab_content, capture_output=True, text=True
    )
    if proc.returncode == 0:
        print(f"  Installed cron: 2 weekly fetch + {scan_count} post-news scan jobs")
    else:
        print(f"  [ERROR] Failed to install cron: {proc.stderr}", file=sys.stderr)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ForexFactory RED events (US only)")
    parser.add_argument("--next", action="store_true", help="Fetch next week")
    parser.add_argument("--no-cron", action="store_true", help="Skip cron job installation")
    args = parser.parse_args()

    calendar = fetch_week(next_week=args.next)
    save_calendar(calendar)

    if calendar["events"]:
        print(f"\n  RED US Events ({calendar['week_start']} → {calendar['week_end']}):")
        print(f"  {'Day':12s} {'Date':12s} {'Time':8s} {'Event':35s} {'Forecast':10s} {'Previous':10s}")
        print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*35} {'-'*10} {'-'*10}")
        for e in calendar["events"]:
            print(f"  {e['day']:12s} {e['date']:12s} {e['time_est']:8s} "
                  f"{e['event']:35s} {e.get('forecast', ''):10s} {e.get('previous', ''):10s}")

        dates = sorted(set(e["date"] for e in calendar["events"] if e["date"] != "unknown"))
        print(f"\n  News Blackout Windows (1 min before to 1 min after release candle only):")
        for d in dates:
            windows = get_no_entry_windows(d)
            for w in windows:
                print(f"    {d}  {w['start_est']} - {w['end_est']} EST  ({w['event']})")

        # Auto-install cron jobs
        if not args.no_cron:
            print()
            install_cron_jobs(calendar)
    else:
        print(f"\n  No RED US events found")


if __name__ == "__main__":
    main()
