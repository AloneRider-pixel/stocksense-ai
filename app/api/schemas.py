from pydantic import BaseModel, Field


class MarketBar(BaseModel):
    close: float = Field(gt=0)
    volume: float = Field(gt=0)


class PredictionRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    history: list[MarketBar] = Field(min_length=10)


class PredictionResponse(BaseModel):
    symbol: str
    predicted_close: float
    expected_change_pct: float
    model: str
    cached: bool = False
