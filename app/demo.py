"""Demo-mode seeding: sample data (CSV provider only), demo account, model.

Only ever runs when DEMO_MODE=true on a non-production environment. Demo
deployments exist so reviewers can click through the product with the
checked-in sample data; nothing here represents live market predictions.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from app.auth.service import AuthService
from app.core.config import settings
from app.db.database import get_session, init_db
from app.db.repository import MarketDataRepository
from app.market_data.csv_provider import CSVMarketDataProvider
from app.market_data.factory import get_market_data_provider
from app.market_data.twelve_data import TwelveDataError
from app.services.features import FEATURE_COLUMNS, build_training_frame
from app.services.predictor import MODEL_PATH

logger = logging.getLogger(__name__)

MODELS_DIR = Path("models")
LIVE_MODEL_ROWS = 500
LIVE_MODEL_MIN_ROWS = 120


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


def _ingest_live_symbols(session) -> int:
    """Pull configured symbols from the live provider (skips fresh data)."""
    provider = get_market_data_provider()
    repository = MarketDataRepository(session)
    ingested = 0
    for symbol in settings.market_data_symbol_list:
        stored = repository.list_history(symbol, limit=1)
        if stored:
            last_ingested = stored[-1].ingested_at
            if last_ingested is not None and last_ingested.tzinfo is None:
                last_ingested = last_ingested.replace(tzinfo=timezone.utc)
            if last_ingested is not None and last_ingested >= datetime.now(
                timezone.utc
            ) - timedelta(minutes=settings.market_data_refresh_interval_minutes):
                continue
        try:
            bars = provider.history(symbol, limit=LIVE_MODEL_ROWS)
        except (TwelveDataError, ValueError) as exc:
            logger.warning("demo seed: live ingestion failed for %s: %s", symbol, exc)
            continue
        if bars:
            ingested += repository.upsert_many(
                [
                    {
                        "date": date.fromisoformat(bar.date),
                        "symbol": bar.symbol,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                        "source_provider": getattr(
                            provider, "name", provider.__class__.__name__
                        ),
                    }
                    for bar in bars
                ]
            )
    return ingested


def _train_live_symbol_models(session) -> int:
    """Fit one small model per ingested symbol so demo predictions stay in range.

    The global sample model and its walk-forward metrics are left untouched;
    these per-symbol artifacts only serve predictions in the live-data demo.
    """
    repository = MarketDataRepository(session)
    trained = 0
    for symbol in settings.market_data_symbol_list:
        model_path = MODELS_DIR / f"stocksense_rf_{symbol}.joblib"
        if model_path.exists():
            continue
        rows = repository.list_history(symbol, limit=LIVE_MODEL_ROWS)
        if len(rows) < LIVE_MODEL_MIN_ROWS:
            continue
        frame = build_training_frame(
            pd.DataFrame(
                [
                    {
                        "date": row.date.isoformat(),
                        "close": float(row.close),
                        "volume": int(row.volume),
                    }
                    for row in rows
                ]
            )
        )
        if len(frame) < 80:
            continue
        model = RandomForestRegressor(
            n_estimators=120,
            random_state=42,
            min_samples_leaf=2,
            n_jobs=-1,
        )
        model.fit(frame[FEATURE_COLUMNS], frame["target"])
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, model_path)
        trained += 1
    return trained


def seed_demo_environment() -> None:
    """Idempotent demo bootstrap; safe to call on every startup."""
    if settings.environment.strip().casefold() == "production":
        logger.warning("DEMO_MODE ignored in production")
        return

    init_db()
    session = get_session()
    try:
        inserted = 0
        trained = 0
        if settings.market_data_provider.strip().lower() == "csv":
            # Only the CSV provider needs the checked-in sample data. With a
            # live provider configured, symbols are ingested on demand instead.
            inserted = _seed_market_data(session)
        else:
            inserted = _ingest_live_symbols(session)
            trained = _train_live_symbol_models(session)
        _seed_demo_user(session)
        logger.info(
            "demo seed: %d bars upserted, %d live symbol models trained",
            inserted,
            trained,
        )
    finally:
        session.close()

    try:
        _ensure_sample_model()
    except Exception:
        logger.exception("demo seed: sample model training failed")
