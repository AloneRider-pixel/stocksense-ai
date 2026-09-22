import pytest

from app.services.features import build_features


def test_build_features_returns_expected_shape() -> None:
    features = build_features(100.0, 1_000_000)

    assert len(features) == 6
    assert all(value > 0 for value in features)


def test_build_features_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        build_features(0, 1_000_000)
