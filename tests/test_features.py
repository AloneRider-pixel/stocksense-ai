import pandas as pd
import pytest

from app.services.features import build_prediction_features, build_training_frame


def sample_frame(rows: int = 24) -> pd.DataFrame:
    return pd.DataFrame({
        "close": [100 + i * 0.5 for i in range(rows)],
        "volume": [1_000_000 + i * 5_000 for i in range(rows)],
    })


def test_training_frame_contains_features() -> None:
    frame = build_training_frame(sample_frame())
    assert len(frame) > 0
    assert {"return_1d", "sma5_ratio", "sma10_ratio", "target"} <= set(frame.columns)


def test_prediction_features_need_history() -> None:
    with pytest.raises(ValueError):
        build_prediction_features(
            [{"close": 100.0, "volume": 1_000_000.0}] * 9
        )


def test_prediction_features_have_expected_shape() -> None:
    history = [
        {"close": 100 + i * 0.5, "volume": 1_000_000 + i * 5_000}
        for i in range(20)
    ]
    features = build_prediction_features(history)
    assert len(features) == 6
    assert all(isinstance(value, float) for value in features)
