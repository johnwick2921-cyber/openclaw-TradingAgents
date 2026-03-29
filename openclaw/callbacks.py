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
    """Simple callback that prints events to stdout."""
    def on_run_start(self, ticker, date):
        print(f"\n{'='*50}")
        print(f"Starting analysis: {ticker} on {date}")
        print(f"{'='*50}")

    def on_agent_status(self, agent, status):
        print(f"  [{agent}] {status}")

    def on_report_section(self, name, content):
        print(f"  Report ready: {name} ({len(content)} chars)")

    def on_debate_turn(self, speaker, argument):
        print(f"  Debate: {speaker} ({len(argument)} chars)")

    def on_signal(self, signal):
        print(f"\n  >>> SIGNAL: {signal} <<<\n")

    def on_run_complete(self, result):
        print(f"Analysis complete: {result.signal} ({result.duration_seconds:.1f}s)")

    def on_error(self, error):
        print(f"  ERROR: {error}")


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
