from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PredictionRecord


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        symbol: str,
        predicted_close: float,
        expected_change_pct: float,
        model: str,
        cached: bool,
    ) -> PredictionRecord:
        record = PredictionRecord(
            symbol=symbol,
            predicted_close=predicted_close,
            expected_change_pct=expected_change_pct,
            model=model,
            cached=cached,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_recent(self, symbol: str | None = None, limit: int = 20) -> list[PredictionRecord]:
        stmt = select(PredictionRecord).order_by(PredictionRecord.created_at.desc()).limit(limit)
        if symbol:
            stmt = stmt.where(PredictionRecord.symbol == symbol)

        return list(self.session.scalars(stmt).all())
