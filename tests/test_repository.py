from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.repository import MarketDataRepository, PredictionRepository


def test_prediction_repository_round_trip() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = PredictionRepository(session)
        created = repository.add(
            user_id=None,
            symbol="DEMO",
            prediction_date=date(2026, 1, 2),
            predicted_close=101.25,
            expected_change_pct=1.25,
            model="test-model",
            cached=False,
        )

        records = repository.list_recent(symbol="DEMO", limit=10)

    assert created.id == 1
    assert len(records) == 1
    assert records[0].symbol == "DEMO"
    assert records[0].prediction_date == date(2026, 1, 2)
    assert records[0].predicted_close == 101.25


def test_pending_prediction_is_evaluated_from_next_market_bar() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        market = MarketDataRepository(session)
        market.upsert_many(
            [
                {
                    "date": date(2026, 1, 2),
                    "symbol": "DEMO",
                    "open": 100,
                    "high": 102,
                    "low": 99,
                    "close": 100,
                    "volume": 1000000,
                    "source_provider": "test",
                },
                {
                    "date": date(2026, 1, 5),
                    "symbol": "DEMO",
                    "open": 100,
                    "high": 104,
                    "low": 99,
                    "close": 103,
                    "volume": 1200000,
                    "source_provider": "test",
                },
            ]
        )

        predictions = PredictionRepository(session)
        predictions.add(
            user_id=7,
            symbol="DEMO",
            prediction_date=date(2026, 1, 2),
            predicted_close=104,
            expected_change_pct=4,
            model="test-model",
            cached=False,
        )

        assert predictions.evaluate_pending("DEMO") == 1
        evaluated = predictions.list_recent(user_id=7, limit=1)[0]

    assert evaluated.actual_date == date(2026, 1, 5)
    assert evaluated.actual_close == 103
    assert evaluated.absolute_error == 1
    assert evaluated.direction_correct is True
