# StockSense AI — Market Intelligence & Evaluation

[![CI](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/ci.yml)
[![CodeQL](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/codeql.yml/badge.svg)](https://github.com/AloneRider-pixel/stocksense-ai/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Market-intelligence application for stock analysis, chronological prediction evaluation, monitoring, and a React dashboard.

## Product surface

- JWT-authenticated accounts and user-scoped prediction history.
- Twelve Data market-data integration with server-side provider credentials.
- Feature engineering and expanding-window walk-forward evaluation.
- Prediction generation and prediction-vs-actual reconciliation.
- Redis caching/rate limiting, PostgreSQL persistence, and background workers.
- Reproducible sample-data evaluation and model-evidence verification.

## Architecture

```text
React dashboard
      ↓
FastAPI API
 ├── Auth / authorization
 ├── Market-data service → provider
 ├── Predictor → Redis / PostgreSQL
 └── Evaluation APIs
      ↓
Background workers
```

## Evaluation contract

Evaluation is chronological: each evaluated period is restricted to information available before that period. CI exercises the checked-in sample dataset and verifies the resulting evidence metadata.

Sample-fixture results are reproducibility evidence, not universal or production performance claims.

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
python scripts/verify_sample_evidence.py
```

For the deterministic sample run:

```bash
python -m app.services.training --data-path data/sample_prices.csv --limit 1000 --model-version ci-sample-v1
```

## Security

Passwords are hashed, JWT-protected endpoints are user-scoped, provider secrets remain server-side, request validation is enforced, and Redis-backed rate limits protect API paths.

See [docs/security.md](docs/security.md) and [SECURITY.md](SECURITY.md).

## Limitations

Predictions are informational and are not investment advice. Meaningful model claims require representative historical data, leakage-safe evaluation, baseline comparison, data provenance, and a reproducible experiment.

## Documentation

- [Architecture](docs/architecture.md)
- [Model evaluation](docs/model-evaluation.md)
- [Testing](docs/testing.md)
- [Security](docs/security.md)
- [Operations](docs/operations.md)
- [Engineering decisions](docs/engineering-decisions.md)

## Maintenance standard

Preserve chronological evaluation boundaries, user-data isolation, provider-secret separation, deterministic evidence, and safe rate limiting.

## License

MIT
