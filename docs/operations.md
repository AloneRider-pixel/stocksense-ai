# StockSense AI Operations Guide

## Real market data

Set MARKET_DATA_PROVIDER=twelve_data and provide TWELVE_DATA_API_KEY.

Manual ingestion:

    python -m app.market_data.cli --symbol AAPL --limit 500

Training against live data:

    python -m app.services.training --symbol AAPL --provider twelve_data --limit 1000

The provider is retried with bounded exponential backoff. Invalid provider responses fail the ingestion operation rather than entering the database silently.

## Prediction evaluation

Predictions are recorded with the market date used for the forecast. Once a later market bar is ingested, the reconciliation process attaches the first later bar as the realized outcome and calculates absolute error, percentage error, and directional correctness.

Reconciliation runs as part of market-data ingestion and therefore also runs from the scheduled worker.

## Scheduled worker

    python -m app.workers.worker

The worker refreshes the configured symbol universe on the configured daily schedule. ARQ provides retries and unique cron scheduling.

## Training artifacts

    models/stocksense_rf.joblib
    models/metrics.json
    models/registry.json
    models/walk_forward_predictions.csv

These files are generated locally and ignored by Git.

## Production

- Use Alembic for schema migrations.
- Set a strong JWT_SECRET.
- Configure CORS_ORIGINS and ALLOWED_HOSTS explicitly.
- Store provider credentials in a secret manager.
- Run the worker separately from the API process.
- Scrape /internal/metrics with a metrics system.
- Monitor /health/live and /health/ready.

## Data-provider note

The default live provider is Twelve Data. Its documented /time_series endpoint supplies daily OHLCV data and supports up to 5,000 data points per request. Provider terms and plan limits apply.