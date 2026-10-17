"""Demo-mode seeding: sample data, demo account, and a trained sample model.

Only ever runs when DEMO_MODE=true on a non-production environment. Demo
deployments exist so reviewers can click through the product with the
checked-in sample data; nothing here represents live market predictions.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from app.auth.service import AuthService
from app.core.config import settings
from app.db.database import get_session, init_db
from app.db.repository import MarketDataRepository
from app.market_data.csv_provider import CSVMarketDataProvider
from app.services.predictor import MODEL_PATH

logger = logging.getLogger(__name__)


def _seed_market_data(session) -> int:
    provider = CSVMarketDataProvider()
    bars = provider.history("DEMO", limit=5000)
    if not bars:
        return 0
    repository = MarketDataRepository(session)
    return repository.upsert_many(
        [
            {
                "date": date.fromisoformat(bar.date),
                "symbol": bar.symbol,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "source_provider": "csv-sample",
            }
            for bar in bars
        ]
    )


def _seed_demo_user(session) -> None:
    service = AuthService(session)
    try:
        service.register(
            email=settings.demo_user_email,
            password=settings.demo_user_password,
            full_name="Demo Reviewer",
        )
    except ValueError:
        pass  # demo account already exists


def _ensure_sample_model() -> None:
    if Path(MODEL_PATH).exists():
        return
    from app.services.training import train_model

    train_model()


def seed_demo_environment() -> None:
    """Idempotent demo bootstrap; safe to call on every startup."""
    if settings.environment.strip().casefold() == "production":
        logger.warning("DEMO_MODE ignored in production")
        return

    init_db()
    session = get_session()
    try:
        inserted = _seed_market_data(session)
        _seed_demo_user(session)
        logger.info("demo seed: %d sample bars upserted", inserted)
    finally:
        session.close()

    try:
        _ensure_sample_model()
    except Exception:
        logger.exception("demo seed: sample model training failed")
