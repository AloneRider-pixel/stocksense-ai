# StockSense AI — Market Intelligence & Evaluation

[![CI](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/codeql.yml)
[![coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FAloneRider-pixel%2Fstocksense-ai%2Fbadges%2Fcoverage.json)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Live demo:** [stocksense-ai-demo.onrender.com](https://stocksense-ai-demo.onrender.com) (one-click demo sign-in, no account setup)

StockSense AI is an India-first model-evaluation sandbox: it makes next-trading-day close forecasts for the NIFTY 50 universe (NSE equities), precious metals (spot gold and silver), and INR currency pairs (USD/INR, EUR/INR, GBP/INR), stores every forecast, and scores each one against the real close when it lands.
The point is not the model; it is the evaluation discipline: measured error is always reported next to naive baselines (last-close persistence) and the NIFTY 50 index over the same windows, and nothing is deleted or restated.
Built solo by [Himanshu Bisht](https://github.com/AloneRider-pixel) to demonstrate a production-shaped FastAPI + React system with honest, chronological model evaluation.

**Research and engineering project. Not investment advice. Not a SEBI-registered research analyst or investment adviser. Past model performance does not indicate future results. Do not trade on this.**

**Stack:** FastAPI · PostgreSQL · Redis · scikit-learn · React/Vite · Docker · GitHub Actions

**API:** [interactive docs (Swagger)](https://stocksense-ai-zvo7.onrender.com/docs) · [endpoint guide with real examples](docs/api.md)

## Try it in 2 minutes

1. Open the [live demo](https://stocksense-ai-demo.onrender.com). First load can take up to a minute on free-tier hosting.
2. Click **Live dashboard** - one click signs you into the shared demo account.
3. Pick an instrument pill (NIFTY 50 stock, gold, silver, or an INR pair) and press **Run prediction**, or open **Backtest** to see the model strategy vs buy-and-hold on real stored bars.
4. Check the landing-page track record: every prediction is stored and scored against the real close, next to naive baselines.

## Live demo

Try the deployed app: [stocksense-ai-demo.onrender.com](https://stocksense-ai-demo.onrender.com)

| | |
|---|---|
| Email | `demo@stocksense.app` |
| Password | `Demo1234!` |

![StockSense AI dashboard](docs/screenshots/dashboard.png)

The demo serves real daily market data (Yahoo Finance for NSE equities, the NIFTY 50 index, metals, and FX; Twelve Data for optional US symbols; bars may be delayed). Metals are USD spot indications, not MCX futures. FX rates are indicative interbank levels, not executable prices. The live track record builds as stored forecasts are reconciled against real closes.

## Honest limits

- **Free-tier hosting:** the demo sleeps when idle; first load can take up to a minute while the instance wakes.
- **Demo, not production:** the deployed instance handles demo traffic only; nothing here is load-tested for production use.
- **Backtest assumptions disclosed:** walk-forward out-of-sample, long/flat, no transaction costs, no shorting, no leverage. Past performance does not guarantee future results.
- **Track record starts empty:** a fresh deployment has no scored predictions yet; the accuracy cards fill in as real closes arrive. That is the honest state, not a bug.

## What it demonstrates

- JWT-authenticated accounts with user-scoped prediction history.
- Server-side Twelve Data integration and provider-secret isolation.
- Feature engineering with expanding-window walk-forward evaluation.
- Prediction generation and prediction-vs-actual reconciliation.
- Redis caching/rate limiting, PostgreSQL persistence, and background workers.
- Reproducible sample-data evaluation and evidence verification.
- India-first instrument registry: NIFTY 50 constituents, the NIFTY 50 index, spot gold/silver, and USD/INR, EUR/INR, GBP/INR pairs (INR, Asia/Kolkata, NSE holiday calendar).
- Public accuracy endpoint and landing-page track record comparing live tracked forecasts against last-close persistence and the NIFTY 50 index over the same windows.
- Walk-forward backtest view: long/flat model strategy vs buy-and-hold equity curve with max drawdown, assumptions disclosed.

## Architecture

```mermaid
graph TB
    UI[React Dashboard] --> API[FastAPI]
    API --> AUTH[Auth / authorization]
    API --> DATA[Market Data Provider]
    API --> MODEL[Prediction / feature pipeline]
    MODEL --> REDIS[(Redis)]
    MODEL --> PG[(PostgreSQL)]
    API --> EVAL[Evaluation APIs]
    WORKER[Background Worker] --> MODEL
```

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Python |
| Data | PostgreSQL, SQLAlchemy, Alembic |
| Cache / limits | Redis |
| ML | scikit-learn / feature pipeline |
| Market data | Twelve Data |
| Frontend | React, Vite |
| Delivery | Docker, GitHub Actions |

## Evaluation contract

Evaluation is chronological: each prediction period is restricted to information available before that period. Sample-fixture results are reproducibility evidence, not universal or production performance claims.

A credible model-quality claim should include:
- a representative dataset and provenance;
- leakage controls and temporal boundaries;
- a baseline comparison;
- the metric definition and sample count;
- the environment/model version; and
- the producing commit or experiment artifact.

## Quick start

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Full stack (local development only):

```bash
docker compose up --build
```

The sample values in `.env.example` and `docker-compose.yml` are development-only. The full-stack Compose ports bind to localhost, and production mode rejects placeholder JWT secrets, weak or local database URLs, unsecured Redis URLs, wildcard/local hosts, invalid database URLs, and non-HTTPS or wildcard CORS origins. See [the deployment guide](docs/deployment.md) before configuring production services.

## Verification

```bash
make lint
make test
make build-frontend
python scripts/verify_sample_evidence.py
```

For the deterministic sample pipeline:

```bash
python -m app.services.training --data-path data/sample_prices.csv --limit 1000 --model-version ci-sample-v1
```

## Security

Passwords are hashed, protected endpoints are user-scoped, provider secrets remain server-side, request validation is enforced, and Redis-backed rate limits protect API paths.

See [docs/security.md](docs/security.md), [docs/deployment.md](docs/deployment.md), and [SECURITY.md](SECURITY.md).

## Limitations

Forecasts are informational and are not investment advice. Backtest results can fail to generalize. Avoid presenting sample fixtures or historical simulations as guarantees of future market behavior.

- **NIFTY 50 universe is a snapshot:** index membership changes; the registry in `app/market_data/symbols.py` is the source of truth and can be refreshed.
- **Metals are spot, not MCX:** gold and silver are delayed USD spot indications from Yahoo Finance, not Indian exchange-traded contracts.
- **FX is indicative:** currency pairs are delayed interbank indications, not executable prices.
- **Data may be delayed:** providers used for the demo do not guarantee real-time or error-free data.

## Regulatory note

This is a personal research and engineering project. It is not investment advice, research-analyst output, or a recommendation to buy or sell any security, commodity, or currency. The operator is not a SEBI-registered research analyst or investment adviser. Past model performance does not indicate future results. Do not trade on this.

## Documentation

- [Architecture](docs/architecture.md)
- [Model evaluation](docs/model-evaluation.md)
- [Testing](docs/testing.md)
- [Security](docs/security.md)
- [Operations](docs/operations.md)
- [Deployment](docs/deployment.md)
- [Engineering decisions](docs/engineering-decisions.md)

## Contribution standard

Preserve chronological evaluation boundaries, user-data isolation, provider-secret separation, deterministic evidence, and rate limiting. Behavioral changes should add or update regression tests.

## License

MIT
