# Verification & Evidence

## Model evaluation

The default CI evaluation uses the repository's checked-in sample dataset. It is a reproducibility fixture, not evidence of live-market trading performance.

| Evidence | Reproduction |
|---|---|
| Unit/integration tests | pytest -q |
| Static analysis | ruff check app tests |
| Sample-data walk-forward evaluation | python -m app.services.training --data-path data/sample_prices.csv --limit 1000 --model-version ci-sample-v1 |
| Live market-data evaluation | .github/workflows/model-evaluation.yml | Manual workflow with Twelve Data credentials |
| Static security analysis | CodeQL workflow |
| Supply-chain verification | OpenSSF Scorecard workflow |

## Measurement integrity

Any published ML metric must identify dataset/source, rows, feature set, model version, validation protocol, timestamp, and commit. A sample fixture result must not be presented as a live-market benchmark.