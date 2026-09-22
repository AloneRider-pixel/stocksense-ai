from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.repository import MarketDataRepository


def test_market_data_upsert_and_ordering() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = MarketDataRepository(session)
        inserted = repository.upsert_many(
            [
                {
                    "date": date(2026, 1, 2),
                    "symbol": "TEST",
                    "open": 100,
                    "high": 102,
                    "low": 99,
                    "close": 101,
                    "volume": 1000000,
                    "source_provider": "test",
                },
                {
                    "date": date(2026, 1, 3),
                    "symbol": "TEST",
                    "open": 101,
                    "high": 103,
                    "low": 100,
                    "close": 102,
                    "volume": 1100000,
                    "source_provider": "test",
                },
            ]
        )

        rows = repository.list_history("TEST", limit=10)

    assert inserted == 2
    assert [row.date for row in rows] == [date(2026, 1, 2), date(2026, 1, 3)]
