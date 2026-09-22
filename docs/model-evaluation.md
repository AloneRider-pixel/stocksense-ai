# StockSense AI Model Evaluation

## Objective

Measure out-of-sample next-period close prediction quality without leaking future observations into training.

## Feature construction

Features are calculated only from observations available at the prediction timestamp:

- 1-day return
- 5-day return
- close / 5-day moving average
- close / 10-day moving average
- 5-day return volatility
- 5-day volume change

The target is the next observed close.

## Walk-forward protocol

The evaluation uses expanding-window TimeSeriesSplit folds. Each fold trains on an earlier contiguous portion of the series and evaluates on a later contiguous portion. Random shuffling is intentionally avoided for time-series data.

For each test observation, the system records:

- fold
- prediction date
- current close
- predicted close
- actual close
- last-close baseline
- directional correctness

## Metrics

The generated metrics include:

- MAE
- RMSE
- MAPE
- directional accuracy
- baseline MAE
- improvement versus the last-close baseline

The baseline comparison is descriptive. A positive or negative improvement is retained as measured; it is not treated as evidence of future trading performance.

## Reproducibility

Run:

    python -m app.services.training --symbol AAPL --provider twelve_data --limit 1000

Outputs:

    models/metrics.json
    models/registry.json
    models/walk_forward_predictions.csv
    models/stocksense_rf.joblib

The source, model version, feature set, row count, evaluation metrics, and training timestamp are recorded in the registry.

## Prediction lifecycle evaluation

Online predictions are stored with their prediction date. When the next market bar is ingested, reconciliation attaches the first later trading bar and computes the realized error and directional result.

This creates a second, production-style measurement path in addition to offline walk-forward evaluation.
