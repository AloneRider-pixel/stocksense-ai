from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from app.services.features import FEATURE_COLUMNS, build_training_frame


@dataclass(frozen=True)
class WalkForwardResult:
    metrics: dict[str, float | int | str]
    predictions: pd.DataFrame


def _mape(actual: pd.Series, predicted: np.ndarray) -> float:
    denominator = actual.replace(0, np.nan)
    return float(
        (np.abs((actual - predicted) / denominator)).dropna().mean() * 100
    )


def walk_forward_evaluate(
    data: pd.DataFrame,
    *,
    n_splits: int = 5,
    random_state: int = 42,
) -> WalkForwardResult:
    frame = build_training_frame(data)

    minimum_rows = max(60, n_splits * 10 + 20)
    if len(frame) < minimum_rows:
        raise ValueError(
            f"Need at least {minimum_rows} usable observations for walk-forward evaluation"
        )

    test_size = max(5, len(frame) // (n_splits + 1))
    splitter = TimeSeriesSplit(
        n_splits=n_splits,
        test_size=test_size,
    )

    rows: list[dict[str, object]] = []

    for fold, (train_idx, test_idx) in enumerate(splitter.split(frame), start=1):
        train = frame.iloc[train_idx]
        test = frame.iloc[test_idx]

        model = RandomForestRegressor(
            n_estimators=200,
            random_state=random_state,
            min_samples_leaf=2,
            n_jobs=-1,
        )
        model.fit(train[FEATURE_COLUMNS], train["target"])
        predictions = model.predict(test[FEATURE_COLUMNS])

        for row_index, (_, row) in enumerate(test.iterrows()):
            previous_close = float(row["close"])
            actual_close = float(row["target"])
            predicted_close = float(predictions[row_index])
            actual_move = np.sign(actual_close - previous_close)
            predicted_move = np.sign(predicted_close - previous_close)

            rows.append(
                {
                    "fold": fold,
                    "prediction_date": str(row["date"]) if "date" in row else row_index,
                    "current_close": previous_close,
                    "predicted_close": predicted_close,
                    "actual_close": actual_close,
                    "baseline_close": previous_close,
                    "direction_correct": int(actual_move == predicted_move),
                }
            )

    predictions_df = pd.DataFrame(rows)

    actual = predictions_df["actual_close"]
    model_pred = predictions_df["predicted_close"].to_numpy()
    baseline_pred = predictions_df["baseline_close"].to_numpy()

    model_mae = float(mean_absolute_error(actual, model_pred))
    baseline_mae = float(mean_absolute_error(actual, baseline_pred))
    model_rmse = float(mean_squared_error(actual, model_pred) ** 0.5)

    metrics: dict[str, float | int | str] = {
        "evaluation": "walk_forward",
        "folds": n_splits,
        "test_rows": int(len(predictions_df)),
        "mae": round(model_mae, 6),
        "rmse": round(model_rmse, 6),
        "mape_pct": round(_mape(actual, model_pred), 6),
        "directional_accuracy_pct": round(
            float(predictions_df["direction_correct"].mean() * 100),
            6,
        ),
        "baseline_mae": round(baseline_mae, 6),
        "improvement_vs_last_close_pct": round(
            ((baseline_mae - model_mae) / baseline_mae * 100)
            if baseline_mae
            else 0.0,
            6,
        ),
    }

    return WalkForwardResult(metrics=metrics, predictions=predictions_df)


def write_walk_forward_artifacts(
    result: WalkForwardResult,
    *,
    metrics_path: str = "models/metrics.json",
    predictions_path: str = "models/walk_forward_predictions.csv",
) -> None:
    Path(metrics_path).parent.mkdir(parents=True, exist_ok=True)
    Path(predictions_path).parent.mkdir(parents=True, exist_ok=True)

    import json

    Path(metrics_path).write_text(
        json.dumps(result.metrics, indent=2),
        encoding="utf-8",
    )
    result.predictions.to_csv(predictions_path, index=False)
