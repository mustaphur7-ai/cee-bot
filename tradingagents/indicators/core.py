"""Small dependency-light technical indicator calculations."""
from __future__ import annotations

from tradingagents.models import Candle


def calculate_indicators(candles: list[Candle], period: int = 14) -> dict[str, float | list[float]]:
    """Return RSI-like Ultimate RSI, normalized momentum, and momentum zones."""
    if len(candles) < 2:
        raise ValueError("at least two candles are required")
    closes = [c.close for c in candles]
    changes = [b - a for a, b in zip(closes, closes[1:])]
    window = changes[-period:]
    gains = sum(max(v, 0.0) for v in window) / max(len(window), 1)
    losses = sum(max(-v, 0.0) for v in window) / max(len(window), 1)
    rsi = 50.0 if gains == 0 and losses == 0 else 100.0 if losses == 0 else 0.0 if gains == 0 else 100 - 100 / (1 + gains / losses)
    baseline = closes[max(0, len(closes) - period - 1)]
    momentum = 100 * (closes[-1] - baseline) / baseline if baseline else 0.0
    returns = [100 * value / closes[i] if closes[i] else 0.0 for i, value in enumerate(changes)]
    zones = [1.0 if x > 0.1 else -1.0 if x < -0.1 else 0.0 for x in returns]
    return {"ultimate_rsi": float(rsi), "momentum": float(momentum), "momentum_zones": zones}


def position_size(equity: float, risk_fraction: float, entry: float, stop: float, max_notional_fraction: float = 1.0) -> float:
    """Calculate units risking at most equity*risk_fraction, with a notional cap."""
    if equity <= 0 or entry <= 0 or not 0 < risk_fraction <= 0.05 or not 0 < max_notional_fraction <= 1:
        raise ValueError("invalid equity, entry, risk fraction, or notional cap")
    distance = abs(entry - stop)
    if distance <= 0 or stop <= 0:
        raise ValueError("stop must be positive and distinct from entry")
    return min(equity * risk_fraction / distance, equity * max_notional_fraction / entry)
