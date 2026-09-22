from __future__ import annotations

import math


def build_features(close: float, volume: float) -> list[float]:
    if close <= 0 or volume <= 0:
        raise ValueError("close and volume must be positive")

    log_close = math.log(close)
    log_volume = math.log(volume)

    return [
        close,
        volume,
        log_close,
        log_volume,
        close / (1.0 + abs(log_close)),
        volume / (1.0 + abs(log_volume)),
    ]
