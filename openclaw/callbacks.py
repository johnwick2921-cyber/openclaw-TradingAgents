"""Callback protocol for RunEngine event streaming."""

import os
from datetime import datetime
from typing import Any, Protocol


class RunCallback(Protocol):
    """Protocol that frontends implement to receive run events."""
    def on_run_start(self, ticker: str, date: str) -> None: ...
    def on_agent_status(self, agent: str, status: str) -> None: ...
    def on_report_section(self, name: str, content: str) -> None: ...
    def on_debate_turn(self, speaker: str, argument: str) -> None: ...
    def on_signal(self, signal: str) -> None: ...
    def on_run_complete(self, result: Any) -> None: ...
    def on_error(self, error: Exception) -> None: ...


class PrintCallback:
    """Callback that prints a clean, high-contrast summary to stdout.

    Uses ANSI bold/dim (no color codes that break on light/dark terminals).
    All text is plain — no emojis, no unicode box drawing that renders wrong.
    """

    # ANSI codes — no explicit fg color, works on light AND dark terminals
    BOLD = "\033[1m"
    DIM = "\033[2m"
    REV = "\033[7m"    # reverse video — always visible regardless of bg
    RESET = "\033[0m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"

    def __init__(self):
        self._agent_count = 0
        self._total_agents = 10

    def on_run_start(self, ticker, date):
        self._agent_count = 0
        B, R = self.BOLD, self.RESET
        print(f"\n{B}{'='*60}{R}")
        print(f"{B}  OPENCLAW TRADING PIPELINE — {ticker} — {date}{R}")
        print(f"{B}{'='*60}{R}")
        print(f"  10 agents dispatching...\n")

    def on_agent_status(self, agent, status):
        D, R = self.DIM, self.RESET
        if status == "running":
            self._agent_count += 1
            print(f"  [{self._agent_count:>2}/{self._total_agents}] {agent}...")
        elif status == "completed":
            print(f"  [{self._agent_count:>2}/{self._total_agents}] {agent} {D}done{R}")

    def on_report_section(self, name, content):
        label = name.replace("_", " ").upper()
        print(f"         -> {label} ({len(content):,} chars)")

    def on_debate_turn(self, speaker, argument):
        print(f"         -> {speaker} ({len(argument):,} chars)")

    def on_signal(self, signal):
        B, R, RV = self.BOLD, self.RESET, self.REV
        # Use color for direction
        if signal in ("BUY", "BULLISH", "OVERWEIGHT"):
            C = self.GREEN
        elif signal in ("SELL", "BEARISH", "UNDERWEIGHT"):
            C = self.RED
        else:
            C = self.YELLOW

        print(f"\n{B}{'='*60}{R}")
        print(f"{B}{C}{RV}  >>> SIGNAL: {signal}  {R}")
        print(f"{B}{'='*60}{R}\n")

    def on_run_complete(self, result):
        B, D, R = self.BOLD, self.DIM, self.RESET
        mins = int(result.duration_seconds // 60)
        secs = int(result.duration_seconds % 60)
        print(f"  {D}Completed in {mins}m {secs}s{R}")

        # Print final decision summary
        if result.final_decision:
            lines = result.final_decision.strip().split("\n")
            print(f"\n{B}{'='*60}{R}")
            print(f"{B}  FINAL DECISION{R}")
            print(f"{B}{'-'*60}{R}")

            key_fields = [
                "Current Price", "Market Bias", "Direction", "Entry Model",
                "Entry Score", "Entry:", "Stop Loss", "Target 1", "Target 2",
                "Stop Points", "Risk:", "Contracts", "R:R Ratio", "Kill Zone",
                "SFP Status", "Draw on Liquidity", "Daily Bias", "Checklist",
                "GAME PLAN", "FINAL TRANSACTION PROPOSAL",
            ]
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                for kf in key_fields:
                    if stripped.startswith(kf):
                        # Highlight the label bold, value normal
                        if ":" in stripped:
                            label, _, value = stripped.partition(":")
                            print(f"  {B}{label}:{R} {value.strip()}")
                        else:
                            print(f"  {B}{stripped}{R}")
                        break

            # Also print the full reasoning section (Executive Summary + Investment Thesis)
            print(f"\n{B}{'-'*60}{R}")
            print(f"{B}  REASONING{R}")
            print(f"{B}{'-'*60}{R}")
            in_reasoning = False
            for line in lines:
                stripped = line.strip()
                if any(stripped.startswith(h) for h in [
                    "Executive Summary", "Investment Thesis", "Rating:",
                    "GAME PLAN", "Conviction", "STANDBY PLAN",
                ]):
                    in_reasoning = True
                if in_reasoning and stripped:
                    print(f"  {stripped}")
                # Stop at analyst reports reference (too long)
                if stripped.startswith("Analyst Reports") or stripped.startswith("Market ICT Analysis"):
                    break

            print(f"{B}{'='*60}{R}\n")

    def on_error(self, error):
        B, R, RED = self.BOLD, self.RESET, self.RED
        print(f"\n  {B}{RED}ERROR: {error}{R}")


class CollectorCallback:
    """Callback that collects all events for testing."""
    def __init__(self):
        self.events = []

    def on_run_start(self, ticker, date):
        self.events.append(("run_start", ticker, date))

    def on_agent_status(self, agent, status):
        self.events.append(("agent_status", agent, status))

    def on_report_section(self, name, content):
        self.events.append(("report", name, len(content)))

    def on_debate_turn(self, speaker, argument):
        self.events.append(("debate", speaker, len(argument)))

    def on_signal(self, signal):
        self.events.append(("signal", signal))

    def on_run_complete(self, result):
        self.events.append(("complete", result.signal))

    def on_error(self, error):
        self.events.append(("error", str(error)))


class FileMemoryCallback:
    """Callback that writes run events to a markdown file in memory_dir.

    Creates memory/<date>.md with a human-readable summary of the run.
    """
    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = memory_dir
        self._lines = []
        self._ticker = ""
        self._date = ""

    def on_run_start(self, ticker, date):
        self._ticker = ticker
        self._date = date
        self._lines.append(f"# Trading Analysis: {ticker} on {date}\n")
        self._lines.append(f"Run started: {datetime.now().isoformat()}\n")

    def on_agent_status(self, agent, status):
        if status == "completed":
            self._lines.append(f"- {agent}: {status}")

    def on_report_section(self, name, content):
        self._lines.append(f"\n## {name.replace('_', ' ').title()}\n")
        # Truncate very long reports for the summary
        if len(content) > 1000:
            self._lines.append(content[:1000] + "\n...(truncated)")
        else:
            self._lines.append(content)

    def on_debate_turn(self, speaker, argument):
        self._lines.append(f"\n### {speaker}\n")
        if len(argument) > 500:
            self._lines.append(argument[:500] + "\n...(truncated)")
        else:
            self._lines.append(argument)

    def on_signal(self, signal):
        self._lines.append(f"\n## Signal: **{signal}**\n")

    def on_run_complete(self, result):
        self._lines.append(f"\nCompleted in {result.duration_seconds:.1f}s")
        self._flush()

    def on_error(self, error):
        self._lines.append(f"\n## ERROR\n{error}")
        self._flush()

    def _flush(self):
        """Write accumulated lines to the markdown file."""
        if not self._date:
            return
        os.makedirs(self.memory_dir, exist_ok=True)
        filepath = os.path.join(self.memory_dir, f"{self._date}.md")
        mode = "a" if os.path.exists(filepath) else "w"
        with open(filepath, mode) as f:
            f.write("\n".join(self._lines))
            f.write("\n")
