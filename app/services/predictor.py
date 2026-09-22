from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import joblib
import numpy as np

from app.core.config import settings
from app.services.features import build_prediction_features


MODEL_PATH = Path("models/stocksense_rf.joblib")
REGISTRY_PATH = Path("models/registry.json")


class Predictor:
    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        registry_path: Path = REGISTRY_PATH,
    ) -> None:
        self.model_path = model_path
        self.registry_path = registry_path
        self.model = None
        self.model_version = None

    def _ensure_loaded(self) -> None:
        if self.model is not None:
            return

        if not self.model_path.exists():
            if settings.environment != "development":
                raise RuntimeError(
                    "Model artifact is missing. Run the training pipeline before starting production."
                )

            from app.services.training import train_model

            train_model(model_path=str(self.model_path))

        self.model = joblib.load(self.model_path)
        self.model_version = self._load_model_version()

    def _load_model_version(self) -> str:
        if not self.registry_path.exists():
            return "random-forest-unknown"

        try:
            registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
            return str(registry.get("version", "random-forest-unknown"))
        except (OSError, ValueError, TypeError):
            return "random-forest-unknown"

    def predict(
        self,
        symbol: str,
        history: list[dict[str, object]],
    ) -> dict[str, object]:
        self._ensure_loaded()

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
            "model": self.model_version or "random-forest-unknown",
            "cached": False,
        }

    @staticmethod
    def cache_key(
        symbol: str,
        history: list[dict[str, object]],
    ) -> str:
        raw = f"{symbol}:{history[-10:]}".encode()
        return "prediction:" + sha256(raw).hexdigest()
