"""The saved model artifact, the training function and the live feature builder must agree."""
import json
from pathlib import Path

import pandas as pd
import pytest
from sklearn.ensemble import RandomForestRegressor

from app.services.features import FEATURE_COLUMNS, build_prediction_features
from app.services.model_io import ModelIncompatibleError, load_model, save_model
from app.services.predictor import Predictor, check_model_compatible
from app.services.training import train_model


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    d = tmp_path_factory.mktemp("models")
    paths = dict(
        model_path=str(d / "m.skops"),
        metrics_path=str(d / "metrics.json"),
        registry_path=str(d / "registry.json"),
        predictions_path=str(d / "wf.csv"),
    )
    train_model(**paths)  # the real training function on the bundled sample CSV
    return d, paths


def test_real_training_artifact_matches_feature_columns_and_registry(trained):
    d, paths = trained
    model = load_model(paths["model_path"])
    assert list(model.feature_names_in_) == list(FEATURE_COLUMNS)
    assert json.loads(Path(paths["registry_path"]).read_text())["features"] == list(FEATURE_COLUMNS)
    check_model_compatible(model, "m.skops")


def test_real_artifact_predicts_on_fixed_history_with_live_feature_builder(trained):
    d, paths = trained
    history = [{"date": f"2024-01-{i + 1:02d}", "open": 100 + i, "high": 101 + i, "low": 99 + i,
                "close": 100 + i * 0.5, "volume": 1000 + 10 * i} for i in range(30)]
    row = build_prediction_features(history)
    assert list(pd.DataFrame([row], columns=FEATURE_COLUMNS).columns) == list(FEATURE_COLUMNS)
    predictor = Predictor(model_path=Path(paths["model_path"]), registry_path=Path(paths["registry_path"]))
    out = predictor.predict("TEST", history)
    assert out["predicted_close"] > 0


def test_incompatible_old_artifact_fails_cleanly_and_is_not_rewritten(tmp_path):
    old = tmp_path / "old.skops"
    X = pd.DataFrame({"legacy_a": [1.0, 2, 3, 4, 5, 6], "legacy_b": [2.0, 1, 4, 3, 6, 5]})
    save_model(RandomForestRegressor(n_estimators=3, random_state=0).fit(X, [1, 2, 3, 4, 5, 6]), old)
    before = old.read_bytes()
    predictor = Predictor(model_path=old, registry_path=tmp_path / "none.json")
    history = [{"date": f"2024-01-{i + 1:02d}", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0 + i, "volume": 1000} for i in range(30)]
    with pytest.raises(ModelIncompatibleError):
        predictor.predict("TEST", history)
    assert old.read_bytes() == before  # not retrained, not overwritten
    assert not list(tmp_path.glob("*.json"))  # no registry/metrics written either


def test_reordered_feature_names_are_rejected():
    X = pd.DataFrame([[1.0] * len(FEATURE_COLUMNS), [2.0] * len(FEATURE_COLUMNS), [3.0] * len(FEATURE_COLUMNS), [4.0] * len(FEATURE_COLUMNS)], columns=list(reversed(FEATURE_COLUMNS)))
    model = RandomForestRegressor(n_estimators=2, random_state=0).fit(X, [1, 2, 3, 4])
    with pytest.raises(ModelIncompatibleError):
        check_model_compatible(model, "reordered.skops")


def _bare_array_model(columns_reversed: bool):
    import numpy as np

    n = len(FEATURE_COLUMNS)
    X = np.arange(8 * n, dtype=float).reshape(8, n)
    if columns_reversed:
        X = X[:, ::-1]
    return RandomForestRegressor(n_estimators=2, random_state=0).fit(X, np.arange(8, dtype=float))


def test_artifact_without_feature_names_needs_a_matching_registry():
    model = _bare_array_model(False)
    assert getattr(model, "feature_names_in_", None) is None
    with pytest.raises(ModelIncompatibleError):
        check_model_compatible(model, "bare.skops")
    with pytest.raises(ModelIncompatibleError):
        check_model_compatible(model, "bare.skops", registry_features=list(reversed(FEATURE_COLUMNS)))
    check_model_compatible(model, "bare.skops", registry_features=list(FEATURE_COLUMNS))


def test_load_path_stays_inside_the_model_directory_and_unsafe_symbol_keys_use_the_global_model(tmp_path):
    import shutil

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    outside = tmp_path / "outside.skops"
    X = pd.DataFrame([[float(i)] * len(FEATURE_COLUMNS) for i in range(1, 6)], columns=list(FEATURE_COLUMNS))
    save_model(RandomForestRegressor(n_estimators=2, random_state=0).fit(X, [1, 2, 3, 4, 5]), outside)
    # a symlink in the model directory that points outside is refused
    (model_dir / "m.skops").symlink_to(outside)
    predictor = Predictor(model_path=model_dir / "m.skops", registry_path=model_dir / "r.json")
    with pytest.raises(ModelIncompatibleError):
        predictor._load_artifact(model_dir / "m.skops")
    # a real file inside loads; a traversal-looking symbol never builds a file name
    (model_dir / "m.skops").unlink()
    shutil.copy(outside, model_dir / "m.skops")
    predictor = Predictor(model_path=model_dir / "m.skops", registry_path=model_dir / "r.json")
    model, _ = predictor._model_for("../../outside")
    assert model is not None


def test_skops_round_trip_predicts_identically(tmp_path):
    X = pd.DataFrame([[float(i + j) for j in range(len(FEATURE_COLUMNS))] for i in range(1, 30)], columns=list(FEATURE_COLUMNS))
    model = RandomForestRegressor(n_estimators=5, random_state=0).fit(X, [float(i) for i in range(1, 30)])
    path = tmp_path / "m.skops"
    save_model(model, path)
    loaded = load_model(path)
    assert list(loaded.predict(X)) == list(model.predict(X))
    assert list(loaded.feature_names_in_) == list(FEATURE_COLUMNS)


def test_legacy_pickle_and_garbage_files_are_refused_not_loaded(tmp_path):
    import pickle

    marker = tmp_path / "executed"

    class Boom:
        def __reduce__(self):
            return (marker.write_text, ("pwned",))

    legacy = tmp_path / "legacy.skops"
    legacy.write_bytes(pickle.dumps(Boom()))
    with pytest.raises(ModelIncompatibleError):
        load_model(legacy)
    assert not marker.exists()
    junk = tmp_path / "junk.skops"
    junk.write_bytes(b"not a model")
    with pytest.raises(ModelIncompatibleError):
        load_model(junk)
