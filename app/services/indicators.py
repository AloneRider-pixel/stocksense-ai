"""Technical indicators computed from stored daily bars.

Pure pandas/numpy, no lookahead: every value at index i uses only bars up to
and including i. Computed server-side so the numbers are unit-testable and
identical for every client.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    result = 100 - (100 / (1 + rs))
    # All-gain windows: RSI 100; flat windows (both zero): neutral 50.
    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    result = result.mask((avg_loss == 0) & (avg_gain == 0), 50.0)
    return result


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def bollinger(
    close: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = sma(close, window)
    std = close.rolling(window=window, min_periods=window).std(ddof=0)
    return mid + num_std * std, mid, mid - num_std * std


def compute_indicators(bars: list[dict]) -> dict[str, list]:
    """Compute the standard indicator set for a list of OHLCV bar dicts.

    Returns per-series lists aligned with the input dates; leading values that
    lack enough history are null.
    """
    frame = pd.DataFrame(bars)
    close = frame["close"].astype(float)

    macd_line, signal_line, histogram = macd(close)
    bb_upper, bb_mid, bb_lower = bollinger(close)

    def clean(series: pd.Series) -> list[float | None]:
        return [None if pd.isna(v) else round(float(v), 4) for v in series]

    return {
        "dates": [str(d)[:10] for d in frame["date"]],
        "close": clean(close),
        "sma20": clean(sma(close, 20)),
        "sma50": clean(sma(close, 50)),
        "ema12": clean(ema(close, 12)),
        "ema26": clean(ema(close, 26)),
        "rsi14": clean(rsi(close)),
        "macd": clean(macd_line),
        "macd_signal": clean(signal_line),
        "macd_hist": clean(histogram),
        "bb_upper": clean(bb_upper),
        "bb_mid": clean(bb_mid),
        "bb_lower": clean(bb_lower),
    }
