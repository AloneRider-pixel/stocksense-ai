from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MarketBarRecord, PredictionRecord, User, WatchlistItem


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
                "baseline_mae": None,
                "baseline_directional_accuracy_pct": None,
                "improvement_vs_persistence_pct": None,
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

        model_mae = round(sum(errors) / len(errors), 6) if errors else None

        # Last-close persistence baseline: "next close = close on the
        # prediction date". Directional baseline is always-up, matching the
        # public accuracy methodology.
        baseline_closes = self.baseline_closes_for(records)
        base_pairs = [
            (baseline_closes[(r.symbol, r.prediction_date)], float(r.actual_close))
            for r in records
            if (r.symbol, r.prediction_date) in baseline_closes
            and r.actual_close is not None
        ]
        baseline_mae = (
            round(sum(abs(b - a) for b, a in base_pairs) / len(base_pairs), 6)
            if base_pairs
            else None
        )
        baseline_up = [a >= b for b, a in base_pairs]
        improvement = None
        if baseline_mae and model_mae is not None:
            improvement = round((baseline_mae - model_mae) / baseline_mae * 100, 4)

        return {
            "evaluated_predictions": len(records),
            "mae": model_mae,
            "mape_pct": round(
                sum(percentage_errors) / len(percentage_errors), 6
            ) if percentage_errors else None,
            "directional_accuracy_pct": round(
                sum(bool(value) for value in directions) / len(directions) * 100,
                6,
            ) if directions else None,
            "baseline_mae": baseline_mae,
            "baseline_directional_accuracy_pct": (
                round(sum(baseline_up) / len(baseline_up) * 100, 6)
                if baseline_up
                else None
            ),
            "improvement_vs_persistence_pct": improvement,
        }

    def baseline_closes_for(
        self, records: list[PredictionRecord]
    ) -> dict[tuple[str, date], float]:
        """Close on each record's prediction_date (persistence baseline)."""
        closes: dict[tuple[str, date], float] = {}
        for rec in records:
            key = (rec.symbol, rec.prediction_date)
            if key in closes:
                continue
            close = self.session.scalar(
                select(MarketBarRecord.close).where(
                    MarketBarRecord.symbol == rec.symbol,
                    MarketBarRecord.date == rec.prediction_date,
                )
            )
            if close is not None:
                closes[key] = float(close)
        return closes

    def public_accuracy(self, symbol: str | None = None) -> list[dict[str, object]]:
        """Anonymized per-symbol accuracy of reconciled predictions.

        Counts only predictions already scored against a realized close and
        compares each one to a last-close persistence baseline (the close on
        the prediction date), so the model must beat "tomorrow = today" to
        show value.
        """
        stmt = select(PredictionRecord).where(
            PredictionRecord.actual_close.is_not(None)
        )
        if symbol:
            stmt = stmt.where(PredictionRecord.symbol == symbol.upper())
        records = list(self.session.scalars(stmt).all())
        if not records:
            return []

        baseline_closes: dict[tuple[str, date], float] = {}
        for rec in records:
            key = (rec.symbol, rec.prediction_date)
            if key in baseline_closes:
                continue
            close = self.session.scalar(
                select(MarketBarRecord.close).where(
                    MarketBarRecord.symbol == rec.symbol,
                    MarketBarRecord.date == rec.prediction_date,
                )
            )
            if close is not None:
                baseline_closes[key] = float(close)

        grouped: dict[str, list[PredictionRecord]] = {}
        for rec in records:
            grouped.setdefault(rec.symbol, []).append(rec)

        summaries: list[dict[str, object]] = []
        for sym in sorted(grouped):
            rows = grouped[sym]
            errors = [r.absolute_error for r in rows if r.absolute_error is not None]
            pct_errors = [
                r.percentage_error for r in rows if r.percentage_error is not None
            ]
            directions = [
                r.direction_correct for r in rows if r.direction_correct is not None
            ]
            baseline_up = [
                float(r.actual_close) >= baseline_closes[(r.symbol, r.prediction_date)]
                for r in rows
                if (r.symbol, r.prediction_date) in baseline_closes and r.actual_close
            ]
            base_pairs = [
                (baseline_closes[(r.symbol, r.prediction_date)], float(r.actual_close))
                for r in rows
                if (r.symbol, r.prediction_date) in baseline_closes and r.actual_close
            ]
            baseline_errors = [abs(b - a) for b, a in base_pairs]
            baseline_pct = [abs(b - a) / a * 100 for b, a in base_pairs]

            model_mae = sum(errors) / len(errors) if errors else None
            baseline_mae = (
                sum(baseline_errors) / len(baseline_errors) if baseline_errors else None
            )
            improvement = None
            if baseline_mae and model_mae is not None:
                improvement = round((baseline_mae - model_mae) / baseline_mae * 100, 4)

            summaries.append(
                {
                    "symbol": sym,
                    "evaluated_predictions": len(rows),
                    "realized_return_avg_pct": (
                        round(
                            sum(
                                (float(r.actual_close) - baseline_closes[(r.symbol, r.prediction_date)])
                                / baseline_closes[(r.symbol, r.prediction_date)]
                                * 100
                                for r in rows
                                if (r.symbol, r.prediction_date) in baseline_closes and r.actual_close
                            )
                            / len(base_pairs),
                            4,
                        )
                        if base_pairs
                        else None
                    ),
                    "first_prediction_date": min(
                        r.prediction_date for r in rows
                    ).isoformat(),
                    "last_prediction_date": max(
                        r.prediction_date for r in rows
                    ).isoformat(),
                    "mae": round(model_mae, 4) if model_mae is not None else None,
                    "mape_pct": (
                        round(sum(pct_errors) / len(pct_errors), 4)
                        if pct_errors
                        else None
                    ),
                    "directional_accuracy_pct": (
                        round(
                            sum(bool(v) for v in directions) / len(directions) * 100,
                            4,
                        )
                        if directions
                        else None
                    ),
                    "baseline_mae": (
                        round(baseline_mae, 4) if baseline_mae is not None else None
                    ),
                    "baseline_directional_accuracy_pct": (
                        round(sum(baseline_up) / len(baseline_up) * 100, 4)
                        if baseline_up
                        else None
                    ),
                    "baseline_mape_pct": (
                        round(sum(baseline_pct) / len(baseline_pct), 4)
                        if baseline_pct
                        else None
                    ),
                    "improvement_vs_persistence_pct": improvement,
                }
            )
        return summaries


    def scored_records(self, symbol: str | None = None) -> list[PredictionRecord]:
        """All predictions already reconciled against a realized close."""
        stmt = select(PredictionRecord).where(
            PredictionRecord.actual_close.is_not(None)
        )
        if symbol:
            stmt = stmt.where(PredictionRecord.symbol == symbol.upper())
        return list(self.session.scalars(stmt).all())

    def index_benchmark_for(
        self,
        records: list[PredictionRecord],
        index_symbol: str,
    ) -> dict[str, object]:
        """Compare scored prediction windows against an index (e.g. NIFTY 50).

        For each evaluated prediction, computes the index's realized return
        over the same window (prediction_date close to actual_date close) and
        the underlying symbol's realized return, then reports how the tracked
        windows did versus the index. Descriptive only: it says nothing about
        what any future return will be.
        """
        index_closes: dict[date, float] = {}

        def index_close(day: date) -> float | None:
            if day not in index_closes:
                close = self.session.scalar(
                    select(MarketBarRecord.close).where(
                        MarketBarRecord.symbol == index_symbol,
                        MarketBarRecord.date == day,
                    )
                )
                index_closes[day] = float(close) if close is not None else None  # type: ignore[assignment]
            return index_closes[day]

        baseline_closes = self.baseline_closes_for(records)
        symbol_returns: list[float] = []
        index_returns: list[float] = []
        outperform = 0
        for rec in records:
            base = baseline_closes.get((rec.symbol, rec.prediction_date))
            if not base or rec.actual_close is None or rec.actual_date is None:
                continue
            idx_start = index_close(rec.prediction_date)
            idx_end = index_close(rec.actual_date)
            if idx_start is None or idx_end is None:
                continue
            symbol_returns.append((float(rec.actual_close) - base) / base * 100)
            index_returns.append((idx_end - idx_start) / idx_start * 100)
            if symbol_returns[-1] > index_returns[-1]:
                outperform += 1

        compared = len(symbol_returns)
        return {
            "symbol": index_symbol,
            "compared_windows": compared,
            "avg_symbol_return_pct": (
                round(sum(symbol_returns) / compared, 4) if compared else None
            ),
            "avg_index_return_pct": (
                round(sum(index_returns) / compared, 4) if compared else None
            ),
            "share_outperforming_index_pct": (
                round(outperform / compared * 100, 4) if compared else None
            ),
        }

    def latest_per_symbol(self) -> list[PredictionRecord]:
        """Most recent stored prediction per symbol, newest first."""
        stmt = select(PredictionRecord).order_by(PredictionRecord.created_at.desc())
        records = list(self.session.scalars(stmt).all())
        seen: set[str] = set()
        latest: list[PredictionRecord] = []
        for record in records:
            if record.symbol in seen:
                continue
            seen.add(record.symbol)
            latest.append(record)
        return latest



class WatchlistRepository:
    def __init__(self, session) -> None:
        self.session = session

    def list_symbols(self, user_id: int) -> list[str]:
        rows = (
            self.session.query(WatchlistItem)
            .filter(WatchlistItem.user_id == user_id)
            .order_by(WatchlistItem.created_at.asc())
            .all()
        )
        return [row.symbol for row in rows]

    def add(self, user_id: int, symbol: str) -> bool:
        """Insert the symbol; returns False when it was already present."""
        existing = (
            self.session.query(WatchlistItem)
            .filter(
                WatchlistItem.user_id == user_id,
                WatchlistItem.symbol == symbol,
            )
            .first()
        )
        if existing is not None:
            return False
        self.session.add(WatchlistItem(user_id=user_id, symbol=symbol))
        self.session.commit()
        return True

    def remove(self, user_id: int, symbol: str) -> bool:
        deleted = (
            self.session.query(WatchlistItem)
            .filter(
                WatchlistItem.user_id == user_id,
                WatchlistItem.symbol == symbol,
            )
            .delete()
        )
        self.session.commit()
        return deleted > 0
