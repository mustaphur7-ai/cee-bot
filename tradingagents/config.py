"""Application settings loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Validated, environment-backed paper trading configuration."""

    offline: bool = os.getenv("TRADINGAGENTS_OFFLINE", "true").lower() not in {"0", "false", "no"}
    provider: str = os.getenv("TRADINGAGENTS_PROVIDER", "mock").lower()
    base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    database: str = os.getenv("TRADINGAGENTS_DB", "paper_trades.sqlite3")
    initial_equity: float = _float_env("TRADINGAGENTS_INITIAL_EQUITY", 10_000.0)
    risk_per_trade: float = _float_env("TRADINGAGENTS_RISK_PER_TRADE", 0.01)
    data_source: str = os.getenv("TRADINGAGENTS_DATA_SOURCE", "auto").lower()

    def __post_init__(self) -> None:
        if self.initial_equity <= 0:
            raise ValueError("initial equity must be positive")
        if not 0 < self.risk_per_trade <= 0.05:
            raise ValueError("risk per trade must be in (0, 0.05]")

    @property
    def db_path(self) -> Path:
        return Path(self.database)


settings = Settings()
