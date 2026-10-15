from urllib.parse import unquote, urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StockSense AI"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://stocksense:stocksense@localhost:5432/stocksense"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300

    jwt_secret: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30

    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    cors_origins: str = "http://localhost:5173"
    allowed_hosts: str = "*"

    market_data_provider: str = "twelve_data"
    twelve_data_api_key: str = ""
    twelve_data_base_url: str = "https://api.twelvedata.com"
    market_data_max_rows: int = 5000
    market_data_timeout_seconds: float = 10.0
    market_data_refresh_interval_minutes: int = 30
    market_data_symbols: str = "AAPL,MSFT,GOOGL,AMZN,NVDA"
    market_data_refresh_hour: int = 22
    market_data_refresh_minute: int = 30

    @model_validator(mode="after")
    def reject_insecure_production_defaults(self) -> "Settings":
        validate_production_settings(self)
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        if self.allowed_hosts.strip() == "*":
            return ["*"]
        return [value.strip() for value in self.allowed_hosts.split(",") if value.strip()]

    @property
    def market_data_symbol_list(self) -> list[str]:
        return [
            value.strip().upper()
            for value in self.market_data_symbols.split(",")
            if value.strip()
        ]


DEFAULT_DATABASE_URL = "postgresql+psycopg://stocksense:stocksense@localhost:5432/stocksense"
INSECURE_JWT_SECRETS = {
    "change-this-in-production",
    "local-development-secret-change-me",
    "replace-with-a-random-secret-of-at-least-32-characters",
}
INSECURE_DATABASE_PASSWORDS = {
    "stocksense",
    "local-development-password-change-me",
    "change-me",
    "password",
    "postgres",
    "admin",
}
LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "postgres", "redis"}


def validate_production_settings(config: Settings) -> None:
    """Fail closed when production configuration contains development defaults."""
    if config.environment.strip().casefold() != "production":
        return

    secret = config.jwt_secret.strip()
    if secret.casefold() in INSECURE_JWT_SECRETS or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET must be a non-placeholder secret of at least 32 characters in production."
        )

    allowed_hosts = config.allowed_host_list
    if not allowed_hosts or any(
        "*" in host or host.casefold() in LOCAL_HOSTNAMES for host in allowed_hosts
    ):
        raise RuntimeError(
            "ALLOWED_HOSTS must explicitly list trusted production hostnames without wildcards or local names."
        )

    cors_origins = config.cors_origin_list
    if not cors_origins:
        raise RuntimeError("CORS_ORIGINS must explicitly list trusted HTTPS production origins.")

    for origin in cors_origins:
        try:
            parsed_origin = urlsplit(origin)
        except ValueError as exc:
            raise RuntimeError("CORS_ORIGINS contains an invalid production origin.") from exc
        if (
            parsed_origin.scheme != "https"
            or not parsed_origin.hostname
            or "*" in parsed_origin.hostname
            or parsed_origin.hostname.casefold() in LOCAL_HOSTNAMES
            or parsed_origin.username
            or parsed_origin.password
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            raise RuntimeError(
                "CORS_ORIGINS must contain only explicit HTTPS production origins."
            )

    if config.database_url == DEFAULT_DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be explicitly configured for production.")

    try:
        parsed_database = urlsplit(config.database_url)
        database_port = parsed_database.port
    except ValueError as exc:
        raise RuntimeError("DATABASE_URL is invalid for production.") from exc

    if (
        parsed_database.scheme not in {"postgresql", "postgresql+psycopg"}
        or not parsed_database.hostname
        or parsed_database.hostname.casefold() in LOCAL_HOSTNAMES
        or not parsed_database.username
        or not parsed_database.password
        or not parsed_database.path.strip("/")
        or database_port == 0
    ):
        raise RuntimeError(
            "DATABASE_URL must use a non-local PostgreSQL host and include database, user, and password."
        )

    database_password = unquote(parsed_database.password).casefold()
    if database_password in INSECURE_DATABASE_PASSWORDS:
        raise RuntimeError("DATABASE_URL must not use default development database credentials.")

    try:
        parsed_redis = urlsplit(config.redis_url)
        redis_port = parsed_redis.port
    except ValueError as exc:
        raise RuntimeError("REDIS_URL is invalid for production.") from exc

    if (
        parsed_redis.scheme != "rediss"
        or not parsed_redis.hostname
        or parsed_redis.hostname.casefold() in LOCAL_HOSTNAMES
        or redis_port == 0
    ):
        raise RuntimeError(
            "REDIS_URL must use rediss:// with a non-local production Redis hostname."
        )


# Instantiate only after validate_production_settings is defined, because the
# Settings model validator calls it while loading this module.
settings = Settings()
