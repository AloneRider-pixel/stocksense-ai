import pytest

from app.core.config import DEFAULT_DATABASE_URL, Settings


def production_settings(**overrides: str) -> Settings:
    values = {
        "environment": "production",
        "database_url": "postgresql+psycopg://prod_user:long-random-db-password@db.example.com:5432/stocksense",
        "jwt_secret": "r4nd0m-production-secret-with-more-than-32-characters",
        "allowed_hosts": "api.example.com,stocks.example.com",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_development_settings_keep_local_defaults() -> None:
    settings = Settings(_env_file=None, environment="development")
    assert settings.jwt_secret == "change-this-in-production"
    assert settings.allowed_host_list == ["*"]


def test_production_accepts_explicit_security_configuration() -> None:
    settings = production_settings()
    assert settings.environment == "production"
    assert settings.allowed_host_list == ["api.example.com", "stocks.example.com"]


@pytest.mark.parametrize(
    "secret",
    [
        "change-this-in-production",
        "local-development-secret-change-me",
        "short",
    ],
)
def test_production_rejects_placeholder_or_short_jwt_secrets(secret: str) -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        production_settings(jwt_secret=secret)


def test_production_rejects_wildcard_hosts() -> None:
    with pytest.raises(RuntimeError, match="ALLOWED_HOSTS"):
        production_settings(allowed_hosts="*")


@pytest.mark.parametrize(
    "database_url",
    [
        DEFAULT_DATABASE_URL,
        "postgresql+psycopg://stocksense:local-development-password-change-me@db.example.com:5432/stocksense",
        "postgresql+psycopg://stocksense:stocksense@db.example.com:5432/stocksense",
    ],
)
def test_production_rejects_default_database_credentials(database_url: str) -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        production_settings(database_url=database_url)
