"""Save and load model artifacts without pickle.

Artifacts are written with skops and loaded with an explicit allow-list of types. Unlike pickle or
joblib, skops does not run arbitrary code from the file. This is a reduction of risk, not a promise
that a hostile file is harmless:

* ``sklearn.tree._tree.Tree`` has to be trusted for any tree model. It stores raw node indices that
  scikit-learn does not bounds-check, so a tampered file can crash the process or read out of bounds
  when predicting. Only files this service wrote into its own model directory should be loaded.
* skops had load-time code-execution bugs before 0.12.0 (CVE-2025-54413); the pinned version is newer.
* Legacy ``.joblib`` pickle files are never loaded. Regenerate them with the training pipeline.
"""
from __future__ import annotations

import os
from pathlib import Path

from skops.io import dump, load

TRUSTED_TYPES = ["sklearn.tree._tree.Tree"]


class ModelIncompatibleError(RuntimeError):
    """The saved model cannot be used by this version of the service."""


def save_model(model: object, path: str | os.PathLike[str]) -> None:
    dump(model, Path(path))


def load_model(path: str | os.PathLike[str]) -> object:
    try:
        return load(Path(path), trusted=TRUSTED_TYPES)
    except Exception as exc:  # skops raises several types for non-skops or untrusted content
        raise ModelIncompatibleError(
            f"Model artifact {Path(path).name} is not a readable skops artifact with only trusted types "
            f"({type(exc).__name__}). Legacy pickle/joblib files are never loaded; regenerate it with the "
            "training pipeline."
        ) from exc
