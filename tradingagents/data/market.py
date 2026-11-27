"""Free-data adapter with deterministic synthetic OHLCV fallback."""
from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta, timezone

from tradingagents.models import Candle

WATCHLIST: dict[str, tuple[str, str]] = {
    "BTC": ("BTC-USD", "crypto"), "ETH": ("ETH-USD", "crypto"), "SOL": ("SOL-USD", "crypto"),
    "EURUSD": ("EURUSD=X", "forex"), "GBPUSD": ("GBPUSD=X", "forex"), "USDJPY": ("JPY=X", "forex"),
    "SPX": ("^GSPC", "index"), "NDX": ("^NDX", "index"), "XAUUSD": ("GC=F", "metal"), "XAGUSD": ("SI=F", "metal"),
}
BASE_PRICES = {"BTC": 65000.0, "ETH": 3400.0, "SOL": 150.0, "EURUSD": 1.08, "GBPUSD": 1.27, "USDJPY": 151.0, "SPX": 5200.0, "NDX": 18100.0, "XAUUSD": 2350.0, "XAGUSD": 29.0}


def synthetic_candles(symbol: str, count: int = 120) -> list[Candle]:
    """Generate reproducible synthetic candles; these are not historical market prices."""
    key = symbol.upper()
    if key not in BASE_PRICES:
        raise ValueError(f"unsupported symbol {symbol!r}; choose from {', '.join(WATCHLIST)}")
    seed = int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)
    rng = random.Random(seed)
    price = BASE_PRICES[key]
    now = datetime.now(timezone.utc)
    result: list[Candle] = []
    for i in range(count):
        drift = math.sin(i / 11) * 0.0007
        change = rng.gauss(drift, 0.003 if key in {"BTC", "ETH", "SOL"} else 0.001)
        close = max(price * (1 + change), price * 0.5)
        spread = abs(rng.gauss(0.0015, 0.0005))
        result.append(Candle((now - timedelta(minutes=count - i)).isoformat(), price, max(price, close) * (1 + spread), min(price, close) * (1 - spread), close, rng.uniform(100, 10000)))
        price = close
    return result


def fetch_candles(symbol: str, count: int = 120, source: str = "auto") -> list[Candle]:
    """Fetch daily free Yahoo Finance bars if possible; always fall back to synthetic data."""
    key = symbol.upper()
    if key not in WATCHLIST:
        raise ValueError(f"unsupported symbol {symbol!r}; choose from {', '.join(WATCHLIST)}")
    if source != "synthetic":
        try:
            import yfinance as yf
            ticker = WATCHLIST[key][0]
            frame = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=True, threads=False)
            if not frame.empty:
                frame = frame.tail(count)
                bars = []
                for idx, row in frame.iterrows():
                    def val(col: str) -> float:
                        value = row[col]
                        return float(value.iloc[0] if hasattr(value, "iloc") else value)
                    bars.append(Candle(idx.to_pydatetime().replace(tzinfo=timezone.utc).isoformat(), val("Open"), val("High"), val("Low"), val("Close"), val("Volume")))
                if len(bars) >= 3:
                    return bars
        except Exception:
            pass
    return synthetic_candles(key, count)
