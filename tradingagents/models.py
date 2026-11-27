"""Shared domain models for market data, signals, and paper positions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Action = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Signal:
    symbol: str
    action: Action
    confidence: float
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    rationale: str
    agent_tokens: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0


@dataclass(frozen=True)
class Trade:
    id: int
    symbol: str
    side: str
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    quantity: float
    remaining_quantity: float
    status: str
    realized_pnl: float
    opened_at: str


@dataclass(frozen=True)
class TradeStats:
    pnl: float
    pnl_pct: float
    trades: int
    win_rate: float
    avg_duration_seconds: float
    equity: float
    open_positions: int


@dataclass(frozen=True)
class AgentNote:
    name: str
    summary: str
    tokens: int
