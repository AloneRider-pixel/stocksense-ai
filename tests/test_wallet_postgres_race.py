"""Concurrent-order race proof against a real PostgreSQL server.

SQLite ignores SELECT ... FOR UPDATE, so the unit suite cannot prove the
locking. This test runs only when STOCKSENSE_TEST_PG_DSN points at a
scratch Postgres database; it hammers one paper account with concurrent
orders from independent sessions (as real requests would) and asserts
money conservation and idempotent-retry behavior.

Local recipe:
    pip install pgserver
    python -c "import pgserver; print(pgserver.get_server('/tmp/pgs').get_uri())"
    STOCKSENSE_TEST_PG_DSN=<uri> pytest tests/test_wallet_postgres_race.py
"""

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


def _seed(factory):
    from app.auth.service import AuthService
    from app.db.models import MarketBarRecord

    session = factory()
    user = AuthService(session).register(
        email="racer@example.com", password="sup3r-secret", full_name="Racer"
    )
    session.add(
        MarketBarRecord(
            symbol="RELIANCE",
            date=date(2026, 10, 30),
            open=1000, high=1010, low=990, close=1000,
            volume=1000, source_provider="test",
        )
    )
    session.commit()
    user_id = user.id
    session.close()
    return user_id


def test_concurrent_buys_conserve_money(pg_session_factory):
    from app.db.models import PaperAccount, PaperOrder, PaperPosition
    from app.services.wallet import STARTING_CASH, WalletService

    user_id = _seed(pg_session_factory)
    # 12 threads x 150 shares @ 1000 = 1.8L demand per order, 21.6L total vs 10L cash
    threads = 12
    qty, price = 150, Decimal("1000.00")

    def place(_):
        session = pg_session_factory()
        try:
            return WalletService(session).place_order(
                user_id=user_id, symbol="RELIANCE", side="buy", quantity=qty
            ).status
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=threads) as pool:
        statuses = list(pool.map(place, range(threads)))

    session = pg_session_factory()
    account = session.query(PaperAccount).filter(PaperAccount.user_id == user_id).one()
    orders = session.query(PaperOrder).all()
    position = session.query(PaperPosition).one()

    filled = [o for o in orders if o.status == "filled"]
    rejected = [o for o in orders if o.status == "rejected"]
    spent = sum(Decimal(o.fill_price) * o.quantity for o in filled)

    assert len(orders) == threads
    assert set(statuses) <= {"filled", "rejected"}
    assert Decimal(account.cash) >= 0  # never overspent
    assert Decimal(account.cash) + spent == Decimal(STARTING_CASH)  # conservation
    assert position.quantity == sum(o.quantity for o in filled)
    assert all(o.reject_code == "INSUFFICIENT_FUNDS" for o in rejected)
    assert len(filled) <= int(Decimal(STARTING_CASH) // (price * qty))
    session.close()


def test_concurrent_same_client_order_id_returns_one_order(pg_session_factory):
    from app.db.models import PaperOrder
    from app.services.wallet import WalletService

    user_id = _seed(pg_session_factory)
    threads = 6

    def place(_):
        session = pg_session_factory()
        try:
            order = WalletService(session).place_order(
                user_id=user_id,
                symbol="RELIANCE",
                side="buy",
                quantity=5,
                client_order_id="retry-abc-123",
            )
            return order.id, order.status
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=threads) as pool:
        results = list(pool.map(place, range(threads)))

    session = pg_session_factory()
    orders = (
        session.query(PaperOrder)
        .filter(PaperOrder.client_order_id == "retry-abc-123")
        .all()
    )
    # the idempotent retry converged on a single stored order
    assert len(orders) == 1
    assert {order_id for order_id, _ in results} == {orders[0].id}
    assert orders[0].status == "filled"
    assert orders[0].quantity == 5
    session.close()
