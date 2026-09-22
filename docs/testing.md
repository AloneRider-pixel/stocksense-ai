# Testing Strategy

StockSense uses layered verification so core behavior can be validated without requiring live market-data credentials.

## Unit tests

Unit tests cover isolated behavior such as:

- market-data normalization and provider failures
- feature generation and validation
- walk-forward evaluation
- authentication and password handling
- prediction reconciliation
- repository operations

## Integration behavior

Database-backed tests exercise persistence boundaries against a configured test database where required. The CI pipeline runs the backend test suite with `pytest`.

## Frontend verification

The frontend is verified by the production build in GitHub Actions. This catches module, bundler, and type/build integration failures.

## Live-data evaluation

The repository keeps live-provider evaluation separate from normal CI because it requires an external API credential and introduces third-party availability/rate-limit variability.

Run it through:

`python -m app.services.training --symbol AAPL --provider twelve_data --limit 1000`

The on-demand workflow in `.github/workflows/model-evaluation.yml` records the resulting metrics and row-level predictions as workflow artifacts.

## What CI does not prove

Passing CI does not establish investment performance, production uptime, or model superiority. Those claims require separate, reproducible measurements with documented datasets, environments, observation windows, and baselines.
