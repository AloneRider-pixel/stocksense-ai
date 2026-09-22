from app.core.config import settings
from app.api.security import require_api_key


def test_missing_api_key_is_rejected() -> None:
    settings.api_key = "test-key"

    from fastapi import HTTPException

    try:
        require_api_key(None)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail["code"] == "UNAUTHORIZED"
    else:
        raise AssertionError("Expected missing API key to be rejected")


def test_valid_api_key_is_accepted() -> None:
    settings.api_key = "test-key"

    assert require_api_key("test-key") == "test-key"
