from arq.connections import RedisSettings
from arq.worker import Function, Worker

from app.core.config import settings
from app.workers.tasks import refresh_market_snapshot


class WorkerSettings:
    functions: list[Function] = [Function(refresh_market_snapshot, name="refresh_market_snapshot")]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 300


if __name__ == "__main__":
    Worker(WorkerSettings).run()
