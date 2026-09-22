from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MarketBar:
    date: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataProvider(Protocol):
    def history(self, symbol: str, limit: int = 100) -> list[MarketBar]:
        ...
