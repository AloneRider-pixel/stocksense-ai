from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Query
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas import (
    PredictionHistoryItem,
    PredictionRequest,
    PredictionResponse,
)
from app.db.database import get_session
from app.db.repository import PredictionRepository
from app.services.cache import PredictionCache
from app.services.predictor import Predictor

router = APIRouter()
predictor = Predictor()
cache = PredictionCache()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "stocksense-ai"}


@router.get("/metrics")
def metrics() -> dict[str, object]:
    metrics_path = Path("models/metrics.json")
    if not metrics_path.exists():
        return {
            "status": "not_available",
            "message": "Run the training module first.",
        }

    return json.loads(metrics_path.read_text(encoding="utf-8"))


@router.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    symbol = request.symbol.upper()
    history = [bar.model_dump() for bar in request.history]
    cache_key = predictor.cache_key(symbol, history)

    cached = cache.get(cache_key)
    if cached is not None:
        cached["cached"] = True
        cached["persisted"] = False
        return PredictionResponse(**cached)

    result = predictor.predict(symbol=symbol, history=history)
    cache.set(cache_key, result)

    persisted = False
    session = get_session()
    try:
        PredictionRepository(session).add(
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


@router.get("/predictions", response_model=list[PredictionHistoryItem])
def prediction_history(
    symbol: str | None = Query(default=None, max_length=16),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[PredictionHistoryItem]:
    session = get_session()
    try:
        records = PredictionRepository(session).list_recent(
            symbol=symbol.upper() if symbol else None,
            limit=limit,
        )
        return [PredictionHistoryItem.model_validate(record) for record in records]
    except SQLAlchemyError:
        return []
    finally:
        session.close()
