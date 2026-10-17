from __future__ import annotations

import fakeredis

from app.core.config import settings
from app.services.cache import PredictionCache
from app.services.rate_limit import RateLimiter


def make_cache():
    cache = PredictionCache()
    cache.client = fakeredis.FakeStrictRedis(decode_responses=True)
    return cache


def make_limiter():
    limiter = RateLimiter()
    limiter.client = fakeredis.FakeStrictRedis(decode_responses=True)
    return limiter


def test_cache_round_trip():
    cache = make_cache()

    assert cache.set("key", {"value": 1}) is True
    assert cache.get("key") == {"value": 1}


def test_cache_miss_returns_none():
    assert make_cache().get("absent") is None


def test_cache_degrades_when_redis_unavailable():
    cache = PredictionCache()  # no Redis server in tests

    assert cache.get("key") is None
    assert cache.set("key", {"value": 1}) is False


def test_rate_limiter_allows_within_limit():
    limiter = make_limiter()

    allowed, remaining = limiter.check("client-1")

    assert allowed is True
    assert remaining == settings.rate_limit_requests - 1


def test_rate_limiter_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_requests", 2)
    limiter = make_limiter()

    assert limiter.check("client-2")[0] is True
    assert limiter.check("client-2")[0] is True
    allowed, remaining = limiter.check("client-2")

    assert allowed is False
    assert remaining == 0
    assert limiter.retry_after() >= 1


def test_rate_limiter_degrades_when_redis_unavailable():
    limiter = RateLimiter()  # no Redis server in tests

    allowed, remaining = limiter.check("client-3")

    assert allowed is True
    assert remaining == settings.rate_limit_requests
