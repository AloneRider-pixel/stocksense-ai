from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MarketBarRecord, PredictionRecord, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user


class MarketDataRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_many(self, bars: list[dict]) -> int:
        if not bars:
            return 0

        symbols = {str(bar["symbol"]).upper() for bar in bars}
        if len(symbols) != 1:
            raise ValueError("upsert_many expects one symbol per batch")

        symbol = symbols.pop()
        dates = [bar["date"] for bar in bars]
        existing = {
            row.date: row
            for row in self.session.scalars(
                select(MarketBarRecord).where(
                    MarketBarRecord.symbol == symbol,
                    MarketBarRecord.date.in_(dates),
                )
            ).all()
        }

        created = 0
        for payload in bars:
            trading_date = payload["date"]
            row = existing.get(trading_date)

            if row is None:
                self.session.add(
                    MarketBarRecord(
                        symbol=symbol,
                        date=trading_date,
                        open=float(payload["open"]),
                        high=float(payload["high"]),
                        low=float(payload["low"]),
                        close=float(payload["close"]),
                        volume=int(payload["volume"]),
                        source_provider=str(payload["source_provider"]),
                    )
                )
                created += 1
            else:
                row.open = float(payload["open"])
                row.high = float(payload["high"])
                row.low = float(payload["low"])
                row.close = float(payload["close"])
                row.volume = int(payload["volume"])
                row.source_provider = str(payload["source_provider"])

        self.session.commit()
        return created

    def list_history(self, symbol: str, limit: int = 500) -> list[MarketBarRecord]:
        rows = list(
            self.session.scalars(
                select(MarketBarRecord)
                .where(MarketBarRecord.symbol == symbol.upper())
                .order_by(MarketBarRecord.date.desc())
                .limit(limit)
            ).all()
        )
        return list(reversed(rows))


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        user_id: int | None,
        symbol: str,
        prediction_date: date,
        predicted_close: float,
        expected_change_pct: float,
        model: str,
        cached: bool,
    ) -> PredictionRecord:
        record = PredictionRecord(
            user_id=user_id,
            symbol=symbol,
            prediction_date=prediction_date,
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

    def evaluate_pending(self, symbol: str | None = None) -> int:
        stmt = select(PredictionRecord).where(PredictionRecord.actual_date.is_(None))

        if symbol:
            stmt = stmt.where(PredictionRecord.symbol == symbol.upper())

        predictions = list(self.session.scalars(stmt).all())
        evaluated = 0

        for prediction in predictions:
            actual = self.session.scalar(
                select(MarketBarRecord)
                .where(
                    MarketBarRecord.symbol == prediction.symbol,
                    MarketBarRecord.date > prediction.prediction_date,
                )
                .order_by(MarketBarRecord.date.asc())
                .limit(1)
            )

            if actual is None:
                continue

            previous_close = self.session.scalar(
                select(MarketBarRecord.close)
                .where(
                    MarketBarRecord.symbol == prediction.symbol,
                    MarketBarRecord.date == prediction.prediction_date,
                )
            )

            prediction.actual_date = actual.date
            prediction.actual_close = actual.close
            prediction.absolute_error = abs(prediction.predicted_close - actual.close)
            prediction.percentage_error = (
                abs(prediction.predicted_close - actual.close) / actual.close * 100
                if actual.close
                else None
            )

            if previous_close is not None:
                predicted_move = prediction.predicted_close - previous_close
                actual_move = actual.close - previous_close
                prediction.direction_correct = (
                    (predicted_move >= 0 and actual_move >= 0)
                    or (predicted_move < 0 and actual_move < 0)
                )

            prediction.evaluated_at = datetime.now(timezone.utc)
            evaluated += 1

        if evaluated:
            self.session.commit()

        return evaluated


    def evaluation_summary(
        self,
        *,
        user_id: int,
        symbol: str | None = None,
    ) -> dict[str, float | int | None]:
        stmt = select(PredictionRecord).where(
            PredictionRecord.user_id == user_id,
            PredictionRecord.actual_close.is_not(None),
        )

        if symbol:
            stmt = stmt.where(PredictionRecord.symbol == symbol.upper())

        records = list(self.session.scalars(stmt).all())
        if not records:
            return {
                "evaluated_predictions": 0,
                "mae": None,
                "mape_pct": None,
                "directional_accuracy_pct": None,
            }

        errors = [
            record.absolute_error
            for record in records
            if record.absolute_error is not None
        ]
        percentage_errors = [
            record.percentage_error
            for record in records
            if record.percentage_error is not None
        ]
        directions = [
            record.direction_correct
            for record in records
            if record.direction_correct is not None
        ]

        return {
            "evaluated_predictions": len(records),
            "mae": round(sum(errors) / len(errors), 6) if errors else None,
            "mape_pct": round(
                sum(percentage_errors) / len(percentage_errors), 6
            ) if percentage_errors else None,
            "directional_accuracy_pct": round(
                sum(bool(value) for value in directions) / len(directions) * 100,
                6,
            ) if directions else None,
        }
