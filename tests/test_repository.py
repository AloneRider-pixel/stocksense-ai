from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.repository import PredictionRepository


def test_prediction_repository_round_trip() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = PredictionRepository(session)
        created = repository.add(
            symbol="DEMO",
            predicted_close=101.25,
            expected_change_pct=1.25,
            model="test-model",
            cached=False,
        )

        records = repository.list_recent(symbol="DEMO", limit=10)

    assert created.id == 1
    assert len(records) == 1
    assert records[0].symbol == "DEMO"
    assert records[0].predicted_close == 101.25
