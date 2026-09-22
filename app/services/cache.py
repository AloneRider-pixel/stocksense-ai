from __future__ import annotations

import json
from typing import Any

from redis import Redis

from app.core.config import settings


class PredictionCache:
    def __init__(self) -> None:
        self.client = Redis.from_url(settings.redis_url, decode_responses=True)

    def get(self, key: str) -> dict[str, Any] | None:
        value = self.client.get(key)
        return json.loads(value) if value else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self.client.setex(
            key,
            settings.cache_ttl_seconds,
            json.dumps(value),
        )
