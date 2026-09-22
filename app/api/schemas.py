from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    persisted: bool = False


class PredictionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    predicted_close: float
    expected_change_pct: float
    model: str
    cached: bool
    created_at: datetime
