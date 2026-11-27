# Cee Bot — paper trading only

Educational, local-first multi-agent trading simulator. It has **no broker integration and no live order execution**. Market-data access is optional; the synthetic fallback makes every command usable offline. The mock agent pipeline is the default.

> **Educational paper-trading software. Not financial advice.** Paper fills, synthetic prices, and back-of-the-envelope indicators do not represent real execution or future results. This project cannot place real-money trades.

## Install

Python 3.10+ is required.

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
python -m pip install -e '.[dev]'
cp .env.example .env            # Windows: copy .env.example .env
pytest
```

The bot runs without credentials. For an OpenAI-compatible analysis endpoint, set `TRADINGAGENTS_OFFLINE=false`, `TRADINGAGENTS_PROVIDER=openai`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` in `.env`. The provider is only used to request a text analysis; the app parses it conservatively and still routes orders exclusively to its local paper engine. Never enter brokerage credentials.

## Commands

```bash
cee-bot watch                    # list supported markets
cee-bot analyze BTC              # run analyst/debate/risk pipeline once
cee-bot run --interval 5         # paper loop (Ctrl-C to stop)
cee-bot chart BTC --output charts/BTC.png
cee-bot report                   # local SQLite paper-trade report
```

Use `python -m cli.main` instead of `cee-bot` if running from a source checkout without installation. Supported symbols: BTC, ETH, SOL, EURUSD, GBPUSD, USDJPY, SPX, NDX, XAUUSD, XAGUSD. Data uses yfinance when available and falls back to deterministic synthetic OHLCV bars when offline or unavailable.

## Safety and execution model

- This app does not import, configure, or connect to a broker, exchange, wallet, or order-routing API.
- Entries and exits are simulated against locally fetched or synthetic prices and persisted in SQLite.
- Risk-based sizing uses current paper equity, configured risk fraction, and stop distance. A maximum notional cap prevents oversized simulated positions.
- At TP1, half the position is realized and the stop moves to breakeven. Remaining size exits at TP2 or the moved stop.
- Data and signals are illustrative; no profitability is implied.

## Configuration

All settings use `TRADINGAGENTS_` environment variables (see `.env.example`). Defaults: offline mock agents, $10,000 simulated starting equity, 1% risk per trade, and `paper_trades.sqlite3` in the current directory. `TRADINGAGENTS_DATA_SOURCE=synthetic` forces synthetic data; `auto` attempts yfinance first. Database paths are local and should not be shared if they contain personal notes.

## Docker

```bash
docker build -t cee-bot .
docker run --rm -it -v "$PWD:/app" cee-bot watch
```

## Project layout

```text
.github/workflows/ci.yml
assets/logo.svg
assets/screenshot-placeholder.svg
cli/main.py
tradingagents/agents/pipeline.py
tradingagents/data/market.py
tradingagents/indicators/core.py
tradingagents/execution/engine.py
tradingagents/ui/terminal.py
tradingagents/chart.py
tests/
```

Apache-2.0 license. See `LICENSE`.
