from fastapi import APIRouter

from app.api.schemas import PredictionRequest, PredictionResponse
from app.services.cache import PredictionCache
from app.services.predictor import Predictor

router = APIRouter()
predictor = Predictor()
cache = PredictionCache()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "stocksense-ai"}


@router.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    symbol = request.symbol.upper()
    history = [bar.model_dump() for bar in request.history]
    cache_key = predictor.cache_key(symbol, history)

    cached = cache.get(cache_key)
    if cached is not None:
        cached["cached"] = True
        return PredictionResponse(**cached)

    result = predictor.predict(symbol=symbol, history=history)
    cache.set(cache_key, result)
    return PredictionResponse(**result)
