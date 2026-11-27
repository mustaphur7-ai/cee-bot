"""SQLite-backed simulator. It has no broker or live-order functionality."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tradingagents.indicators.core import position_size
from tradingagents.models import Signal, Trade, TradeStats


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PaperEngine:
    """Execute simulated fills and persist positions/events locally in SQLite."""

    def __init__(self, database: str | Path = "paper_trades.sqlite3", initial_equity: float = 10_000.0, risk_fraction: float = 0.01):
        if initial_equity <= 0 or not 0 < risk_fraction <= 0.05:
            raise ValueError("invalid paper equity or risk fraction")
        self.database = str(database)
        self.initial_equity = initial_equity
        self.risk_fraction = risk_fraction
        Path(self.database).parent.mkdir(parents=True, exist_ok=True) if self.database != ":memory:" else None
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL, entry REAL NOT NULL, stop_loss REAL NOT NULL, tp1 REAL NOT NULL, tp2 REAL NOT NULL, quantity REAL NOT NULL, remaining_quantity REAL NOT NULL, status TEXT NOT NULL, realized_pnl REAL NOT NULL DEFAULT 0, opened_at TEXT NOT NULL, closed_at TEXT, tp1_hit INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, trade_id INTEGER, timestamp TEXT NOT NULL, message TEXT NOT NULL);
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        return db

    @property
    def equity(self) -> float:
        return self.initial_equity + self.stats().pnl

    def open_trade(self, signal: Signal) -> Trade | None:
        """Open a simulated market fill; HOLD signals do nothing."""
        if signal.action == "HOLD":
            return None
        if signal.entry <= 0 or signal.stop_loss <= 0 or signal.take_profit_1 <= 0 or signal.take_profit_2 <= 0:
            raise ValueError("prices must be positive")
        long = signal.action == "BUY"
        if (long and not signal.stop_loss < signal.entry < signal.take_profit_1 < signal.take_profit_2) or (not long and not signal.stop_loss > signal.entry > signal.take_profit_1 > signal.take_profit_2):
            raise ValueError("signal levels are inconsistent with its side")
        with self._connect() as db:
            if db.execute("SELECT 1 FROM trades WHERE symbol=? AND status='open'", (signal.symbol,)).fetchone():
                return None
            equity = self.initial_equity + float(db.execute("SELECT COALESCE(SUM(realized_pnl),0) FROM trades").fetchone()[0])
            qty = position_size(equity, self.risk_fraction, signal.entry, signal.stop_loss)
            cur = db.execute("INSERT INTO trades(symbol,side,entry,stop_loss,tp1,tp2,quantity,remaining_quantity,status,opened_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (signal.symbol, signal.action, signal.entry, signal.stop_loss, signal.take_profit_1, signal.take_profit_2, qty, qty, "open", _now()))
            trade_id = int(cur.lastrowid)
            db.execute("INSERT INTO events(trade_id,timestamp,message) VALUES(?,?,?)", (trade_id, _now(), f"order filled · {signal.action} {signal.symbol} paper"))
            row = db.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            return self._trade(row)

    @staticmethod
    def _trade(row: sqlite3.Row) -> Trade:
        return Trade(row["id"], row["symbol"], row["side"], row["entry"], row["stop_loss"], row["tp1"], row["tp2"], row["quantity"], row["remaining_quantity"], row["status"], row["realized_pnl"], row["opened_at"])

    def open_positions(self) -> list[Trade]:
        """Return currently open local paper positions."""
        with self._connect() as db:
            return [self._trade(row) for row in db.execute("SELECT * FROM trades WHERE status='open' ORDER BY id")]

    def recent_event_records(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return timestamped recent paper-order events for dashboard consumers."""
        if limit < 1:
            return []
        with self._connect() as db:
            rows = db.execute("SELECT timestamp,message,trade_id FROM events ORDER BY id DESC LIMIT ?", (min(limit, 500),)).fetchall()
            return [{"timestamp": row["timestamp"], "message": row["message"], "trade_id": row["trade_id"]} for row in reversed(rows)]

    def update_price(self, symbol: str, price: float) -> list[str]:
        """Advance open paper positions against a price; TP1 realizes half and moves SL to entry."""
        if price <= 0:
            raise ValueError("price must be positive")
        messages: list[str] = []
        with self._connect() as db:
            rows = db.execute("SELECT * FROM trades WHERE symbol=? AND status='open'", (symbol.upper(),)).fetchall()
            for row in rows:
                long = row["side"] == "BUY"
                hit_stop = price <= row["stop_loss"] if long else price >= row["stop_loss"]
                hit_tp1 = price >= row["tp1"] if long else price <= row["tp1"]
                hit_tp2 = price >= row["tp2"] if long else price <= row["tp2"]
                if hit_stop:
                    qty = row["remaining_quantity"]
                    pnl = (price - row["entry"]) * qty * (1 if long else -1)
                    total = row["realized_pnl"] + pnl
                    db.execute("UPDATE trades SET realized_pnl=?,remaining_quantity=0,status='closed',closed_at=? WHERE id=?", (total, _now(), row["id"]))
                    msg = f"closed {row['side'].lower()} {total / max(row['entry'] * row['quantity'],1e-12) * 100:+.2f}% · stop"
                elif hit_tp2:
                    qty = row["remaining_quantity"]
                    pnl = (price - row["entry"]) * qty * (1 if long else -1)
                    total = row["realized_pnl"] + pnl
                    db.execute("UPDATE trades SET realized_pnl=?,remaining_quantity=0,status='closed',closed_at=? WHERE id=?", (total, _now(), row["id"]))
                    msg = f"closed {row['side'].lower()} {total / max(row['entry'] * row['quantity'],1e-12) * 100:+.2f}% · TP2"
                elif hit_tp1 and not row["tp1_hit"]:
                    partial = row["quantity"] * 0.5
                    pnl = (row["tp1"] - row["entry"]) * partial * (1 if long else -1)
                    db.execute("UPDATE trades SET realized_pnl=realized_pnl+?,remaining_quantity=remaining_quantity-?,stop_loss=entry,tp1_hit=1 WHERE id=?", (pnl, partial, row["id"]))
                    msg = "TP1 hit → stop→breakeven"
                else:
                    continue
                db.execute("INSERT INTO events(trade_id,timestamp,message) VALUES(?,?,?)", (row["id"], _now(), msg))
                messages.append(msg)
        return messages

    def recent_events(self, limit: int = 20) -> list[str]:
        """Return event messages, preserving the original CLI interface."""
        return [row["message"] for row in self.recent_event_records(limit)]

    def stats(self) -> TradeStats:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM trades ORDER BY id").fetchall()
            closed = [r for r in rows if r["status"] == "closed"]
            pnl = sum(r["realized_pnl"] for r in rows)
            wins = sum(r["realized_pnl"] > 0 for r in closed)
            durations = []
            for row in closed:
                try:
                    durations.append((datetime.fromisoformat(row["closed_at"]) - datetime.fromisoformat(row["opened_at"])).total_seconds())
                except (TypeError, ValueError):
                    pass
            return TradeStats(pnl, pnl / self.initial_equity * 100, len(rows), wins / len(closed) if closed else 0.0, sum(durations) / len(durations) if durations else 0.0, self.initial_equity + pnl, sum(r["status"] == "open" for r in rows))
