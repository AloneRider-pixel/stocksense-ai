# StockSense AI

AI-assisted stock analysis and prediction platform built with **Python, FastAPI, PostgreSQL, Redis, and scikit-learn**.

> This repository is structured as an engineering portfolio project. Performance and reliability numbers are documented only when backed by reproducible measurements.

## What it does

- Ingests historical OHLCV market data.
- Builds technical features such as returns, moving averages, and volatility.
- Trains a baseline regression model for next-period price estimation.
- Exposes prediction and health APIs through FastAPI.
- Persists prediction records and model metadata.
- Uses Redis caching for repeated prediction requests.
- Includes automated tests and GitHub Actions CI.
- Provides Docker-based local development.

## Architecture

```text
Client
  │
  ▼
FastAPI
  ├── Prediction Service ──► Feature Engineering ──► ML Model
  ├── Prediction Repository ───────────────────────► PostgreSQL
  └── Cache Layer ─────────────────────────────────► Redis
```

## Repository structure

```text
stocksense-ai/
├── app/
│   ├── api/
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   └── database.py
│   ├── services/
│   │   ├── cache.py
│   │   ├── features.py
│   │   └── predictor.py
│   └── main.py
├── data/
│   └── sample_prices.csv
├── models/
├── tests/
│   ├── test_features.py
│   └── test_health.py
├── .github/
│   └── workflows/
│       └── ci.yml
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Quick start

```bash
git clone https://github.com/AloneRider-pixel/stocksense-ai.git
cd stocksense-ai

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
uvicorn app.main:app --reload
```

API documentation is available at `/docs`.

## Example endpoint

```http
GET /api/v1/health
```

Prediction requests use:

```http
POST /api/v1/predict
Content-Type: application/json

{
  "symbol": "DEMO",
  "close": 125.40,
  "volume": 1500000
}
```

## Testing

```bash
pytest -q
```

## Docker

```bash
docker compose up --build
```

## Engineering notes

The initial implementation intentionally uses a transparent baseline model and small local sample data. Production-grade accuracy claims require a time-series backtest, leakage checks, a fixed evaluation protocol, and enough historical observations.

## License

MIT
