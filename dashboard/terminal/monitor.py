"""Rich-based signal board for the OpenClaw terminal dashboard.

Reads from trading.db and trading-config.json to display:
- Halt status and active strategy
- Watchlist tickers with latest signals, prices, and correctness
- Memory stats (per-agent counts)
- Last run info (ticker, date, signal, status, duration)
"""

from typing import Any, Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from openclaw.config import load_config
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


def _build_halt_status(config: Dict[str, Any]) -> Text:
    """Build a colored halt-status text."""
    halted = config.get("halt", False)
    if halted:
        return Text("HALTED", style="bold red")
    return Text("ACTIVE", style="bold green")


def _build_strategy_text(config: Dict[str, Any]) -> Text:
    """Build a text showing the active strategy."""
    strategy = config.get("strategy", "default")
    return Text(strategy, style="bold cyan")


def _build_watchlist_table(config: Dict[str, Any], db_path: str) -> Table:
    """Build a table of watchlist tickers with their latest signals."""
    table = Table(title="Watchlist", expand=True)
    table.add_column("Ticker", style="bold")
    table.add_column("Signal")
    table.add_column("Date")
    table.add_column("Status")
    table.add_column("Correct?")

    watchlist = config.get("watchlist", [])
    if not watchlist:
        table.add_row("(empty)", "", "", "", "")
        return table

    with safe_get_db(db_path) as conn:
        for ticker in watchlist:
            # Get latest run for this ticker
            row = conn.execute(
                "SELECT signal, trade_date, status FROM runs "
                "WHERE ticker = ? ORDER BY created_at DESC LIMIT 1",
                (ticker,),
            ).fetchone()

            # Get latest outcome for correctness
            outcome = conn.execute(
                "SELECT correct FROM outcomes "
                "WHERE ticker = ? ORDER BY created_at DESC LIMIT 1",
                (ticker,),
            ).fetchone()

            if row:
                signal = row["signal"] or "-"
                signal_style = _signal_style(signal)
                correct_val = ""
                if outcome and outcome["correct"] is not None:
                    correct_val = "Yes" if outcome["correct"] else "No"

                table.add_row(
                    ticker,
                    Text(signal, style=signal_style),
                    row["trade_date"] or "-",
                    row["status"] or "-",
                    correct_val,
                )
            else:
                table.add_row(ticker, "-", "-", "-", "")

    return table


def _build_memory_table(db_path: str) -> Table:
    """Build a table showing memory counts per agent."""
    table = Table(title="Memory Stats", expand=True)
    table.add_column("Agent", style="bold")
    table.add_column("Memories", justify="right")

    with safe_get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT agent_name, COUNT(*) as cnt FROM memories "
            "GROUP BY agent_name ORDER BY cnt DESC"
        ).fetchall()

    if not rows:
        table.add_row("(none)", "0")
    else:
        for row in rows:
            table.add_row(row["agent_name"], str(row["cnt"]))

    return table


def _build_last_run_info(db_path: str) -> Table:
    """Build a table showing the most recent run."""
    table = Table(title="Last Run", expand=True)
    table.add_column("Field", style="bold")
    table.add_column("Value")

    with safe_get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, ticker, trade_date, strategy, signal, status, "
            "duration_seconds, created_at FROM runs "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

    if not row:
        table.add_row("Status", "No runs yet")
        return table

    table.add_row("Run ID", row["id"] or "-")
    table.add_row("Ticker", row["ticker"] or "-")
    table.add_row("Date", row["trade_date"] or "-")
    table.add_row("Strategy", row["strategy"] or "-")

    signal = row["signal"] or "-"
    table.add_row("Signal", Text(signal, style=_signal_style(signal)))
    table.add_row("Status", row["status"] or "-")

    duration = row["duration_seconds"]
    if duration is not None:
        table.add_row("Duration", f"{duration:.1f}s")
    else:
        table.add_row("Duration", "-")

    table.add_row("Created", row["created_at"] or "-")

    return table


def render_signal_board(
    config_path: str = "trading-config.json",
    db_path: str = "trading.db",
) -> Panel:
    """Render the full signal board as a Rich Panel.

    Args:
        config_path: Path to trading-config.json.
        db_path: Path to the SQLite trading database.

    Returns:
        A Rich Panel containing the signal board.
    """
    config = load_config(config_path)

    # Resolve db_path from config if using default
    if db_path == "trading.db":
        db_path = config.get("paths", {}).get("database", "trading.db")

    # Build header line
    halt_status = _build_halt_status(config)
    strategy = _build_strategy_text(config)

    header = Table.grid(expand=True)
    header.add_column()
    header.add_column(justify="right")
    header.add_row(
        Text.assemble("Status: ", halt_status),
        Text.assemble("Strategy: ", strategy),
    )

    # Build sub-sections
    watchlist_table = _build_watchlist_table(config, db_path)
    memory_table = _build_memory_table(db_path)
    last_run_table = _build_last_run_info(db_path)

    # Combine into a grid layout
    layout = Table.grid(expand=True)
    layout.add_column()
    layout.add_row(header)
    layout.add_row("")
    layout.add_row(watchlist_table)
    layout.add_row("")
    layout.add_row(memory_table)
    layout.add_row("")
    layout.add_row(last_run_table)

    return Panel(
        layout,
        title="[bold]OpenClaw Signal Board[/bold]",
        border_style="bold",
        style="default",
        expand=True,
    )


def show_monitor(
    config_path: str = "trading-config.json",
    db_path: str = "trading.db",
) -> None:
    """Print the signal board to the terminal.

    Args:
        config_path: Path to trading-config.json.
        db_path: Path to the SQLite trading database.
    """
    console = Console()
    panel = render_signal_board(config_path, db_path)
    console.print(panel)
