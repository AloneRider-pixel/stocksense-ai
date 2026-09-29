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



def test_training_frame_does_not_cross_contaminate_symbols() -> None:
    rows = []
    for symbol, base in (("AAA", 100.0), ("BBB", 1000.0)):
        for index in range(15):
            rows.append(
                {
                    "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=index),
                    "symbol": symbol,
                    "close": base + index,
                    "volume": 1_000 + index,
                }
            )

    frame = build_training_frame(pd.DataFrame(rows))

    bbb = frame.loc[frame["symbol"] == "BBB"].sort_values("date").reset_index(drop=True)

    assert len(bbb) == 5
    assert bbb.loc[0, "return_1d"] == pytest.approx(1 / 1008)
    assert bbb.loc[0, "return_5d"] == pytest.approx(5 / 1004)
    assert bbb.loc[0, "target"] == pytest.approx(1010.0)
