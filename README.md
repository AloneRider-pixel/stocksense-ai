# StockSense AI

[![CI](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Market intelligence platform for stock analysis, next-period prediction, and model-driven monitoring.

StockSense AI is built as a product system rather than a single prediction script. The codebase separates the web client, authenticated API, market-data ingestion, ML evaluation, persistence, asynchronous workers, caching, observability, and operational controls.

## Product

- User accounts with JWT authentication
- Real daily OHLCV ingestion through a configurable market-data provider
- Technical feature engineering and walk-forward model evaluation
- Next-period price prediction
- Prediction-versus-actual reconciliation
- Per-user prediction history and evaluation metrics
- Redis caching and rate limiting
- PostgreSQL persistence
- Background job execution and scheduled refresh
- Prometheus-compatible runtime metrics
- Responsive React dashboard
- Dockerized local stack

## Real market data

The primary integration is Twelve Data. Configure `TWELVE_DATA_API_KEY` and set `MARKET_DATA_PROVIDER=twelve_data`.

Use the ingestion CLI:

    python -m app.market_data.cli --symbol AAPL --limit 500

Or call the authenticated API:

    POST /api/v1/stocks/AAPL/ingest

The provider data is normalized into the internal `MarketBar` contract and persisted in PostgreSQL. Stored rows are keyed by symbol and trading date. The API refreshes stale data automatically, and the background worker refreshes the configured symbol universe on a schedule.

## ML evaluation

Training can use live provider data:

    python -m app.services.training --symbol AAPL --provider twelve_data --limit 1000

The model evaluation uses expanding-window walk-forward validation with scikit-learn `TimeSeriesSplit`. Each fold trains only on earlier observations and evaluates on later observations; random shuffling is avoided because it can produce unrealistic time-series evaluation.

Generated evaluation artifacts contain:

- MAE
- RMSE
- MAPE
- directional accuracy
- last-close baseline MAE
- improvement versus the baseline
- row-level predicted and actual closes for every evaluation observation

The final model is then fit on the available historical training frame and registered with its feature set, dataset source, metrics, timestamp, and model version.

## Prediction-versus-actual tracking

Every persisted prediction records the prediction date. Once a later market bar becomes available, the reconciliation job finds the first subsequent trading bar and stores:

- actual date
- actual close
- absolute error
- percentage error
- directional correctness
- evaluation timestamp

The product exposes:

    GET /api/v1/predictions
    GET /api/v1/predictions/evaluation

## Architecture

    Browser
       │
       ▼
    React Web App
       │
       ▼
    FastAPI
       ├── Auth / Authorization
       ├── Market Data Service ──► Twelve Data
       ├── Prediction Service ───► Redis
       │                       └─► PostgreSQL
       └── Evaluation APIs
                   │
                   ▼
              Redis Queue
                   │
                   ▼
             Background Worker

## Local development

Backend:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    alembic upgrade head
    python -m app.services.training --symbol AAPL --provider twelve_data --limit 1000
    uvicorn app.main:app --reload

Frontend:

    cd frontend
    npm install
    npm run dev

Full stack:

    docker compose up --build

## API

Public:

    POST /api/v1/auth/register
    POST /api/v1/auth/login
    GET  /api/v1/health
    GET  /health/live
    GET  /health/ready

Authenticated:

    GET  /api/v1/auth/me
    GET  /api/v1/stocks/{symbol}/history
    POST /api/v1/stocks/{symbol}/ingest
    POST /api/v1/predict
    GET  /api/v1/predictions
    GET  /api/v1/predictions/evaluation
    GET  /api/v1/metrics

Operational:

    GET /internal/metrics

## Deployment & Metrics

StockSense AI is containerized for separate web, API, database, cache, and worker services. The repository includes `docs/deployment.md` with the deployment runbook and measurement protocol.

**Live URL:** Pending AWS deployment.

Do not publish an uptime claim until it is backed by an external probe window with recorded successes, failures, timestamps, and version identifiers.

For model-performance claims, use the generated walk-forward artifacts from a documented real-data run. The repository's on-demand GitHub Actions workflow is available at `.github/workflows/model-evaluation.yml` and expects a `TWELVE_DATA_API_KEY` repository/environment secret.

## Verification

The repository has separate paths for fast deterministic CI and credentialed live-data evaluation:

- `make lint` — Ruff linting
- `make test` — backend tests
- `make build-frontend` — production frontend build
- `make train-real` — local live-data training
- `.github/workflows/model-evaluation.yml` — on-demand real-data evaluation with downloadable artifacts

See [Testing Strategy](docs/testing.md) and [Engineering Decisions](docs/engineering-decisions.md) for the review rationale behind the validation boundaries.

## Engineering quality

CI runs backend linting and tests plus the frontend production build. CodeQL scans Python and TypeScript/JavaScript on pushes, pull requests, and a scheduled run. Dependabot is configured for Python, frontend npm, and GitHub Actions dependencies.

Database schema changes are managed through Alembic. Background jobs use ARQ and Redis. Runtime health probes distinguish liveness from dependency readiness.

## Security

- Passwords are hashed with scrypt.
- JWT bearer tokens protect product endpoints.
- Prediction history is scoped to the authenticated user.
- Redis-backed rate limiting protects authenticated and public auth endpoints.
- Request validation and structured errors are enabled.
- Secrets are loaded from environment variables and ignored by Git.

See docs/security.md and docs/operations.md for operational details.

## Model limitations

Predictions are informational and are not investment advice. The bundled CSV dataset exists for local reproducibility. Production model claims should be based on real historical data, reproducible walk-forward evaluation, baseline comparisons, and clearly documented data provenance.

## License

MIT
