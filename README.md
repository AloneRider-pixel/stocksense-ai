# StockSense AI

AI-assisted stock analysis and next-period price prediction platform built with **Python, FastAPI, PostgreSQL, Redis, and scikit-learn**.

> Portfolio note: measured performance claims are documented only when they can be reproduced from the repository's evaluation workflow.

## Current capabilities

- Historical OHLCV data pipeline using Pandas.
- Technical feature engineering: daily return, 5-day return, moving-average ratios, volatility, and volume change.
- Chronological 80/20 train-test evaluation to avoid random time-series shuffling.
- Random Forest regression for next-period close prediction.
- FastAPI prediction and health endpoints.
- Redis-ready caching layer.
- PostgreSQL-ready database layer.
- Automated tests with PyTest.
- GitHub Actions CI.
- Docker and Docker Compose for local infrastructure.

## Architecture

```text
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
        └────────► PostgreSQL
```

## Repository structure

```text
stocksense-ai/
├── app/
│   ├── api/
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── core/config.py
│   ├── db/database.py
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
```

## Setup

```bash
git clone https://github.com/AloneRider-pixel/stocksense-ai.git
cd stocksense-ai

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python -m app.services.training
uvicorn app.main:app --reload
```

Open the interactive API documentation at `http://127.0.0.1:8000/docs`.

## Train and evaluate

```bash
python -m app.services.training
cat models/metrics.json
```

Training uses the first 80% of observations chronologically and evaluates on the final 20%.

The generated model artifact is intentionally ignored by Git. This keeps the repository source-controlled and reproducible rather than committing binary model files.

## Prediction API

```http
POST /api/v1/predict
Content-Type: application/json
```

Example payload:

```json
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
```

Response includes the predicted next-period close and estimated percentage change from the latest close.

## Testing

```bash
pytest -q
```

## Docker

```bash
docker compose up --build
```

## Model limitations

This repository currently uses deterministic sample data to demonstrate the engineering pipeline. It is **not investment advice** and the model should not be presented as a validated trading strategy.

For a production evaluation, add real historical market data, walk-forward validation, benchmark comparisons, transaction-cost assumptions, drift monitoring, and model/version tracking.

## License

MIT
