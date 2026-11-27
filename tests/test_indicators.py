"""Deterministic indicator unit tests."""
from tradingagents.data.market import synthetic_candles
from tradingagents.indicators.core import calculate_indicators


def test_indicator_values_are_finite_and_bounded():
    values = calculate_indicators(synthetic_candles("BTC", 40))
    assert 0 <= values["ultimate_rsi"] <= 100
    assert isinstance(values["momentum"], float)
    assert len(values["momentum_zones"]) == 39


def test_rsi_flat_series_is_neutral():
    from tradingagents.models import Candle
    bars = [Candle(str(i), 10, 10, 10, 10) for i in range(20)]
    assert calculate_indicators(bars)["ultimate_rsi"] == 50
