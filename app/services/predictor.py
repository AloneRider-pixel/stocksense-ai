from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import joblib
import numpy as np

from app.services.features import build_prediction_features


MODEL_PATH = Path("models/stocksense_rf.joblib")


class Predictor:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path
        self.model = self._load_model()

    def _load_model(self):
        if not self.model_path.exists():
            from app.services.training import train_model
            train_model(model_path=str(self.model_path))
        return joblib.load(self.model_path)

    def predict(self, symbol: str, history: list[dict[str, float]]) -> dict[str, object]:
        features = np.array([build_prediction_features(history)])
        predicted_close = float(self.model.predict(features)[0])
        current_close = float(history[-1]["close"])
        return {
            "symbol": symbol,
            "predicted_close": round(predicted_close, 4),
            "expected_change_pct": round(
                ((predicted_close - current_close) / current_close) * 100,
                4,
            ),
            "model": "random-forest-v0.2",
            "cached": False,
        }

    @staticmethod
    def cache_key(symbol: str, history: list[dict[str, float]]) -> str:
        raw = f"{symbol}:{history[-10:]}".encode()
        return "prediction:" + sha256(raw).hexdigest()
