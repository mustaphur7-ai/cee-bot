# Cee Bot — paper trading only

Educational, local-first multi-agent simulator with a responsive web terminal and CLI. It has **no broker integration and no live order execution**. Market-data access is optional; synthetic fallback keeps the dashboard usable offline. Agent analysis defaults to mock/offline mode.

> **Educational paper-trading software. Not financial advice.** Paper fills, synthetic prices, and indicators do not represent real execution or future results. This project cannot place real-money trades.

## Install

Python 3.10+ is required.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install -e '.[dev]'
cp .env.example .env            # Windows: copy .env.example .env
pytest
```

## Web dashboard

Start the API and static UI from the repository root:

```bash
uvicorn tradingagents.web:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The backend serves the bundled static frontend and JSON endpoints from the same origin. On first load, the page fetches the supported-symbol watchlist, OHLCV chart, indicative snapshot, paper positions, and activity; it polls local state every five seconds. Choose a symbol/timeframe and click **Run paper analysis** to execute one local analysis step. Only the local SQLite paper engine can receive simulated fills. API docs are available at `/docs`.

The interactive candlestick library is loaded from a pinned lightweight-charts CDN URL; if that CDN is unavailable, the rest of the dashboard/API still works and reports the chart library issue. For offline hosting, vendor `lightweight-charts.standalone.production.js` locally and update the script path in `tradingagents/web/index.html`.

For deployment, install the package with `pip install -e .` and run `uvicorn tradingagents.web:app --host 0.0.0.0 --port 8000`. Configure TLS and authentication at a trusted reverse proxy before exposing any dashboard publicly. The API intentionally provides no authentication layer and should remain local or behind access control.

## CLI

```bash
cee-bot watch
cee-bot analyze BTC
cee-bot analyze BTC --paper
cee-bot run --interval 5         # local paper loop; Ctrl-C to stop
cee-bot chart BTC --output charts/BTC.png
cee-bot report
```

Use `python -m cli.main` instead of `cee-bot` if running from source without installation. Supported symbols: BTC, ETH, SOL, EURUSD, GBPUSD, USDJPY, SPX, NDX, XAUUSD, XAGUSD. Data uses yfinance when available and falls back to synthetic OHLCV. Dashboard timeframes aggregate available source bars; they do not increase source-data resolution.

## Dashboard panels and data semantics

- **Price chart:** interactive lightweight-charts candles, symbol/timeframe selection, and decision entry/SL/TP markers.
- **Snapshot/depth:** indicative bid/ask levels are generated from the latest candle range and volume. This is explicitly synthetic depth, not exchange market depth.
- **Agent activity:** analyst, neutral mock sentiment/news, risk review, and paper execution statuses; no news feed is configured by default.
- **Positions/fills:** actual persisted state/events from the local SQLite engine.
- **One-step execution:** the analysis button may create a paper fill for BUY/SELL and never submits a live order.

## Safety and execution model

- No broker, exchange, wallet, or live order-routing API is imported or called.
- Entries/exits are simulated against fetched or synthetic prices and persisted in SQLite.
- Risk sizing uses configured paper equity and stop distance; the engine applies a notional cap.
- At TP1, half the position is realized and the stop moves to breakeven. Remaining size exits at TP2 or stop.
- Market data, depth snapshot, and agent output are illustrative; no profitability is implied.

## Configuration

Copy `.env.example` to `.env`. Defaults are offline mock agents, $10,000 simulated starting equity, 1% risk per trade, automatic data source, and `paper_trades.sqlite3` in the current directory. `TRADINGAGENTS_DATA_SOURCE=synthetic` forces synthetic bars. An optional OpenAI-compatible text provider can be configured with `TRADINGAGENTS_OFFLINE=false`, `TRADINGAGENTS_PROVIDER=openai`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`; it is not an execution provider. Never enter brokerage credentials. `TRADINGAGENTS_WEB_HOST` and `TRADINGAGENTS_WEB_PORT` document convenient bind settings; specify host/port in the uvicorn command explicitly.

## Docker

```bash
docker build -t cee-bot .
docker run --rm -it -p 8000:8000 -v "$PWD:/app" cee-bot
```

The image's default command is the CLI watchlist; to start the dashboard use:

```bash
docker run --rm -it -p 8000:8000 -v "$PWD:/app" cee-bot uvicorn tradingagents.web:app --host 0.0.0.0 --port 8000
```

## Project layout

```text
.github/workflows/ci.yml
assets/logo.svg
assets/screenshot-placeholder.svg
cli/main.py
tradingagents/agents/pipeline.py
tradingagents/data/market.py
tradingagents/execution/engine.py
tradingagents/indicators/core.py
tradingagents/web.py
tradingagents/web/{index.html,styles.css,app.js}
tests/
```

Apache-2.0 license. See `LICENSE`.
