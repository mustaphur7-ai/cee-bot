"""Dashboard API smoke tests; all execution stays inside a temporary paper DB."""
from fastapi.testclient import TestClient

from tradingagents import web


def test_health_and_symbols_are_paper_only():
    client = TestClient(web.app)
    assert client.get("/api/health").json()["paper_only"] is True
    symbols = {row["symbol"] for row in client.get("/api/symbols").json()}
    assert {"BTC", "ETH", "SOL", "EURUSD", "GBPUSD", "USDJPY", "SPX", "NDX", "XAUUSD", "XAGUSD"} <= symbols


def test_market_snapshot_and_timeframe_validation():
    client = TestClient(web.app)
    response = client.get("/api/market/BTC?timeframe=5m")
    assert response.status_code == 200
    body = response.json()
    assert body["candles"]
    assert body["snapshot"]["bids"] and body["snapshot"]["asks"]
    assert client.get("/api/market/BTC?timeframe=10y").status_code == 422


def test_step_runs_pipeline_without_live_execution(monkeypatch, tmp_path):
    service = web.DashboardService()
    from tradingagents.execution.engine import PaperEngine
    service.engine = PaperEngine(tmp_path / "dashboard.db")
    monkeypatch.setattr(web, "service", service)
    client = TestClient(web.app)
    response = client.post("/api/step", json={"symbol": "BTC", "paper": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["paper_only"] is True
    assert payload["signal"]["action"] in {"BUY", "SELL", "HOLD"}
    assert all(item["role"] in {"analyst", "sentiment/news", "risk", "execution"} for item in payload["state"]["activity"])
    assert client.get("/api/state").json()["paper_only"] is True
