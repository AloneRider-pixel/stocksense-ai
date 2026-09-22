from __future__ import annotations

import pandas as pd


FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "sma5_ratio",
    "sma10_ratio",
    "volatility5",
    "volume_change5",
]


def build_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    required = {"close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    frame = df.copy()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")

    frame["return_1d"] = frame["close"].pct_change()
    frame["return_5d"] = frame["close"].pct_change(5)
    frame["sma5_ratio"] = frame["close"] / frame["close"].rolling(5).mean()
    frame["sma10_ratio"] = frame["close"] / frame["close"].rolling(10).mean()
    frame["volatility5"] = frame["return_1d"].rolling(5).std()
    frame["volume_change5"] = frame["volume"].pct_change(5)
    frame["target"] = frame["close"].shift(-1)

    frame = frame.dropna(subset=FEATURE_COLUMNS + ["target"]).reset_index(drop=True)
    return frame


def build_prediction_features(history: list[dict[str, float]]) -> list[float]:
    if len(history) < 10:
        raise ValueError("At least 10 historical bars are required")

    frame = pd.DataFrame(history)
    frame["close"] = pd.to_numeric(frame["close"], errors="raise")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="raise")

    if (frame["close"] <= 0).any() or (frame["volume"] <= 0).any():
        raise ValueError("close and volume must be positive")

    training_frame = build_training_frame(frame)
    if training_frame.empty:
        raise ValueError("Not enough valid history after feature construction")

    latest = training_frame.iloc[-1]
    return [float(latest[column]) for column in FEATURE_COLUMNS]
