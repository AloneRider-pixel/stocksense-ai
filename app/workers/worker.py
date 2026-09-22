from arq import cron
from arq.connections import RedisSettings
from arq.worker import Worker

from app.core.config import settings
from app.workers.tasks import refresh_configured_markets, refresh_market_data


class WorkerSettings:
    functions = [refresh_market_data, refresh_configured_markets]
    cron_jobs = [
        cron(
            refresh_configured_markets,
            hour=settings.market_data_refresh_hour,
            minute=settings.market_data_refresh_minute,
            max_tries=3,
            timeout=900,
        )
    ]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 900
    max_tries = 3


if __name__ == "__main__":
    Worker(WorkerSettings).run()
