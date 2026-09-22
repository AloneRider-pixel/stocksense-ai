# Deployment & Metrics

## Current deployment status

StockSense AI is containerized and deployment-ready, but no public production URL is configured in this repository yet.

**Live URL:** Pending AWS deployment.

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
3. Run alembic upgrade head.
4. Start API and worker as separate services.
5. Run an initial historical ingestion.
6. Run live-data training and review the walk-forward metrics.
7. Promote the reviewed model version.
8. Configure uptime, latency, worker, and data-freshness alerts.
9. Record deployment and rollback identifiers.

## Local verification

    docker compose up --build
    curl http://localhost:8000/health/live
    curl http://localhost:8000/health/ready
    curl http://localhost:8000/docs
