"""Concurrent alert-evaluation race proof against a real PostgreSQL server.

Two workers ingesting the same symbol at the same time must not
double-notify: the alert rules are locked FOR UPDATE during evaluation.
SQLite ignores FOR UPDATE, so this proof needs a real server; it runs
only when STOCKSENSE_TEST_PG_DSN is set (wired in CI)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DSN = os.environ.get("STOCKSENSE_TEST_PG_DSN")

pytestmark = pytest.mark.skipif(
    not DSN, reason="STOCKSENSE_TEST_PG_DSN not set - needs a scratch Postgres"
)


@pytest.fixture()
def pg_session_factory():
    from app.db.models import Base

    engine = create_engine(DSN)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield factory
    engine.dispose()


def test_concurrent_evaluation_notifies_once_per_rule(pg_session_factory):
    from app.auth.service import AuthService
    from app.db.models import AlertRule, MarketBarRecord, Notification
    from app.services.alerts import AlertService

    session = pg_session_factory()
    user = AuthService(session).register(
        email="alert-racer@example.com", password="sup3r-secret", full_name="Racer"
    )
    for i in range(4):  # several rules racing on the same symbol
        session.add(
            AlertRule(
                user_id=user.id,
                symbol="RELIANCE",
                direction="above",
                target_price=Decimal(str(1400 + i * 200)),
                active=True,
            )
        )
    session.add(
        MarketBarRecord(symbol="RELIANCE", date=date(2026, 10, 29),
                        open=1300, high=1310, low=1290, close=1300, volume=1,
                        source_provider="test")
    )
    session.add(
        MarketBarRecord(symbol="RELIANCE", date=date(2026, 10, 30),
                        open=2000, high=2010, low=1990, close=2000, volume=1,
                        source_provider="test")
    )
    session.commit()
    session.close()

    threads = 8

    def evaluate(_):
        s = pg_session_factory()
        try:
            return AlertService(s).evaluate_symbol("RELIANCE")
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=threads) as pool:
        fired_counts = list(pool.map(evaluate, range(threads)))

    session = pg_session_factory()
    notes = session.query(Notification).all()
    # exactly one notification per rule, however many workers raced
    assert len(notes) == 4
    assert sorted(fired_counts) == [0] * (threads - 1) + [4]
    session.close()
