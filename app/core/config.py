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


settings = Settings()

DEFAULT_DATABASE_URL = "postgresql+psycopg://stocksense:stocksense@localhost:5432/stocksense"
INSECURE_JWT_SECRETS = {
    "change-this-in-production",
    "local-development-secret-change-me",
    "replace-with-a-random-secret-of-at-least-32-characters",
}


def validate_production_settings(config: Settings) -> None:
    """Fail closed when production configuration still contains development defaults."""
    if config.environment.strip().lower() != "production":
        return

    if config.jwt_secret in INSECURE_JWT_SECRETS or len(config.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be a non-placeholder secret of at least 32 characters in production.")

    if config.allowed_host_list == ["*"] or not config.allowed_host_list:
        raise RuntimeError("ALLOWED_HOSTS must explicitly list trusted production hostnames.")

    if config.database_url == DEFAULT_DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be explicitly configured for production.")

    try:
        from urllib.parse import urlsplit

        parsed = urlsplit(config.database_url)
    except ValueError as exc:
        raise RuntimeError("DATABASE_URL is invalid for production.") from exc

    if parsed.username == "stocksense" and parsed.password == "stocksense":
        raise RuntimeError("DATABASE_URL must not use the default development database credentials.")
