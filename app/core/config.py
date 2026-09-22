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

    api_key: str = ""
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    cors_origins: str = "http://localhost:5173"
    allowed_hosts: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        if self.allowed_hosts.strip() == "*":
            return ["*"]
        return [value.strip() for value in self.allowed_hosts.split(",") if value.strip()]


settings = Settings()
