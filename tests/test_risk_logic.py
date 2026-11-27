"""Risk sizing invariants."""
import pytest
from tradingagents.indicators.core import position_size


def test_position_size_respects_risk_budget():
    qty = position_size(10_000, 0.01, 100, 95)
    assert qty == pytest.approx(20)
    assert qty * 5 == pytest.approx(200)


def test_position_size_caps_notional():
    assert position_size(1_000, 0.01, 100, 99, 0.5) == pytest.approx(5)


@pytest.mark.parametrize("args", [(0, .01, 100, 90), (1000, 0, 100, 90), (1000, .01, 100, 100), (1000, .06, 100, 90)])
def test_invalid_risk_inputs_rejected(args):
    with pytest.raises(ValueError):
        position_size(*args)
