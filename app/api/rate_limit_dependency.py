from fastapi import Depends, HTTPException, Response, status

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.services.rate_limit import RateLimiter


rate_limiter = RateLimiter()


def enforce_rate_limit(
    response: Response,
    current_user=Depends(get_current_user),
):
    identity = f"user:{current_user.id}"
    allowed, remaining = rate_limiter.check(identity)

    response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)

    if not allowed:
        retry_after = rate_limiter.retry_after()
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Rate limit exceeded. Retry after the current window.",
            },
            headers={"Retry-After": str(retry_after)},
        )

    return current_user
