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

The target is the next-period return ratio (next close / close); metrics are computed in price space by converting predictions back with the current close, so they stay comparable to the last-close baseline.

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


## Live prediction tracking (public accuracy)

`GET /api/v1/public/accuracy` aggregates every prediction the API has served and later reconciled against the next realized close, anonymized and grouped per symbol. It reports evaluated count, MAE, MAPE, directional accuracy, and two naive baselines computed over the same scored predictions:

- last-close persistence (predicting no change), compared on MAE/MAPE; and
- an always-up directional guess, compared on hit rate.

This is a live track record, not a backtest: sample sizes are shown on purpose and start small. `GET /api/v1/public/predictions/latest` exposes the most recent stored prediction per symbol so the forecasts are inspectable before they are scored.

## Backtest view

`GET /api/v1/backtest/{symbol}` runs a fully disclosed long/flat strategy over walk-forward out-of-sample predictions on stored daily bars: long when the model predicts an up move, flat otherwise, no transaction costs, no shorting, no leverage. It returns the strategy and buy-and-hold equity curves, total returns, max drawdowns, and the out-of-sample directional hit rate. Results are illustrative evaluation evidence, not trading performance claims.
