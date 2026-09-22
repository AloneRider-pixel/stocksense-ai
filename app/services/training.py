from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from app.services.features import FEATURE_COLUMNS, build_training_frame


def train_model(
    data_path: str = "data/sample_prices.csv",
    model_path: str = "models/stocksense_rf.joblib",
    metrics_path: str = "models/metrics.json",
    registry_path: str = "models/registry.json",
    model_version: str = "random-forest-v0.2",
) -> dict[str, float | int | str]:
    df = pd.read_csv(data_path)
    frame = build_training_frame(df)

    if len(frame) < 40:
        raise ValueError("At least 40 usable observations are required for training")

    split = int(len(frame) * 0.8)
    train = frame.iloc[:split]
    test = frame.iloc[split:]

    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        min_samples_leaf=2,
        n_jobs=-1,
    )
    model.fit(train[FEATURE_COLUMNS], train["target"])

    predictions = model.predict(test[FEATURE_COLUMNS])
    rmse = mean_squared_error(test["target"], predictions) ** 0.5

    metrics: dict[str, float | int | str] = {
        "model_version": model_version,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "mae": round(float(mean_absolute_error(test["target"], predictions)), 6),
        "rmse": round(float(rmse), 6),
        "r2": round(float(r2_score(test["target"], predictions)), 6),
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    metadata = {
        "version": model_version,
        "algorithm": "RandomForestRegressor",
        "features": FEATURE_COLUMNS,
        "dataset": data_path,
        "trained_at": metrics["trained_at"],
        "status": "candidate",
        "metrics": {
            key: metrics[key]
            for key in ("mae", "rmse", "r2", "train_rows", "test_rows")
        },
    }

    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    Path(metrics_path).parent.mkdir(parents=True, exist_ok=True)
    Path(registry_path).parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, model_path)
    Path(metrics_path).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    Path(registry_path).write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return metrics


if __name__ == "__main__":
    result = train_model()
    print(json.dumps(result, indent=2))
