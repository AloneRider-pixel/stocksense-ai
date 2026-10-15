import pytest

from app.core.config import DEFAULT_DATABASE_URL, Settings


def production_settings(**overrides: str) -> Settings:
    values = {
        "environment": "production",
        "database_url": "postgresql+psycopg://prod_user:long-random-db-password@db.example.com:5432/stocksense",
        "redis_url": "rediss://default:long-random-redis-password@redis.example.com:6380/0",
        "jwt_secret": "r4nd0m-production-secret-with-more-than-32-characters",
        "allowed_hosts": "api.example.com,stocks.example.com",
        "cors_origins": "https://app.example.com",
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
    assert settings.cors_origin_list == ["https://app.example.com"]


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


@pytest.mark.parametrize(
    "hosts",
    ["*", "*.example.com", "api.example.com,*", "localhost", "redis.example.com,localhost"],
)
def test_production_rejects_wildcard_or_local_hosts(hosts: str) -> None:
    with pytest.raises(RuntimeError, match="ALLOWED_HOSTS"):
        production_settings(allowed_hosts=hosts)


@pytest.mark.parametrize(
    "origins",
    [
        "*",
        "http://app.example.com",
        "http://localhost:5173",
        "https://*.example.com",
        "https://localhost:5173",
        "https://app.example.com/path",
    ],
)
def test_production_rejects_unsafe_cors_origins(origins: str) -> None:
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        production_settings(cors_origins=origins)


@pytest.mark.parametrize(
    "database_url",
    [
        DEFAULT_DATABASE_URL,
        "postgresql+psycopg://stocksense:local-development-password-change-me@db.example.com:5432/stocksense",
        "postgresql+psycopg://stocksense:stocksense@db.example.com:5432/stocksense",
        "postgresql+psycopg://user:password@db.example.com:5432/stocksense",
        "postgresql+psycopg://user@db.example.com:5432/stocksense",
        "postgresql+psycopg://user:secure-password@/stocksense",
        "postgresql+psycopg://user:secure-password@postgres:5432/stocksense",
        "sqlite:///stocksense.db",
    ],
)
def test_production_rejects_default_or_incomplete_database_urls(database_url: str) -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        production_settings(database_url=database_url)


def test_production_rejects_url_encoded_weak_database_password() -> None:
    database_url = "postgresql+psycopg://user:pass%77ord@db.example.com:5432/stocksense"
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        production_settings(database_url=database_url)


@pytest.mark.parametrize(
    "redis_url",
    [
        "redis://redis.example.com:6379/0",
        "rediss://localhost:6380/0",
        "redis://redis:6379/0",
    ],
)
def test_production_rejects_unencrypted_or_local_redis(redis_url: str) -> None:
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        production_settings(redis_url=redis_url)
