"""Rich-based analysis viewer for individual trading runs.

Accepts a run_id and displays:
- Header: ticker, date, strategy, signal, duration
- Each report section as a panel
- Debate history with labeled turns
- Final decision highlighted
"""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from openclaw.database import safe_get_db

_SIGNAL_STYLES = {
    "buy": "bold green",
    "sell": "bold red",
    "overweight": "green",
    "underweight": "red",
    "bullish": "bold green",
    "bearish": "bold red",
    "neutral": "bold yellow",
    "hold": "bold yellow",  # legacy
}


def _signal_style(signal: str) -> str:
    """Return Rich style string for a signal."""
    return _SIGNAL_STYLES.get(signal.lower(), "yellow")


def _build_header_panel(run_row) -> Panel:
    """Build a header panel from a run row."""
    table = Table.grid(expand=True, padding=(0, 2))
    table.add_column()
    table.add_column()

    table.add_row("Ticker:", Text(run_row["ticker"] or "-", style="bold cyan"))
    table.add_row("Date:", Text(run_row["trade_date"] or "-"))
    table.add_row("Strategy:", Text(run_row["strategy"] or "default", style="bold"))

    signal = run_row["signal"] or "-"
    table.add_row("Signal:", Text(signal, style=_signal_style(signal)))

    status = run_row["status"] or "-"
    status_style = (
        "green" if status == "completed"
        else "red" if status == "failed"
        else "yellow"
    )
    table.add_row("Status:", Text(status, style=status_style))

    duration = run_row["duration_seconds"]
    if duration is not None:
        table.add_row("Duration:", Text(f"{duration:.1f}s"))
    else:
        table.add_row("Duration:", Text("-"))

    if run_row["error_message"]:
        table.add_row("Error:", Text(run_row["error_message"], style="bold red"))

    return Panel(table, title="[bold]Run Summary[/bold]", border_style="bold", style="default")


def _build_report_panels(reports) -> list:
    """Build a list of panels, one per report section."""
    panels = []
    for report in reports:
        section = report["section_name"] or "Unknown Section"
        content = report["content"] or "(no content)"
        # Skip final_decision — shown separately in the main view
        if section == "final_decision":
            continue
        panels.append(
            Panel(
                content,
                title=f"[bold]{section.upper().replace('_', ' ')}[/bold]",
                border_style="bold",
                style="default",
                expand=True,
            )
        )
    return panels


def _build_debate_panels(debates) -> list:
    """Build panels showing debate history."""
    panels = []
    for debate in debates:
        debate_type = debate["debate_type"] or "Debate"

        # Build the debate content — all text bright/white for contrast
        parts = []

        if debate["side_a_history"]:
            parts.append(Text.assemble(
                ("BULL CASE:\n", "bold green"),
                (debate["side_a_history"], ""),
            ))

        if debate["side_b_history"]:
            parts.append(Text.assemble(
                ("\nBEAR CASE:\n", "bold red"),
                (debate["side_b_history"], ""),
            ))

        if debate["side_c_history"]:
            parts.append(Text.assemble(
                ("\nNEUTRAL CASE:\n", "bold"),
                (debate["side_c_history"], ""),
            ))

        # Judge decision highlighted
        if debate["judge_decision"]:
            parts.append(Text.assemble(
                ("\nJUDGE DECISION:\n", "bold blue"),
                (debate["judge_decision"], "bold"),
            ))

        # Full history at end
        if debate["full_history"] and not debate["judge_decision"]:
            parts.append(Text.assemble(
                ("\nFULL HISTORY:\n", "bold"),
                (debate["full_history"], ""),
            ))

        # Combine parts into a single renderable
        content_table = Table.grid(expand=True)
        content_table.add_column()
        for part in parts:
            content_table.add_row(part)

        panels.append(
            Panel(
                content_table,
                title=f"[bold]{debate_type.upper()}[/bold]",
                border_style="bold",
                style="default",
                expand=True,
            )
        )

    return panels


def show_analysis(
    run_id: str,
    db_path: str = "trading.db",
) -> Optional[Panel]:
    """Display a detailed analysis view for a specific run.

    Args:
        run_id: The unique run identifier.
        db_path: Path to the SQLite trading database.

    Returns:
        A Rich Panel with the full analysis, or None if run not found.
    """
    console = Console()

    with safe_get_db(db_path) as conn:
        # Fetch the run
        run_row = conn.execute(
            "SELECT id, ticker, trade_date, strategy, signal, status, "
            "error_message, duration_seconds, created_at "
            "FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()

        if not run_row:
            console.print(
                Panel(
                    f"Run [bold]{run_id}[/bold] not found.",
                    title="[bold red]Error[/bold red]",
                    border_style="red", style="default",
                )
            )
            return None

        # Fetch reports
        reports = conn.execute(
            "SELECT section_name, content FROM reports "
            "WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()

        # Fetch debates
        debates = conn.execute(
            "SELECT debate_type, full_history, side_a_history, "
            "side_b_history, side_c_history, judge_decision "
            "FROM debates WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()

    # Build all sections
    header = _build_header_panel(run_row)
    report_panels = _build_report_panels(reports)
    debate_panels = _build_debate_panels(debates)

    # Extract final decision from reports (if saved)
    final_decision_panel = None
    reasoning_parts = []
    reasoning_panel = None
    for report in reports:
        if report["section_name"] == "final_decision" and report["content"]:
            content = report["content"]
            # Build a highlighted final decision panel
            fd_table = Table.grid(expand=True, padding=(0, 1))
            fd_table.add_column(style="bold", min_width=22)
            fd_table.add_column()

            key_fields = [
                "Current Price", "Market Bias", "Direction", "Entry Model",
                "Entry Score", "Entry:", "Stop Loss", "Target 1", "Target 2",
                "Stop Points", "Risk:", "Contracts", "R:R Ratio", "Kill Zone",
                "SFP Status", "Draw on Liquidity", "Daily Bias", "Checklist",
                "GAME PLAN", "FINAL TRANSACTION PROPOSAL",
            ]
            for line in content.split("\n"):
                stripped = line.strip()
                if not stripped:
                    continue
                for kf in key_fields:
                    if stripped.startswith(kf):
                        if ":" in stripped:
                            label, _, value = stripped.partition(":")
                            # Color-code the signal line
                            if label.strip() == "FINAL TRANSACTION PROPOSAL":
                                sig = value.strip().strip("*").strip()
                                style = _signal_style(sig)
                                fd_table.add_row(
                                    Text(label.strip(), style="bold"),
                                    Text(value.strip(), style=style),
                                )
                            elif label.strip() == "Market Bias":
                                bias_val = value.strip()
                                if "BULLISH" in bias_val.upper():
                                    style = "bold green"
                                elif "BEARISH" in bias_val.upper():
                                    style = "bold red"
                                else:
                                    style = "bold yellow"
                                fd_table.add_row(
                                    Text(label.strip(), style="bold"),
                                    Text(bias_val, style=style),
                                )
                            else:
                                fd_table.add_row(label.strip(), value.strip())
                        else:
                            fd_table.add_row(stripped, "")
                        break

            # Add reasoning sections
            reasoning_parts = []
            in_section = False
            for line in content.split("\n"):
                stripped = line.strip()
                if any(stripped.startswith(h) for h in [
                    "Executive Summary", "Investment Thesis", "Rating:",
                    "GAME PLAN", "Conviction", "STANDBY PLAN",
                ]):
                    in_section = True
                if stripped.startswith("Analyst Reports") or stripped.startswith("Market ICT Analysis"):
                    break
                if in_section and stripped:
                    reasoning_parts.append(stripped)

            final_decision_panel = Panel(
                fd_table,
                title="[bold]FINAL DECISION[/bold]",
                border_style="bold",
                style="default",
                expand=True,
            )

            if reasoning_parts:
                reasoning_text = "\n".join(reasoning_parts)
                reasoning_panel = Panel(
                    reasoning_text,
                    title="[bold]REASONING & GAME PLAN[/bold]",
                    border_style="bold",
                    style="default",
                    expand=True,
                )
            break

    # Combine into a master layout
    layout = Table.grid(expand=True)
    layout.add_column()
    layout.add_row(header)

    # Show final decision FIRST — most important
    if final_decision_panel:
        layout.add_row("")
        layout.add_row(final_decision_panel)
        if reasoning_parts:
            layout.add_row("")
            layout.add_row(reasoning_panel)

    if report_panels:
        layout.add_row("")
        for panel in report_panels:
            # Skip final_decision from report panels (already shown above)
            layout.add_row(panel)

    if debate_panels:
        layout.add_row("")
        for panel in debate_panels:
            layout.add_row(panel)

    if not report_panels and not debate_panels and not final_decision_panel:
        layout.add_row("")
        layout.add_row(
            Panel("No reports or debates recorded for this run.",
                  border_style="bold", style="default")
        )

    master = Panel(
        layout,
        title=f"[bold]Analysis: {run_id}[/bold]",
        border_style="bold",
        style="default",
        expand=True,
    )

    console.print(master)
    return master
