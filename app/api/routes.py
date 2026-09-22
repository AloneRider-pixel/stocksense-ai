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
from app.db.repository import PredictionRepository
from app.market_data.csv_provider import CSVMarketDataProvider
from app.market_data.service import MarketDataService
from app.services.cache import PredictionCache
from app.services.predictor import Predictor

router = APIRouter()
predictor = Predictor()
cache = PredictionCache()
market_data = MarketDataService(CSVMarketDataProvider())


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "stocksense-ai"}


@router.get("/stocks/{symbol}/history", dependencies=[Depends(enforce_rate_limit)])
def stock_history(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, object]]:
    try:
        bars = market_data.history(symbol, limit)
        if not bars:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SYMBOL_NOT_FOUND",
                    "message": f"No market data found for symbol '{symbol.upper()}'.",
                },
            )
        return [bar.__dict__ for bar in bars]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "MARKET_DATA_INPUT_ERROR",
                "message": str(exc),
            },
        ) from exc


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

    cache.set(cache_key, result)

    persisted = False
    session = get_session()
    try:
        PredictionRepository(session).add(
            user_id=current_user.id,
            symbol=symbol,
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
    symbol: str | None = Query(default=None, max_length=16),
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
