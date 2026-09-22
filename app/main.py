from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="StockSense AI prediction and analysis API.",
)

app.include_router(router, prefix="/api/v1")
