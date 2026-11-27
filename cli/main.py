"""Cee Bot command line: watch, analyze, run, chart, report."""
from __future__ import annotations

import argparse
import time
from rich.console import Console
from rich.table import Table

from tradingagents.agents.pipeline import AgentPipeline
from tradingagents.config import settings
from tradingagents.data.market import WATCHLIST, fetch_candles
from tradingagents.execution.engine import PaperEngine
from tradingagents.ui.terminal import render_dashboard, render_header, render_signal

console = Console()


def engine() -> PaperEngine:
    return PaperEngine(settings.database, settings.initial_equity, settings.risk_per_trade)


def analyze(symbol: str, execute: bool = False) -> None:
    candles = fetch_candles(symbol, source=settings.data_source)
    result = AgentPipeline().analyze(symbol, candles)
    render_header(console)
    render_signal(console, result.signal)
    if execute:
        paper = engine()
        trade = paper.open_trade(result.signal)
        if trade:
            console.print(f"order filled · {trade.side} {trade.symbol} · simulated quantity {trade.quantity:.6g}", style="green")
        elif result.signal.action == "HOLD":
            console.print("HOLD · no paper position opened", style="yellow")
        else:
            console.print("position already open for this symbol; duplicate ignored", style="yellow")
    render_dashboard(console, engine(), result.signal)


def command_watch(_: argparse.Namespace) -> None:
    render_header(console)
    table = Table(title="Watchlist · free data with synthetic fallback")
    table.add_column("Symbol"); table.add_column("Market"); table.add_column("Last (illustrative / fetched)", justify="right")
    for symbol, (_, market) in WATCHLIST.items():
        close = fetch_candles(symbol, count=3, source=settings.data_source)[-1].close
        table.add_row(symbol, market, f"{close:.5g}")
    console.print(table)


def command_analyze(args: argparse.Namespace) -> None:
    analyze(args.symbol, execute=args.paper)


def command_run(args: argparse.Namespace) -> None:
    paper = engine()
    render_header(console)
    console.print("Paper loop started. Ctrl-C to stop; no live orders are possible.", style="bold yellow")
    try:
        while True:
            for symbol in args.symbols or list(WATCHLIST):
                candles = fetch_candles(symbol, source=settings.data_source)
                signal = AgentPipeline().analyze(symbol, candles).signal
                # The engine is only ever the local simulated engine.
                paper.open_trade(signal)
                paper.update_price(symbol, candles[-1].close)
                render_dashboard(console, paper, signal)
            time.sleep(max(args.interval, 1))
    except KeyboardInterrupt:
        console.print("Paper loop stopped.", style="yellow")


def command_chart(args: argparse.Namespace) -> None:
    from tradingagents.chart import save_chart
    candles = fetch_candles(args.symbol, source=settings.data_source)
    path = save_chart(args.symbol.upper(), candles, args.output, engine().open_positions())
    console.print(f"Saved chart: {path}")


def command_report(_: argparse.Namespace) -> None:
    paper = engine(); stats = paper.stats(); render_header(console)
    table = Table(title="Paper trading report")
    table.add_column("Metric"); table.add_column("Value", justify="right")
    table.add_row("Equity", f"${stats.equity:,.2f}"); table.add_row("Realized P&L", f"${stats.pnl:+,.2f} ({stats.pnl_pct:+.2f}%)")
    table.add_row("Trades", str(stats.trades)); table.add_row("Open positions", str(stats.open_positions)); table.add_row("Win rate", f"{stats.win_rate:.1%}"); table.add_row("Avg closed duration", f"{stats.avg_duration_seconds:.1f}s")
    console.print(table)
    for event in paper.recent_events(20): console.print(event, style="dim")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cee-bot", description="Educational multi-agent paper-trading simulator; never executes live orders.")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("watch", help="show supported-symbol watchlist")
    item = subs.add_parser("analyze", help="analyze one symbol"); item.add_argument("symbol", choices=WATCHLIST); item.add_argument("--paper", action="store_true", help="simulate a fill if signal is BUY or SELL")
    loop = subs.add_parser("run", help="run the local paper loop"); loop.add_argument("--interval", type=int, default=5); loop.add_argument("--symbols", nargs="+", choices=WATCHLIST)
    chart = subs.add_parser("chart", help="save an analysis chart as PNG"); chart.add_argument("symbol", choices=WATCHLIST); chart.add_argument("--output", default="charts/chart.png")
    subs.add_parser("report", help="show local SQLite paper statistics")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    {"watch": command_watch, "analyze": command_analyze, "run": command_run, "chart": command_chart, "report": command_report}[args.command](args)


if __name__ == "__main__":
    main()
