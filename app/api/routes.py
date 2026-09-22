from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.rate_limit_dependency import enforce_rate_limit
from app.api.schemas import (
    PredictionHistoryItem,
    PredictionRequest,
    PredictionResponse,
)
from app.auth.dependencies import get_current_user
from app.db.database import get_session
from app.db.repository import MarketDataRepository, PredictionRepository
from app.market_data.factory import get_market_data_provider
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.twelve_data import TwelveDataError
from app.services.cache import PredictionCache
from app.services.predictor import Predictor

router = APIRouter()
predictor = Predictor()
cache = PredictionCache()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "stocksense-ai"}


def _ingest_symbol(symbol: str, limit: int) -> dict[str, int | str]:
    session = get_session()
    try:
        repository = MarketDataRepository(session)
        prediction_repository = PredictionRepository(session)
        service = MarketDataIngestionService(
            get_market_data_provider(),
            repository,
            prediction_repository,
        )
        return service.ingest(symbol, limit=limit)
    finally:
        session.close()


@router.post(
    "/stocks/{symbol}/ingest",
    dependencies=[Depends(enforce_rate_limit)],
)
def ingest_market_data(
    symbol: str,
    limit: int = Query(default=500, ge=20, le=5000),
) -> dict[str, int | str]:
    try:
        return _ingest_symbol(symbol, limit)
    except (ValueError, TwelveDataError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MARKET_DATA_PROVIDER_ERROR",
                "message": str(exc),
            },
        ) from exc


@router.get(
    "/stocks/{symbol}/history",
    dependencies=[Depends(enforce_rate_limit)],
)
def stock_history(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=5000),
) -> list[dict[str, object]]:
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "MARKET_DATA_INPUT_ERROR",
                "message": "Symbol is required.",
            },
        )

    session = get_session()
    try:
        repository = MarketDataRepository(session)
        stored = repository.list_history(normalized, limit=limit)

        if len(stored) < limit:
            try:
                provider = get_market_data_provider()
                bars = provider.history(normalized, limit=limit)
                if bars:
                    repository.upsert_many(
                        [
                            {
                                "date": bar.date,
                                "symbol": bar.symbol,
                                "open": bar.open,
                                "high": bar.high,
                                "low": bar.low,
                                "close": bar.close,
                                "volume": bar.volume,
                                "source_provider": getattr(
                                    provider,
                                    "name",
                                    provider.__class__.__name__,
                                ),
                            }
                            for bar in bars
                        ]
                    )
                    stored = repository.list_history(normalized, limit=limit)
            except TwelveDataError as exc:
                if not stored:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={
                            "code": "MARKET_DATA_PROVIDER_ERROR",
                            "message": str(exc),
                        },
                    ) from exc

        if not stored:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SYMBOL_NOT_FOUND",
                    "message": f"No market data found for symbol '{normalized}'.",
                },
            )

        return [
            {
                "date": row.date.isoformat(),
                "symbol": row.symbol,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
                "source_provider": row.source_provider,
            }
            for row in stored
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Market data is temporarily unavailable.",
            },
        ) from exc
    finally:
        session.close()


@router.get("/metrics", dependencies=[Depends(enforce_rate_limit)])
def metrics() -> dict[str, object]:
    metrics_path = Path("models/metrics.json")
    if not metrics_path.exists():
        return {
            "status": "not_available",
            "message": "Run the training module first.",
        }

    return json.loads(metrics_path.read_text(encoding="utf-8"))


@router.post(
    "/predict",
    response_model=PredictionResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
def predict(
    request: PredictionRequest,
    current_user=Depends(get_current_user),
) -> PredictionResponse:
    symbol = request.symbol.upper()
    history = [bar.model_dump() for bar in request.history]
    prediction_date = history[-1]["date"]
    cache_key = predictor.cache_key(symbol, history)

    cached = cache.get(cache_key)
    if cached is not None:
        cached["cached"] = True
        cached["persisted"] = False
        return PredictionResponse(**cached)

    try:
        result = predictor.predict(symbol=symbol, history=history)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "PREDICTION_INPUT_ERROR",
                "message": str(exc),
            },
        ) from exc

    result["prediction_date"] = prediction_date
    cache.set(cache_key, result)

    persisted = False
    session = get_session()
    try:
        PredictionRepository(session).add(
            user_id=current_user.id,
            symbol=symbol,
            prediction_date=prediction_date,
            predicted_close=float(result["predicted_close"]),
            expected_change_pct=float(result["expected_change_pct"]),
            model=str(result["model"]),
            cached=False,
        )
        persisted = True
    except SQLAlchemyError:
        session.rollback()
    finally:
        session.close()

    result["persisted"] = persisted
    return PredictionResponse(**result)


@router.get(
    "/predictions",
    response_model=list[PredictionHistoryItem],
    dependencies=[Depends(enforce_rate_limit)],
)
def prediction_history(
    symbol: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_user),
) -> list[PredictionHistoryItem]:
    session = get_session()
    try:
        records = PredictionRepository(session).list_recent(
            user_id=current_user.id,
            symbol=symbol.upper() if symbol else None,
            limit=limit,
        )
        return [PredictionHistoryItem.model_validate(record) for record in records]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Prediction history is temporarily unavailable.",
            },
        ) from exc
    finally:
        session.close()


@router.get(
    "/predictions/evaluation",
    dependencies=[Depends(enforce_rate_limit)],
)
def prediction_evaluation(
    symbol: str | None = Query(default=None, max_length=32),
    current_user=Depends(get_current_user),
) -> dict[str, float | int | None]:
    session = get_session()
    try:
        repository = PredictionRepository(session)
        return repository.evaluation_summary(
            user_id=current_user.id,
            symbol=symbol.upper() if symbol else None,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Prediction evaluation is temporarily unavailable.",
            },
        ) from exc
    finally:
        session.close()
