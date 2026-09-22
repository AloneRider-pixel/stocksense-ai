from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StockSense AI"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://stocksense:stocksense@localhost:5432/stocksense"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
