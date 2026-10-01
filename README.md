# StockSense AI

[![CI](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Market-intelligence platform for stock analysis, next-period prediction, evaluation, and monitoring.

## Product surface

- JWT-authenticated user accounts.
- Configurable market-data ingestion with a Twelve Data integration.
- Technical feature engineering and expanding-window walk-forward evaluation.
- Next-period price prediction and prediction-vs-actual reconciliation.
- Per-user prediction history and evaluation metrics.
- Redis caching/rate limiting, PostgreSQL persistence, background workers, and runtime metrics.
- React dashboard and Dockerized local stack.

## Architecture

```text
React Web App
     ↓
FastAPI
 ├── Auth / authorization
 ├── Market data service → provider
 ├── Prediction service → Redis / PostgreSQL
 └── Evaluation APIs
              ↓
        Background worker
```

## ML evaluation

StockSense uses chronological walk-forward evaluation so each fold trains only on information available before the evaluated period.

CI runs evaluation against the checked-in sample dataset and stores:

- metrics
- model registry metadata
- row-level predictions
- evidence verification output

Live-provider evaluation is explicitly separated into an on-demand workflow and requires the corresponding repository/environment secret.

Do not interpret sample-fixture metrics as universal model performance.

## API surface

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/auth/register` | Register |
| POST | `/api/v1/auth/login` | Authenticate |
| GET | `/api/v1/stocks/{symbol}/history` | Historical market data |
| POST | `/api/v1/stocks/{symbol}/ingest` | Ingest/refresh |
| POST | `/api/v1/predict` | Generate prediction |
| GET | `/api/v1/predictions` | Prediction history |
| GET | `/api/v1/predictions/evaluation` | Reconciled results |
| GET | `/api/v1/health` | Health |
| GET | `/api/v1/metrics` | Runtime metrics |

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

Full stack:

```bash
docker compose up --build
```

## Verification

```bash
make lint
make test
make build-frontend
```

For a deterministic model run:

```bash
python -m app.services.training --data-path data/sample_prices.csv --limit 1000 --model-version ci-sample-v1
python scripts/verify_sample_evidence.py
```

## Security

Passwords are hashed with scrypt; JWTs protect authenticated endpoints; prediction history is user-scoped; Redis rate limiting protects API paths; request validation is enabled; provider secrets remain server-side.

See [docs/security.md](docs/security.md) and [docs/operations.md](docs/operations.md).

## Deployment

The application is containerized for separate web/API/database/cache/worker roles. The repository includes a deployment runbook. Live deployment and uptime claims should only be published with externally measured evidence.

## Limitations

Predictions are informational and are not investment advice. Production model claims require real historical data, leakage-safe evaluation, baseline comparisons, and documented data provenance.

## Review path

Start with [testing](docs/testing.md), [security](docs/security.md), [model evaluation](docs/model-evaluation.md), and [engineering decisions](docs/engineering-decisions.md).

## Maintenance standard

Keep time-series evaluation leakage-safe, user data scoped, provider secrets server-side, and model claims tied to reproducible evidence.

## License

MIT
