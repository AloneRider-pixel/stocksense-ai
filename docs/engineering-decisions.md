# Engineering Decisions

## PostgreSQL as the system of record

Users, market bars, and prediction records are durable application state, so PostgreSQL is the source of truth. This keeps reconciliation and historical evaluation queryable and transactional.

## Redis for cache and job coordination

Redis is used for low-latency cache/rate-limit state and asynchronous job coordination. Cached data is treated as disposable so recovery does not depend on Redis durability.

## Provider adapter boundary

External market data is normalized behind a provider interface. This keeps ingestion, storage, and evaluation independent from a specific vendor and allows CSV-backed local testing.

## Walk-forward validation

Time-series validation uses expanding historical windows rather than random shuffling. This makes evaluation ordering explicit and avoids training on observations that occur after the test period.

## Prediction reconciliation

Predictions are persisted before their future outcomes are known. When a later market bar becomes available, the first subsequent trading observation is attached to the prediction so realized error can be measured without rewriting historical predictions.

## Operational startup

The containerized API applies database migrations before serving traffic, while liveness and readiness remain separate. This makes dependency state visible to orchestration and avoids treating a running process as proof that the application is ready.
