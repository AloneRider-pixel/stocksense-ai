from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketBar(BaseModel):
    date: date
    close: float = Field(gt=0)
    volume: float = Field(gt=0)


class PredictionRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    history: list[MarketBar] = Field(min_length=11)


class PredictionResponse(BaseModel):
    symbol: str
    prediction_date: date
    predicted_close: float
    expected_change_pct: float
    model: str
    cached: bool = False
    persisted: bool = False


class PredictionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    prediction_date: date
    predicted_close: float
    expected_change_pct: float
    model: str
    cached: bool
    actual_date: date | None
    actual_close: float | None
    absolute_error: float | None
    percentage_error: float | None
    direction_correct: bool | None
    evaluated_at: datetime | None
    created_at: datetime
