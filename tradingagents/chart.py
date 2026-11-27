"""Chart renderer for momentum, RSI, synthetic liquidation intensity, and trade levels."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from tradingagents.indicators.core import calculate_indicators
from tradingagents.models import Candle


def save_chart(symbol: str, candles: list[Candle], output: str | Path, positions: list | None = None) -> Path:
    """Save a PNG chart with indicator panels and illustrative liquidity heatmap."""
    if len(candles) < 2:
        raise ValueError("at least two candles are required")
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    closes = np.array([c.close for c in candles], dtype=float)
    highs = np.array([c.high for c in candles], dtype=float)
    lows = np.array([c.low for c in candles], dtype=float)
    x = np.arange(len(candles))
    ind = calculate_indicators(candles)
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1, 1]})
    ax = axes[0]
    ax.plot(x, closes, color="#0ea5e9", label="close", linewidth=1.5)
    # Heatmap is a synthetic visualization proxy, not exchange liquidation data.
    levels = np.linspace(float(lows.min()), float(highs.max()), 30)
    density = np.zeros((len(levels), len(candles)))
    for i, (lo, hi, candle) in enumerate(zip(lows, highs, candles)):
        band = np.abs(levels - closes[i]) <= max(hi - lo, closes[i] * 0.001)
        density[band, i] = max(candle.volume, 1.0)
    ax.imshow(density, aspect="auto", origin="lower", extent=[0, len(candles) - 1, levels[0], levels[-1]], alpha=0.22, cmap="magma")
    ax.set_title(f"{symbol} · paper analysis (heatmap is illustrative)")
    ax.set_ylabel("Price")
    for trade in positions or []:
        if trade.symbol != symbol.upper():
            continue
        color = "#22c55e" if trade.side == "BUY" else "#ef4444"
        ax.axhspan(min(trade.entry, trade.tp2), max(trade.entry, trade.tp2), color=color, alpha=0.08)
        ax.axhspan(min(trade.entry, trade.stop_loss), max(trade.entry, trade.stop_loss), color="#f97316", alpha=0.12)
        ax.axhline(trade.entry, color=color, linestyle="--", linewidth=0.8)
        ax.text(len(candles) - 1, trade.entry, f" {trade.side} · P&L {trade.realized_pnl:+.2f}", color=color, fontsize=8)
    axes[1].bar(x[1:], ind["momentum_zones"], color=["#22c55e" if z > 0 else "#ef4444" if z < 0 else "#94a3b8" for z in ind["momentum_zones"]], width=1)
    axes[1].set_ylabel("Momentum zone")
    axes[2].plot(x, [ind["ultimate_rsi"]] * len(x), label=f"Ultimate RSI {ind['ultimate_rsi']:.1f}", color="#a855f7")
    axes[2].axhline(70, linestyle="--", color="#ef4444", linewidth=0.8)
    axes[2].axhline(30, linestyle="--", color="#22c55e", linewidth=0.8)
    axes[2].set_ylim(0, 100)
    axes[2].set_ylabel("Ultimate RSI")
    axes[2].set_xlabel("Bar")
    axes[2].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path
