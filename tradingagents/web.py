"""FastAPI dashboard bridge for the local paper-trading engine."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tradingagents.agents.pipeline import AgentPipeline
from tradingagents.config import settings
from tradingagents.data.market import WATCHLIST, fetch_candles
from tradingagents.execution.engine import PaperEngine
from tradingagents.models import Candle, Signal

WEB_DIR = Path(__file__).with_name("web")
TIMEFRAME_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aggregate(candles: list[Candle], timeframe: str) -> list[Candle]:
    """Aggregate available bars into timeframe buckets without inventing source data."""
    factor = max(1, TIMEFRAME_MINUTES[timeframe] // 1)
    if factor == 1:
        return candles[-240:]
    result: list[Candle] = []
    for offset in range(0, len(candles), factor):
        chunk = candles[offset:offset + factor]
        if not chunk:
            continue
        result.append(Candle(chunk[-1].timestamp, chunk[0].open, max(c.high for c in chunk), min(c.low for c in chunk), chunk[-1].close, sum(c.volume for c in chunk)))
    return result[-240:]


def _trade_dict(trade: Any) -> dict[str, Any]:
    return {"id": trade.id, "symbol": trade.symbol, "side": trade.side, "entry": trade.entry, "stop_loss": trade.stop_loss, "tp1": trade.tp1, "tp2": trade.tp2, "quantity": trade.quantity, "remaining_quantity": trade.remaining_quantity, "status": trade.status, "realized_pnl": trade.realized_pnl, "opened_at": trade.opened_at}


class StepRequest(BaseModel):
    """Request a single analysis and optional local paper fill."""
    symbol: str = Field(min_length=2, max_length=12)
    paper: bool = True


class DashboardService:
    """Coordinates read-only views and explicitly simulated analysis steps."""

    def __init__(self) -> None:
        self.engine = PaperEngine(settings.database, settings.initial_equity, settings.risk_per_trade)
        self.pipeline = AgentPipeline()
        self.lock = RLock()
        self.activity: deque[dict[str, Any]] = deque(maxlen=100)
        self.last_signal: dict[str, Any] | None = None
        self.last_latency_ms = 0

    def record(self, role: str, status: str, message: str, **extra: Any) -> None:
        self.activity.append({"timestamp": _timestamp(), "role": role, "status": status, "message": message, **extra})

    def market(self, symbol: str, timeframe: str) -> dict[str, Any]:
        key = symbol.upper()
        if key not in WATCHLIST:
            raise ValueError(f"unsupported symbol {symbol}")
        bars = _aggregate(fetch_candles(key, count=240, source=settings.data_source), timeframe)
        last = bars[-1]
        # Illustrative synthetic depth levels; not an exchange order book.
        half_spread = max((last.high - last.low) * 0.08, last.close * 0.0001)
        bids = [{"price": round(last.close - half_spread * i, 8), "size": round(last.volume * (0.12 / i), 4)} for i in range(1, 6)]
        asks = [{"price": round(last.close + half_spread * i, 8), "size": round(last.volume * (0.10 / i), 4)} for i in range(1, 6)]
        return {"symbol": key, "timeframe": timeframe, "source": "synthetic fallback or Yahoo Finance; depth is illustrative", "candles": [{"time": c.timestamp, "open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume} for c in bars], "snapshot": {"last": last.close, "change_pct": (last.close / bars[-2].close - 1) * 100 if len(bars) > 1 else 0, "spread": asks[0]["price"] - bids[0]["price"], "bids": bids, "asks": asks}, "levels": self.last_signal if self.last_signal and self.last_signal["symbol"] == key else None}

    def state(self) -> dict[str, Any]:
        stats = self.engine.stats()
        trades = self.engine.open_positions()
        return {"paper_only": True, "status": "online", "timestamp": _timestamp(), "stats": {"pnl": stats.pnl, "pnl_pct": stats.pnl_pct, "trades": stats.trades, "win_rate": stats.win_rate, "avg_duration_seconds": stats.avg_duration_seconds, "equity": stats.equity, "open_positions": stats.open_positions}, "positions": [_trade_dict(t) for t in trades], "activity": list(reversed(self.activity)), "fills": self.engine.recent_event_records(30), "agents": self._agents()}

    def _agents(self) -> list[dict[str, str]]:
        latest = {item["role"]: item for item in self.activity}
        return [latest.get(role, {"role": role, "status": "idle", "message": message, "timestamp": "—"}) for role, message in [("analyst", "Waiting for analysis"), ("sentiment/news", "Mock context; no news feed configured"), ("risk", "Paper risk checks enabled"), ("execution", "Local simulated execution only")]]

    def step(self, symbol: str, paper: bool = True) -> dict[str, Any]:
        key = symbol.upper()
        if key not in WATCHLIST:
            raise ValueError(f"unsupported symbol {symbol}")
        with self.lock:
            self.record("analyst", "running", f"Analyzing {key}")
            candles = fetch_candles(key, count=120, source=settings.data_source)
            result = self.pipeline.analyze(key, candles)
            signal = result.signal
            self.last_latency_ms = signal.latency_ms
            self.record("analyst", "complete", f"{key}: {signal.action} · confidence {signal.confidence:.0%}", tokens=signal.agent_tokens.get("analyst team", 0))
            self.record("sentiment/news", "mock", "No news provider configured; sentiment context is neutral")
            self.record("risk", "complete", f"Risk review complete · entry {signal.entry:.6g}, SL {signal.stop_loss:.6g}", tokens=signal.agent_tokens.get("risk review", 0))
            fill = None
            if paper and signal.action != "HOLD":
                trade = self.engine.open_trade(signal)
                if trade:
                    fill = _trade_dict(trade)
                    self.record("execution", "paper", f"order filled · {trade.side} {key} · paper quantity {trade.quantity:.6g}")
                else:
                    self.record("execution", "skipped", "Existing paper position or no eligible order")
            else:
                self.record("execution", "paper", "No simulated order submitted" if not paper else "HOLD · no paper position opened")
            self.engine.update_price(key, candles[-1].close)
            self.last_signal = {"symbol": signal.symbol, "action": signal.action, "confidence": signal.confidence, "entry": signal.entry, "stop_loss": signal.stop_loss, "tp1": signal.take_profit_1, "tp2": signal.take_profit_2, "latency_ms": signal.latency_ms, "tokens": signal.agent_tokens, "rationale": signal.rationale}
            return {"signal": self.last_signal, "fill": fill, "state": self.state()}


service = DashboardService()
app = FastAPI(title="Cee Bot Paper Dashboard", version="1.0.0", description="Local paper-trading dashboard; no live broker execution.")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "paper_only": True, "timestamp": _timestamp()}


@app.get("/api/symbols")
def symbols() -> list[dict[str, str]]:
    return [{"symbol": key, "market": value[1]} for key, value in WATCHLIST.items()]


@app.get("/api/market/{symbol}")
def market(symbol: str, timeframe: str = Query("1m")) -> dict[str, Any]:
    if timeframe not in TIMEFRAME_MINUTES:
        raise HTTPException(422, "timeframe must be one of 1m, 5m, 15m, 1h, 1d")
    try:
        return service.market(symbol, timeframe)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/state")
def state() -> dict[str, Any]:
    return service.state()


@app.post("/api/step")
def step(request: StepRequest) -> dict[str, Any]:
    try:
        return service.step(request.symbol, request.paper)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
