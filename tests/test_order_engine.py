"""Paper order engine tests use only temporary local SQLite databases."""
from tradingagents.execution.engine import PaperEngine
from tradingagents.models import Signal


def long_signal():
    return Signal("BTC", "BUY", .8, 100, 95, 105, 110, "test")


def test_tp1_partial_and_breakeven_then_tp2(tmp_path):
    engine = PaperEngine(tmp_path / "test.db", 10_000, .01)
    trade = engine.open_trade(long_signal())
    assert trade is not None and trade.quantity == 20
    assert engine.update_price("BTC", 105) == ["TP1 hit → stop→breakeven"]
    current = engine.open_positions()[0]
    assert current.remaining_quantity == 10
    assert current.stop_loss == 100
    messages = engine.update_price("BTC", 110)
    assert len(messages) == 1 and "TP2" in messages[0]
    assert engine.stats().trades == 1
    assert engine.stats().pnl > 0
    assert engine.stats().open_positions == 0


def test_stop_loss_closes_trade(tmp_path):
    engine = PaperEngine(tmp_path / "test.db", 10_000, .01)
    engine.open_trade(long_signal())
    assert "stop" in engine.update_price("BTC", 95)[0]
    assert engine.open_positions() == []


def test_hold_does_not_open_and_duplicate_is_ignored(tmp_path):
    engine = PaperEngine(tmp_path / "test.db")
    hold = Signal("BTC", "HOLD", .5, 100, 95, 105, 110, "none")
    assert engine.open_trade(hold) is None
    assert engine.open_trade(long_signal()) is not None
    assert engine.open_trade(long_signal()) is None
