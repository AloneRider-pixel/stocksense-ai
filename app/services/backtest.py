"""Walk-forward backtest: model strategy vs buy-and-hold on stored daily bars.

The strategy is deliberately simple and fully disclosed: walk-forward
out-of-sample predictions decide a long-or-flat position for the next bar.
No transaction costs, no shorting, no leverage. Results are illustrative
evaluation evidence, not a claim about live trading performance.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.services.walk_forward import walk_forward_evaluate


@dataclass(frozen=True)
class BacktestResult:
    metrics: dict[str, float | int | str]
    equity_curve: list[dict[str, object]]


def _max_drawdown_pct(equity: list[float]) -> float:
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak:
            worst = min(worst, value / peak - 1.0)
    return round(worst * 100, 4)


def run_backtest(
    bars: pd.DataFrame,
    *,
    n_splits: int = 5,
    random_state: int = 42,
) -> BacktestResult:
    """Run the disclosed long/flat strategy over walk-forward predictions.

    ``bars`` needs date/close/volume columns for a single symbol.
    """
    frame = bars if "symbol" in bars.columns else bars.assign(symbol="BACKTEST")
    result = walk_forward_evaluate(
        frame, n_splits=n_splits, random_state=random_state
    )
    predictions = result.predictions
    if predictions.empty:
        raise ValueError("Walk-forward evaluation produced no predictions")

    strategy_equity = [1.0]
    buy_hold_equity = [1.0]
    curve: list[dict[str, object]] = []
    hits = 0

    for row in predictions.itertuples():
        current = float(row.current_close)
        actual = float(row.actual_close)
        predicted = float(row.predicted_close)
        if not current:
            continue
        actual_return = actual / current - 1.0
        position = 1.0 if predicted > current else 0.0
        strategy_equity.append(strategy_equity[-1] * (1.0 + position * actual_return))
        buy_hold_equity.append(buy_hold_equity[-1] * (1.0 + actual_return))
        if (predicted > current) == (actual > current):
            hits += 1
        curve.append(
            {
                "date": str(row.prediction_date),
                "strategy": round((strategy_equity[-1] - 1.0) * 100, 4),
                "buy_hold": round((buy_hold_equity[-1] - 1.0) * 100, 4),
            }
        )

    periods = len(curve)
    if not periods:
        raise ValueError("No usable backtest observations")

    metrics: dict[str, float | int | str] = {
        "evaluation": "walk_forward_long_flat",
        "periods": periods,
        "strategy_return_pct": round((strategy_equity[-1] - 1.0) * 100, 4),
        "buy_hold_return_pct": round((buy_hold_equity[-1] - 1.0) * 100, 4),
        "strategy_max_drawdown_pct": _max_drawdown_pct(strategy_equity),
        "buy_hold_max_drawdown_pct": _max_drawdown_pct(buy_hold_equity),
        "directional_hit_rate_pct": round(hits / periods * 100, 4),
    }
    return BacktestResult(metrics=metrics, equity_curve=curve)
