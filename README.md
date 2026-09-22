# StockSense AI

AI-assisted stock analysis and next-period price prediction platform built with **Python, FastAPI, PostgreSQL, Redis, and scikit-learn**.

> Portfolio note: measured performance claims are documented only when they can be reproduced from the repository's evaluation workflow.

## Current capabilities

- Historical OHLCV data pipeline using Pandas.
- Technical feature engineering: daily return, 5-day return, moving-average ratios, volatility, and volume change.
- Chronological 80/20 train-test evaluation to avoid random time-series shuffling.
- Random Forest regression for next-period close prediction.
- FastAPI prediction, history, health, and model-metrics endpoints.
- Redis caching with graceful failure handling.
- PostgreSQL persistence for prediction history.
- SQLAlchemy data-access layer with an explicit repository boundary.
- Automated tests with PyTest.
- GitHub Actions CI.
- Docker and Docker Compose for local infrastructure.

## Architecture

    Market Data (CSV/API)
            │
            ▼
      Feature Engineering
            │
            ├──────────────► Training / Evaluation
            │                       │
            │                       ▼
            │                Random Forest Model
            │                       │
            ▼                       ▼
        FastAPI ◄──────── Prediction Service
            │
            ├────────► Redis Cache
            │
            └────────► SQLAlchemy Repository ──► PostgreSQL

## Repository structure

    stocksense-ai/
    ├── app/
    │   ├── api/
    │   │   ├── routes.py
    │   │   └── schemas.py
    │   ├── core/config.py
    │   ├── db/
    │   │   ├── database.py
    │   │   ├── models.py
    │   │   ├── repository.py
    │   │   └── init_db.py
    │   ├── services/
    │   │   ├── cache.py
    │   │   ├── features.py
    │   │   ├── predictor.py
    │   │   └── training.py
    │   └── main.py
    ├── data/sample_prices.csv
    ├── models/
    ├── tests/
    ├── .github/workflows/ci.yml
    ├── .env.example
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    └── README.md

## Setup

    git clone https://github.com/AloneRider-pixel/stocksense-ai.git
    cd stocksense-ai

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

    cp .env.example .env
    python -m app.db.init_db
    python -m app.services.training
    uvicorn app.main:app --reload

Open the interactive API documentation at http://127.0.0.1:8000/docs.

## Database

PostgreSQL stores prediction history in the prediction_records table.

Initialize the schema with:

    python -m app.db.init_db

The API writes successful uncached predictions to PostgreSQL and exposes them through:

    GET /api/v1/predictions
    GET /api/v1/predictions?symbol=DEMO&limit=10

## Train and evaluate

    python -m app.services.training
    cat models/metrics.json

Training uses the first 80% of observations chronologically and evaluates on the final 20%.

The generated model artifact is intentionally ignored by Git. This keeps the repository source-controlled and reproducible rather than committing binary model files.

The metrics endpoint is available at:

    GET /api/v1/metrics

## Authentication and rate limiting

Protected endpoints require the `X-API-Key` header. Set `API_KEY` in `.env` before starting the API.

The API uses a Redis-backed fixed-window rate limiter. Defaults are **60 requests per 60 seconds per API key** and can be configured with `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`.

Example:

    curl -H "X-API-Key: change-this-development-key" http://127.0.0.1:8000/api/v1/metrics

Rate-limit responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After` headers. When Redis is unavailable, the limiter fails open so an infrastructure dependency does not take the API offline.

## Structured errors

API errors use a consistent JSON envelope with an error code and request ID.

    {
      "error": {
        "code": "UNAUTHORIZED",
        "message": "A valid X-API-Key header is required.",
        "request_id": "..."
      }
    }

Validation failures return `VALIDATION_ERROR`; invalid prediction input returns `PREDICTION_INPUT_ERROR`; unavailable prediction history returns `DATABASE_UNAVAILABLE`.

## Prediction API

    POST /api/v1/predict
    Content-Type: application/json

Example payload:

    {
      "symbol": "DEMO",
      "history": [
        {"close": 100.10, "volume": 1000000},
        {"close": 100.55, "volume": 1010000},
        {"close": 101.20, "volume": 1025000},
        {"close": 101.85, "volume": 1030000},
        {"close": 102.30, "volume": 1040000},
        {"close": 102.75, "volume": 1055000},
        {"close": 103.10, "volume": 1060000},
        {"close": 103.60, "volume": 1070000},
        {"close": 104.05, "volume": 1080000},
        {"close": 104.50, "volume": 1090000}
      ]
    }

The response includes the predicted next-period close, expected percentage change, model version, cache state, and whether the result was persisted.

## Testing

    pytest -q

## Docker

    docker compose up --build

PostgreSQL and Redis are provisioned as separate services. The API can start even when either dependency is temporarily unavailable; prediction persistence becomes active once PostgreSQL is reachable.

## Model limitations

This repository currently uses deterministic sample data to demonstrate the engineering pipeline. It is **not investment advice** and the model should not be presented as a validated trading strategy.

For a production evaluation, add real historical market data, walk-forward validation, benchmark comparisons, transaction-cost assumptions, drift monitoring, and model/version tracking.

## License

MIT
