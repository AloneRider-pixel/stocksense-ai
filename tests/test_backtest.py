from __future__ import annotations

import pandas as pd
import pytest

from app.services.backtest import _max_drawdown_pct, run_backtest


def _bars(rows: int = 160) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=rows, freq="B")
    close = [100.0]
    for i in range(1, rows):
        drift = 0.4 if i % 7 else -1.2
        close.append(close[-1] + drift)
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": close,
            "volume": [1_000_000 + i * 1000 for i in range(rows)],
        }
    )


def test_max_drawdown_pct_tracks_peak_to_trough() -> None:
    assert _max_drawdown_pct([1.0, 1.2, 0.9, 1.1]) == pytest.approx(-25.0)
    assert _max_drawdown_pct([1.0, 1.1, 1.2]) == 0.0


def test_run_backtest_returns_curve_and_metrics() -> None:
    result = run_backtest(_bars())

    assert result.metrics["periods"] == len(result.equity_curve)
    assert result.metrics["periods"] > 0
    assert set(result.equity_curve[0]) == {"date", "strategy", "buy_hold"}
    assert result.metrics["strategy_max_drawdown_pct"] <= 0
    assert result.metrics["buy_hold_max_drawdown_pct"] <= 0
    assert 0 <= result.metrics["directional_hit_rate_pct"] <= 100


def test_run_backtest_rejects_tiny_inputs() -> None:
    with pytest.raises(ValueError):
        run_backtest(_bars(20))
