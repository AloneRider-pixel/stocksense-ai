from __future__ import annotations

import time

from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_COUNT = Counter(
    "stocksense_http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "stocksense_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        REQUEST_COUNT.labels(
            request.method,
            request.url.path,
            str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(
            request.method,
            request.url.path,
        ).observe(elapsed)

        return response


def prometheus_response() -> Response:
    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4",
    )
