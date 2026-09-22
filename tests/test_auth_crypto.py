from app.auth.jwt import create_access_token, decode_access_token
from app.auth.passwords import hash_password, verify_password
from app.core.config import settings


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct-horse-battery-staple")
    assert encoded != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_round_trip() -> None:
    original_secret = settings.jwt_secret
    settings.jwt_secret = "test-secret"

    try:
        token = create_access_token("42")
        assert decode_access_token(token) == "42"
    finally:
        settings.jwt_secret = original_secret
