from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.api.routes import router
from app.core.config import settings
from app.core.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.db.database import init_db


app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description="StockSense AI prediction and analysis API.",
)


@app.on_event("startup")
def startup() -> None:
    try:
        init_db()
    except Exception:
        pass


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_handler(
    request: Request,
    exc: RequestValidationError,
):
    return await validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def exception_handler(
    request: Request,
    exc: Exception,
):
    return await unhandled_exception_handler(request, exc)


app.include_router(router, prefix="/api/v1")
