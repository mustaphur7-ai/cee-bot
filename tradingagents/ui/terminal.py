"""Terminal dashboard components using Rich."""
from __future__ import annotations

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from tradingagents.execution.engine import PaperEngine
from tradingagents.models import Signal


def render_header(console: Console) -> None:
    console.print(Panel(Text("● live · paper", style="bold green") + Text("     CEE BOT · MULTI-AGENT SIMULATOR", style="bold white"), box=box.ROUNDED, border_style="cyan"))


def render_pipeline(console: Console, signal: Signal) -> None:
    progress = Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(bar_width=22), TextColumn("{task.completed}%"), TextColumn("{task.fields[tokens]} tokens"), console=console, transient=False)
    with progress:
        for name, tokens in signal.agent_tokens.items():
            task = progress.add_task(name, total=100, tokens=tokens)
            progress.update(task, completed=100)


def render_signal(console: Console, signal: Signal) -> None:
    table = Table(title=f"{signal.symbol} · agent decision", box=box.ROUNDED)
    for column in ("Action", "Size", "Entry", "SL", "TP1", "TP2", "Confidence"):
        table.add_column(column)
    table.add_row(signal.action, "risk-based on fill", f"{signal.entry:.5g}", f"{signal.stop_loss:.5g}", f"{signal.take_profit_1:.5g}", f"{signal.take_profit_2:.5g}", f"{signal.confidence:.0%}")
    console.print(table)
    console.print(signal.rationale, style="dim")


def render_dashboard(console: Console, engine: PaperEngine, signal: Signal | None = None) -> None:
    render_header(console)
    if signal:
        render_pipeline(console, signal)
        render_signal(console, signal)
    events = Table(title="Paper order log", box=box.ROUNDED)
    events.add_column("Recent events")
    for event in engine.recent_events(8) or ["No simulated fills yet"]:
        events.add_row(event)
    console.print(events)
    stats = engine.stats()
    latency = f"{signal.latency_ms}ms" if signal else "--"
    avg = f"{stats.avg_duration_seconds:.1f}s" if stats.trades else "--"
    console.print(f"pnl {stats.pnl_pct:+.1f}% paper · trades {stats.trades} · avg {avg} · latency {latency}", style="bold cyan")
