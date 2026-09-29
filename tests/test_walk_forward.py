import pandas as pd

from app.services.walk_forward import walk_forward_evaluate


def synthetic_market_data(rows: int = 140) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=rows, freq="D"),
            "symbol": ["TEST"] * rows,
            "open": [100 + i * 0.2 for i in range(rows)],
            "high": [100.5 + i * 0.2 for i in range(rows)],
            "low": [99.5 + i * 0.2 for i in range(rows)],
            "close": [100 + i * 0.2 for i in range(rows)],
            "volume": [1_000_000 + i * 1000 for i in range(rows)],
        }
    )


def test_walk_forward_produces_future_only_predictions() -> None:
    result = walk_forward_evaluate(synthetic_market_data())

    assert result.metrics["evaluation"] == "walk_forward"
    assert result.metrics["folds"] == 5
    assert result.metrics["test_rows"] > 0
    assert result.predictions["prediction_date"].is_monotonic_increasing
    assert {"predicted_close", "actual_close", "baseline_close", "train_end_date"} <= set(
        result.predictions.columns
    )
    assert (result.predictions["prediction_date"] > result.predictions["train_end_date"]).all()
    assert len(result.metrics["data_sha256"]) == 64
    assert result.metrics["source_rows"] == 140
