from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.db.database import init_db


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description="StockSense AI prediction and analysis API.",
)


@app.on_event("startup")
def startup() -> None:
    try:
        init_db()
    except Exception:
        # Keep the API usable when PostgreSQL is unavailable during local development.
        pass


app.include_router(router, prefix="/api/v1")
