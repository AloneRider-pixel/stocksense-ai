from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PredictionRecord, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.email == email)
        )

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        user_id: int | None,
        symbol: str,
        predicted_close: float,
        expected_change_pct: float,
        model: str,
        cached: bool,
    ) -> PredictionRecord:
        record = PredictionRecord(
            user_id=user_id,
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

    def list_recent(
        self,
        *,
        user_id: int | None = None,
        symbol: str | None = None,
        limit: int = 20,
    ) -> list[PredictionRecord]:
        stmt = (
            select(PredictionRecord)
            .order_by(PredictionRecord.created_at.desc())
            .limit(limit)
        )

        if user_id is not None:
            stmt = stmt.where(PredictionRecord.user_id == user_id)

        if symbol:
            stmt = stmt.where(PredictionRecord.symbol == symbol)

        return list(self.session.scalars(stmt).all())
