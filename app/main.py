import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.api.data_health_routes import router as data_health_router
from app.api.scanner_routes import router as scanner_router
from app.api.alert_routes import router as alert_router
from app.api.wallet_routes import router as wallet_router
from app.auth.routes import router as auth_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.db.database import engine, init_db
from app.http.middleware import RequestContextMiddleware
from app.observability import MetricsMiddleware, prometheus_response
from app.services.cache import PredictionCache


configure_logging(settings.log_level, settings.log_format)


async def _finish_demo_bootstrap(application: FastAPI) -> None:
    try:
        from app.demo import seed_demo_environment

        await asyncio.to_thread(seed_demo_environment)
    except Exception:
        application.state.bootstrap_status = "failed"
        logging.getLogger(__name__).exception("Demo bootstrap failed; market routes remain unavailable")
    else:
        application.state.bootstrap_status = "ready"


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.bootstrap_status = "ready"
    task = None
    if settings.environment.strip().casefold() != "production":
        try:
            init_db()
            if settings.demo_mode:
                from app.demo import _seed_demo_user
                from app.db.database import get_session

                # Login is usable before optional provider/model work completes.
                with get_session() as session:
                    _seed_demo_user(session)
                application.state.bootstrap_status = "pending"
                task = asyncio.create_task(_finish_demo_bootstrap(application))
        except Exception:
            application.state.bootstrap_status = "failed"
            logging.getLogger(__name__).exception("Application bootstrap failed")
    try:
        yield
    finally:
        if task is not None:
            # Do not abandon an active DB write or model artifact on shutdown.
            await task


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Market intelligence platform for stock analysis, prediction, and monitoring.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

async def bootstrap_guard(request: Request, call_next):
    status = getattr(request.app.state, "bootstrap_status", "ready")
    path = request.url.path
    exempt = path.startswith("/api/v1/auth/") or path in {
        "/api/v1/data-health", "/api/v1/health",
    }
    if status != "ready" and path.startswith("/api/v1/") and not exempt and request.method != "OPTIONS":
        message = (
            "Market data and models are still starting. Wait a moment and retry."
            if status == "pending" else
            "Market startup failed. Data and prediction routes are unavailable."
        )
        return await http_exception_handler(request, HTTPException(
            status_code=503,
            detail={"code": "BOOTSTRAP_UNAVAILABLE", "message": message},
            headers={"Retry-After": "15"} if status == "pending" else None,
        ))
    return await call_next(request)


app.add_middleware(BaseHTTPMiddleware, dispatch=bootstrap_guard)
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
def readiness(request: Request):
    checks: dict[str, str] = {}
    overall = True
    bootstrap = getattr(request.app.state, "bootstrap_status", "ready")
    checks["bootstrap"] = bootstrap
    if bootstrap != "ready":
        return JSONResponse(status_code=503, content={"status": "starting" if bootstrap == "pending" else "unavailable", "checks": checks})

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

    return JSONResponse(status_code=200 if overall else 503, content={
        "status": "ready" if overall else "degraded",
        "checks": checks,
    })


app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(scanner_router, prefix="/api/v1")
app.include_router(wallet_router, prefix="/api/v1")
app.include_router(alert_router, prefix="/api/v1")

app.include_router(data_health_router, prefix="/api/v1")
