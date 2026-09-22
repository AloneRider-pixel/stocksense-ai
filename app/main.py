from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import router
from app.auth.routes import router as auth_router
from app.core.config import settings
from app.core.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.db.database import engine, init_db
from app.http.middleware import RequestContextMiddleware
from app.observability import MetricsMiddleware, prometheus_response
from app.services.cache import PredictionCache


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Market intelligence platform for stock analysis, prediction, and monitoring.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)


@app.on_event("startup")
def startup() -> None:
    if settings.environment == "production" and settings.jwt_secret == "change-this-in-production":
        raise RuntimeError("JWT_SECRET must be replaced in production.")

    if settings.environment != "production":
        try:
            init_db()
        except Exception:
            pass


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return await validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return await unhandled_exception_handler(request, exc)


@app.get("/internal/metrics", include_in_schema=False)
def internal_metrics():
    return prometheus_response()


@app.get("/health/live", include_in_schema=False)
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def readiness() -> dict[str, object]:
    checks: dict[str, str] = {}
    overall = True

    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        overall = False

    try:
        PredictionCache().client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
        overall = False

    return {
        "status": "ready" if overall else "degraded",
        "checks": checks,
    }


app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
