from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    close: float = Field(gt=0)
    volume: float = Field(gt=0)


class PredictionResponse(BaseModel):
    symbol: str
    predicted_close: float
    model: str
    cached: bool = False
