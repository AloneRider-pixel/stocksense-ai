from __future__ import annotations

import time

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


class RateLimiter:
    def __init__(self) -> None:
        self.client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
        )

    def check(self, client_id: str) -> tuple[bool, int]:
        window = settings.rate_limit_window_seconds
        key = f"ratelimit:{client_id}:{int(time.time()) // window}"

        try:
            count = int(self.client.incr(key))
            if count == 1:
                self.client.expire(key, window)

            remaining = max(settings.rate_limit_requests - count, 0)
            return count <= settings.rate_limit_requests, remaining
        except RedisError:
            return True, settings.rate_limit_requests

    def retry_after(self) -> int:
        window = settings.rate_limit_window_seconds
        now = int(time.time())
        return max(window - (now % window), 1)
