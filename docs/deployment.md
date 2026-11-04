# Deployment & Metrics

## Current deployment status

The live demo runs on Render, connected to this repository's `main` branch
with auto-deploy on commit - merging to `main` redeploys both services:

- **API**: Docker web service built from the repo `Dockerfile`. At container
  start it runs `python -m app.db.migrate` and only then starts uvicorn; if
  migration fails, the container exits and the previous deploy keeps serving.
  Free instance, so it spins down when idle (first request after idle is
  slow). Migrations 0004-0006 (paper wallet, price alerts) apply on the
  first deploy that carries them.

  `app.db.migrate` also handles alembic adoption: the demo database predates
  alembic (its tables came from the old `create_all` startup, with no
  `alembic_version` row). The entrypoint compares an unversioned database's
  structure against `app/db/legacy_schema_spec.json` (generated from the
  last pre-migration deploy's models) and only then stamps the pre-migration
  head `0003_scanner_bars` and upgrades. A drifted, partial, or unknown
  schema fails closed with a printed diff - no stamp, no migration, no data
  change - and needs manual review. Empty databases and already-versioned
  databases upgrade normally. Concurrent container starts are serialized
  with a Postgres advisory lock.
- **Frontend**: static site, build `cd frontend && npm install && npm run
  build`, publish `frontend/dist`, served at
  https://stocksense-ai-demo.onrender.com.
- **Database**: external managed Postgres, supplied to the API service as
  the `DATABASE_URL` env var. Bare `postgres://` / `postgresql://` provider
  URLs are normalized onto the pinned psycopg driver at settings load.

Rollback: redeploy the previous deploy from the hosting dashboard. Schema
changes are additive-only (new tables, nullable columns), so the previous
code keeps working against a migrated database; `alembic downgrade` exists
if a reversal is ever required.

Migration concurrency: `app.db.migrate` holds a Postgres advisory lock
around adoption and upgrade, so multiple instances starting at once are
serialized.

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
4. Run python -m app.db.migrate (the demo API container does this automatically at start).
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
