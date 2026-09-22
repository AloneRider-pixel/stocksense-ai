from __future__ import annotations

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings
from app.services.rate_limit import RateLimiter


limiter = RateLimiter()


def enforce_public_rate_limit(request: Request, response: Response) -> None:
    host = request.client.host if request.client else "unknown"
    allowed, remaining = limiter.check(f"ip:{host}")

    response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)

    if not allowed:
        retry_after = limiter.retry_after()
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many authentication attempts. Try again later.",
            },
            headers={"Retry-After": str(retry_after)},
        )
