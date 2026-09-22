from __future__ import annotations

from hashlib import sha256

import numpy as np
from sklearn.linear_model import Ridge

from app.services.features import build_features


class Predictor:
    """Small transparent baseline used for the initial API implementation."""

    def __init__(self) -> None:
        self.model = Ridge(alpha=1.0)
        self._fit_baseline()

    def _fit_baseline(self) -> None:
        closes = np.linspace(80.0, 120.0, 64)
        volumes = np.linspace(900_000, 1_600_000, 64)

        x = np.array([build_features(float(c), float(v)) for c, v in zip(closes, volumes)])
        y = closes * 1.002

        self.model.fit(x, y)

    def predict(self, symbol: str, close: float, volume: float) -> dict[str, object]:
        features = np.array([build_features(close, volume)])
        predicted = float(self.model.predict(features)[0])

        return {
            "symbol": symbol,
            "predicted_close": round(predicted, 4),
            "model": "ridge-baseline-v0.1",
            "cached": False,
        }

    @staticmethod
    def cache_key(symbol: str, close: float, volume: float) -> str:
        raw = f"{symbol}:{close:.8f}:{volume:.4f}".encode()
        return "prediction:" + sha256(raw).hexdigest()
