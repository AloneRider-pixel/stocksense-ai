from fastapi import APIRouter

from app.api.schemas import PredictionRequest, PredictionResponse
from app.services.predictor import Predictor

router = APIRouter()
predictor = Predictor()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "stocksense-ai"}


@router.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    result = predictor.predict(
        symbol=request.symbol.upper(),
        history=[bar.model_dump() for bar in request.history],
    )
    return PredictionResponse(**result)
