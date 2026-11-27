from __future__ import annotations

import json
import os
import logging
import re
import warnings
from hashlib import sha256
from pathlib import Path

import joblib
import pandas as pd

from app.core.config import settings
from app.services.features import FEATURE_COLUMNS, build_prediction_features


MODEL_PATH = Path("models/stocksense_rf.joblib")
REGISTRY_PATH = Path("models/registry.json")


def inference_model_label(model_version: str | None) -> str:
    """Preserve short labels and hash long identities within the existing DB limit."""
    base = model_version or "random-forest-unknown"
    suffix = ":latest-bar-v1"
    if len(base) + len(suffix) <= 64:
        return base + suffix
    identity = sha256(base.encode()).hexdigest()[:16]
    return base[:33] + ":" + identity + suffix


_SAFE_KEY = re.compile(r"^[A-Z0-9&^=-]{1,32}$")
logger = logging.getLogger(__name__)


class ModelIncompatibleError(RuntimeError):
    """A saved model artifact does not match the feature schema the code builds."""


def check_model_compatible(model: object, source: str, registry_features: list[str] | None = None) -> None:
    """Fail cleanly when a loaded artifact was fitted on different features.

    Never retrains or rewrites the artifact: the caller gets an error and the
    file on disk is left untouched. An artifact without fitted feature names is
    accepted only when the registry records exactly the current feature list.
    """
    if not callable(getattr(model, "predict", None)):
        raise ModelIncompatibleError(f"Model artifact {source} has no predict method.")
    names = getattr(model, "feature_names_in_", None)
    if names is not None and list(names) != list(FEATURE_COLUMNS):
        raise ModelIncompatibleError(
            f"Model artifact {source} was fitted on different features than this version builds. "
            "Retrain it with the current training pipeline; it was not changed."
        )
    if names is None:
        # No fitted feature names (e.g. trained on a bare array): trust only a registry that records
        # exactly the current feature list. Otherwise the column order cannot be established.
        if registry_features is None or list(registry_features) != list(FEATURE_COLUMNS):
            raise ModelIncompatibleError(
                f"Model artifact {source} has no recorded feature names and the registry does not confirm "
                "the current feature list, so its column order cannot be verified. It was not changed."
            )
    count = getattr(model, "n_features_in_", None)
    if count is not None and int(count) != len(FEATURE_COLUMNS):
        raise ModelIncompatibleError(
            f"Model artifact {source} expects {int(count)} features but this version builds "
            f"{len(FEATURE_COLUMNS)}. Retrain it with the current training pipeline; it was not changed."
        )


class Predictor:
    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        registry_path: Path = REGISTRY_PATH,
    ) -> None:
        self.model_path = model_path
        self.registry_path = registry_path
        self._models: dict[str, tuple[object, str]] = {}

    def _model_for(self, symbol: str) -> tuple[object, str]:
        """Resolve the model for a symbol.

        Per-symbol live-trained artifacts (stocksense_rf_<SYMBOL>.joblib, written
        by the demo seeder from ingested provider data) win over the global
        sample model so predictions stay in the symbol's price range.
        """
        key = symbol.upper()
        if not _SAFE_KEY.match(key):
            key = ""  # never build a file name from unexpected characters; use the global model
        if key in self._models:
            return self._models[key]

        candidates: list[tuple[Path, str | None]] = []
        if key:
            candidates.append(
                (
                    self.model_path.with_name(f"stocksense_rf_{key}.joblib"),
                    f"random-forest-live-{key.lower()}",
                )
            )
        candidates.append((self.model_path, None))

        for path, version in candidates:
            if path.exists():
                loaded = self._load_artifact(path)
                resolved = (loaded, version or self._load_model_version())
                self._models[key] = resolved
                return resolved

        if settings.environment != "development":
            raise RuntimeError(
                "Model artifact is missing. Run the training pipeline before starting production."
            )

        from app.services.training import train_model

        train_model(model_path=str(self.model_path))
        loaded = self._load_artifact(self.model_path)
        resolved = (loaded, self._load_model_version())
        self._models[key] = resolved
        return resolved

    def _registry_features(self) -> list[str] | None:
        try:
            features = json.loads(self.registry_path.read_text(encoding="utf-8")).get("features")
        except (OSError, ValueError, TypeError, AttributeError):
            return None
        return list(features) if isinstance(features, list) else None

    def _load_artifact(self, path: Path) -> object:
        """Load a model file that sits next to the configured model path, then check its schema.

        joblib/pickle executes code on load, so the file must be one this service wrote: it has to
        resolve inside the model directory (no symlink or ".." escape). The check below cannot make an
        untrusted file safe; it only catches honest mismatches. A scikit-learn version mismatch is logged.
        """
        root = os.path.realpath(self.model_path.absolute().parent)
        safe_path = os.path.realpath(os.path.join(root, path.name))
        if os.path.dirname(safe_path) != root or not safe_path.startswith(root + os.sep):
            raise ModelIncompatibleError("Model artifact is outside the model directory and was not loaded.")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            loaded = joblib.load(safe_path)
        for w in caught:
            if "version" in str(w.message).lower():
                logger.warning("model artifact %s loaded with a scikit-learn version warning: %s", path.name, w.message)
        check_model_compatible(loaded, path.name, self._registry_features())
        return loaded

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
        model, model_version = self._model_for(symbol)

        # Named columns in the same order the model was fitted with (FEATURE_COLUMNS), so sklearn can check them.
        features = pd.DataFrame([build_prediction_features(history)], columns=FEATURE_COLUMNS)
        # The model predicts the next-period return ratio; convert to price.
        predicted_ratio = float(model.predict(features)[0])
        current_close = float(history[-1]["close"])
        predicted_close = current_close * predicted_ratio

        return {
            "symbol": symbol,
            "predicted_close": round(predicted_close, 4),
            "expected_change_pct": round(
                ((predicted_close - current_close) / current_close) * 100,
                4,
            ),
            "model": inference_model_label(model_version),
            "cached": False,
        }

    @staticmethod
    def cache_key(
        symbol: str,
        history: list[dict[str, object]],
    ) -> str:
        raw = f"{symbol}:{history[-10:]}".encode()
        return "prediction:latest-bar-v1:" + sha256(raw).hexdigest()
