# StockSense AI

Market intelligence platform for stock analysis, next-period prediction, and model-driven monitoring.

StockSense AI is designed as a product system rather than a single prediction script. The codebase separates the web client, authenticated API, market-data boundary, ML pipeline, persistence, asynchronous workers, caching, observability, and operational controls.

## Product

The platform provides:

- User accounts with JWT authentication
- Stock market-data access through a provider abstraction
- Technical feature engineering and time-series model evaluation
- Next-period price prediction
- Per-user prediction history
- Redis caching and rate limiting
- PostgreSQL persistence
- Model evaluation metrics
- Background job execution
- Prometheus-compatible runtime metrics
- Responsive React dashboard
- Dockerized local stack

## Architecture

    Browser
       │
       ▼
    React Web App
       │ HTTPS / JSON
       ▼
    FastAPI API
       ├── Authentication
       ├── Prediction Service ──────► Redis
       │                         └──► PostgreSQL
       ├── Market Data Service
       └── Model Metrics
                 │
                 ▼
             Redis Queue
                 │
                 ▼
          Background Worker

## Engineering stack

Backend: Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Redis

ML: Pandas, NumPy, scikit-learn, joblib

Frontend: React, Vite, CSS

Platform: Docker, Docker Compose, GitHub Actions, Alembic

Observability: Prometheus-compatible HTTP metrics, health probes, request IDs

## Repository structure

    stocksense-ai/
    ├── app/
    │   ├── api/
    │   ├── auth/
    │   ├── core/
    │   ├── db/
    │   ├── http/
    │   ├── market_data/
    │   ├── services/
    │   ├── workers/
    │   ├── observability.py
    │   └── main.py
    ├── frontend/
    ├── ml models and evaluation outputs under models/
    ├── tests/
    ├── alembic/
    ├── docs/
    ├── .github/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── pyproject.toml
    └── requirements.txt

## Local development

### Backend

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    alembic upgrade head
    python -m app.services.training
    uvicorn app.main:app --reload

API documentation is available at http://127.0.0.1:8000/docs.

### Frontend

    cd frontend
    npm install
    npm run dev

Set the API URL through `VITE_API_BASE_URL` when needed.

### Full stack

    docker compose up --build

The Compose stack includes the API, React web application, PostgreSQL, Redis, and worker.

## API surface

Public:

    POST /api/v1/auth/register
    POST /api/v1/auth/login
    GET  /api/v1/health
    GET  /health/live
    GET  /health/ready

Authenticated:

    GET  /api/v1/auth/me
    GET  /api/v1/stocks/{symbol}/history
    POST /api/v1/predict
    GET  /api/v1/predictions
    GET  /api/v1/metrics

Operational:

    GET /internal/metrics

## Machine learning

The initial model is a Random Forest regressor trained on engineered OHLCV-derived features. Training uses a chronological split rather than random shuffling to keep the evaluation protocol aligned with time-series data.

Training output is written as a model artifact plus machine-readable metrics. The model binary is ignored by Git so the repository stays source-oriented and reproducible.

Production evaluation should use real market data, walk-forward validation, baseline comparisons, drift monitoring, and explicit cost assumptions before any performance figure is treated as meaningful.

## Data layer

PostgreSQL is the system of record for users and prediction history. SQLAlchemy repositories provide the data-access boundary. Alembic is the production migration mechanism.

Redis is used for prediction caching, rate limiting, and the background-job transport.

The market-data layer exposes a provider interface so the product can move from the bundled local dataset to an external data provider without rewriting API/business logic.

## Security

- Passwords are hashed with scrypt.
- Access is controlled with signed JWT bearer tokens.
- Prediction history is scoped to the authenticated user.
- Request payloads are validated with Pydantic.
- Rate limiting is Redis-backed.
- HTTP responses include request IDs and baseline security headers.
- Secrets are provided through environment variables and excluded from Git.

See `docs/security.md` for the current security model.

## Quality

CI runs backend linting and tests plus a frontend production build.

    ruff check app tests
    pytest -q
    cd frontend && npm run build

Repository contribution conventions live under `.github/` and production-operational notes are in `docs/`.

## Operating principles

StockSense AI is built around reliability, explicit boundaries, reproducible evaluation, observable behavior, and maintainable interfaces.

The system is a market-analysis product and not a brokerage or order-execution system. Predictions are informational and should not be represented as investment advice.

## License

MIT
