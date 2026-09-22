# StockSense AI Architecture

StockSense AI is structured as a market-intelligence product with explicit boundaries between the web client, API, domain services, persistence, asynchronous jobs, and ML workloads.

## Runtime

    Browser
      │
      ▼
    React Web App
      │ HTTPS / JSON
      ▼
    FastAPI
      ├── Auth & authorization
      ├── Prediction service ──► Redis
      │                      └─► PostgreSQL
      ├── Market-data service
      └── Model metrics
              │
              ▼
          Worker Queue
              │
              ▼
       Background jobs

## Backend boundaries

- `app/api`: HTTP contracts and routing.
- `app/auth`: identity, password hashing, JWT issuance, and user lookup.
- `app/services`: business logic and ML orchestration.
- `app/db`: SQLAlchemy models, sessions, and repository access.
- `app/market_data`: provider abstraction and ingestion boundary.
- `app/workers`: asynchronous jobs.
- `app/http`: request context and response hardening.
- `app/observability.py`: request metrics.

## Data ownership

PostgreSQL is the system of record for users and prediction records. Redis is a performance and coordination layer; cached state can be regenerated.

## ML boundary

Training produces a model artifact and machine-readable evaluation metrics. The API consumes the artifact through the predictor service rather than coupling model internals to HTTP routes.
