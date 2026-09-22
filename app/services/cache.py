from __future__ import annotations

import json
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


class PredictionCache:
    def __init__(self) -> None:
        self.client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
        )

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            value = self.client.get(key)
            return json.loads(value) if value else None
        except (RedisError, ValueError):
            return None

    def set(self, key: str, value: dict[str, Any]) -> bool:
        try:
            self.client.setex(
                key,
                settings.cache_ttl_seconds,
                json.dumps(value),
            )
            return True
        except RedisError:
            return False
