# Deployment & Metrics

## Current deployment status

StockSense AI is containerized and deployment-ready for evaluation, but no public production URL is configured in this repository yet.

**Live URL:** Pending AWS deployment.

## Local Docker Compose versus production

The repository's `docker-compose.yml` is for local development only. It uses intentionally weak sample credentials, enables development mode by default, and binds published ports to `127.0.0.1`. Do not expose this development stack to the internet or treat its sample settings as production-ready.

Production API and worker services should run as separate services with managed PostgreSQL and Redis. Supply configuration through the deployment platform or a secret manager; do not copy the sample credentials from `.env.example`.

At minimum, explicitly configure the following for both API and worker:

- `ENVIRONMENT=production`
- `JWT_SECRET`: random secret, at least 32 characters, held in a secret manager
- `DATABASE_URL`: PostgreSQL URL with explicit non-local host, database, user, and strong password (URL-encode reserved characters)
- `REDIS_URL`: TLS-enabled `rediss://` URL with a non-local production endpoint
- `ALLOWED_HOSTS`: comma-separated exact hostnames; wildcards and local service names are rejected
- `CORS_ORIGINS`: comma-separated HTTPS origins; localhost, HTTP origins, paths, and wildcards are rejected
- `TWELVE_DATA_API_KEY`: secret-manager value if using Twelve Data

Application startup fails closed when production JWT, database, Redis, host, or CORS settings contain development defaults or invalid values. Configure the same required settings for the background worker because it loads the same settings model.

## Intended runtime

- React frontend behind a CDN / static web host.
- FastAPI API as a stateless service.
- PostgreSQL as the system of record.
- Redis for cache, rate limiting, and job transport.
- Separate worker process for ingestion and prediction reconciliation.
- Secret manager for JWT_SECRET and TWELVE_DATA_API_KEY.

## Health and metrics endpoints

Liveness:

    GET /health/live

Readiness:

    GET /health/ready

Prometheus-compatible metrics:

    GET /internal/metrics

The request middleware records request counts and latency by HTTP method, route path, and response status.

## Uptime measurement

Do not document the existing 99.2% figure as a production uptime claim until it is backed by an externally measured time window.

For an auditable uptime calculation, record:

    uptime_pct = (scheduled_observation_count - failed_observation_count) / scheduled_observation_count * 100

Every measurement should include:

- measurement start/end timestamps
- probe interval
- health endpoint used
- deployment/version identifier
- number of successful probes
- number of failed probes
- incident/outage windows

A public dashboard or durable monitoring system should be used for a production claim.

## ML metrics

The training pipeline produces:

- MAE
- RMSE
- MAPE
- directional accuracy
- last-close baseline MAE
- improvement versus baseline

The generated models/metrics.json should only be committed when it was produced from a documented real-data run. The source provider, symbol, row count, training timestamp, and model version should be preserved in models/registry.json.

## Production runbook

1. Set MARKET_DATA_PROVIDER=twelve_data.
2. Store TWELVE_DATA_API_KEY in a secret manager.
3. Configure and validate production environment variables for API and worker.
4. Run alembic upgrade head.
5. Start API and worker as separate services.
6. Run an initial historical ingestion.
7. Run live-data training and review the walk-forward metrics.
8. Promote the reviewed model version.
9. Configure uptime, latency, worker, and data-freshness alerts.
10. Record deployment and rollback identifiers.

## Local verification

    docker compose up --build
    curl http://localhost:8000/health/live
    curl http://localhost:8000/health/ready
    curl http://localhost:8000/docs

## Demo deployment (sample data)

A public demo can run without PostgreSQL, Redis, or a market-data key:

- `DEMO_MODE=true` (ignored in production), `ENVIRONMENT=development`
- `DATABASE_URL=sqlite:////data/stocksense.db`
- `MARKET_DATA_PROVIDER=csv` (uses the checked-in `data/sample_prices.csv`)
- `CORS_ORIGINS=<frontend origin>`, `JWT_SECRET=<random 32+ chars>`

On startup the app seeds the DEMO symbol from the sample CSV, creates the
demo account `demo@stocksense.app` / `Demo1234!`, and trains the sample model
if no artifact exists. The frontend shows a sample-data banner when built
with `VITE_DEMO=true`. Demo predictions are illustrative, not investment
advice.
