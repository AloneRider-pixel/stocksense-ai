from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.auth.service import AuthService
from app.db.models import MarketBarRecord
from app.services.wallet import (
    REJECT_INSUFFICIENT_FUNDS,
    REJECT_INSUFFICIENT_HOLDINGS,
    REJECT_NO_STORED_PRICE,
    REJECT_STALE_PRICE,
    STARTING_CASH,
    WalletInputError,
    WalletService,
)


def _user(session, email="trader@example.com"):
    return AuthService(session).register(
        email=email, password="sup3r-secret", full_name="Test Trader"
    )


def _bar(session, symbol, day, close):
    session.add(
        MarketBarRecord(
            symbol=symbol,
            date=day,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
            source_provider="test",
        )
    )
    session.commit()


def test_buy_fills_at_latest_stored_close(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    _bar(session, "INFY", date(2026, 10, 30), 50.0)

    service = WalletService(session)
    order = service.place_order(user.id, "RELIANCE", "buy", 10)

    assert order.status == "filled"
    assert Decimal(order.fill_price) == Decimal("100.0000")
    assert order.fill_bar_date == date(2026, 10, 30)
    summary = service.summary(user.id)
    assert summary["cash"] == "999000.00"
    assert summary["positions"][0]["symbol"] == "RELIANCE"
    assert summary["positions"][0]["quantity"] == 10
    assert summary["positions"][0]["avg_cost"] == "100.0000"


def test_second_buy_weights_average_cost(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)
    service.place_order(user.id, "RELIANCE", "buy", 10)

    _bar(session, "RELIANCE", date(2026, 10, 31), 120.0)
    service.place_order(user.id, "RELIANCE", "buy", 10)

    summary = service.summary(user.id)
    assert summary["positions"][0]["avg_cost"] == "110.0000"
    assert summary["positions"][0]["quantity"] == 20
    assert summary["cash"] == "997800.00"


def test_sell_realizes_pnl(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)
    service.place_order(user.id, "RELIANCE", "buy", 10)
    _bar(session, "RELIANCE", date(2026, 10, 31), 120.0)
    service.place_order(user.id, "RELIANCE", "buy", 10)
    _bar(session, "RELIANCE", date(2026, 11, 2), 130.0)

    order = service.place_order(user.id, "RELIANCE", "sell", 5)

    assert order.status == "filled"
    summary = service.summary(user.id)
    # realized = (130 - 110) * 5 = 100.00
    assert summary["realized_pnl"] == "100.00"
    assert summary["positions"][0]["quantity"] == 15
    # cash = 1000000 - 1000 - 1200 + 650 = 998450.00
    assert summary["cash"] == "998450.00"


def test_sell_more_than_held_is_rejected_without_state_change(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)
    service.place_order(user.id, "RELIANCE", "buy", 10)

    order = service.place_order(user.id, "RELIANCE", "sell", 11)

    assert order.status == "rejected"
    assert order.reject_code == REJECT_INSUFFICIENT_HOLDINGS
    summary = service.summary(user.id)
    assert summary["cash"] == "999000.00"
    assert summary["positions"][0]["quantity"] == 10


def test_buy_with_insufficient_funds_is_rejected(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)

    order = service.place_order(user.id, "RELIANCE", "buy", 20000)

    assert order.status == "rejected"
    assert order.reject_code == REJECT_INSUFFICIENT_FUNDS
    assert service.summary(user.id)["cash"] == str(STARTING_CASH)


def test_symbol_without_stored_bar_is_rejected(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "INFY", date(2026, 10, 30), 50.0)
    service = WalletService(session)

    order = service.place_order(user.id, "TATAMOTORS", "buy", 1)

    assert order.status == "rejected"
    assert order.reject_code == REJECT_NO_STORED_PRICE


def test_stale_bar_is_rejected(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 28), 100.0)
    _bar(session, "INFY", date(2026, 10, 30), 50.0)
    service = WalletService(session)

    order = service.place_order(user.id, "RELIANCE", "buy", 1)

    assert order.status == "rejected"
    assert order.reject_code == REJECT_STALE_PRICE


@pytest.mark.parametrize("symbol", ["GOLD", "USDINR", "AAPL", "NIFTY50", "NOPE"])
def test_non_nifty50_symbols_are_refused(session_factory, symbol):
    session = session_factory()
    user = _user(session)
    service = WalletService(session)

    with pytest.raises(WalletInputError) as excinfo:
        service.place_order(user.id, symbol, "buy", 1)
    assert excinfo.value.code == "UNSUPPORTED_SYMBOL"


def test_invalid_side_and_quantity_are_refused(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)

    with pytest.raises(WalletInputError):
        service.place_order(user.id, "RELIANCE", "hold", 1)
    with pytest.raises(WalletInputError):
        service.place_order(user.id, "RELIANCE", "buy", 0)
    with pytest.raises(WalletInputError):
        service.place_order(user.id, "RELIANCE", "buy", -3)


def test_client_order_id_makes_retries_idempotent(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)

    first = service.place_order(user.id, "RELIANCE", "buy", 10, client_order_id="abc-1")
    second = service.place_order(user.id, "RELIANCE", "buy", 10, client_order_id="abc-1")

    assert first.id == second.id
    summary = service.summary(user.id)
    assert summary["cash"] == "999000.00"
    assert summary["positions"][0]["quantity"] == 10
    assert len(service.list_orders(user.id)) == 1


def test_wallets_are_isolated_per_user(session_factory):
    session = session_factory()
    user_a = _user(session, "a@example.com")
    user_b = _user(session, "b@example.com")
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)
    service.place_order(user_a.id, "RELIANCE", "buy", 10)

    summary_b = service.summary(user_b.id)
    assert summary_b["cash"] == str(STARTING_CASH)
    assert summary_b["positions"] == []
    assert service.list_orders(user_b.id) == []


def test_reset_restores_starting_state(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)
    service.place_order(user.id, "RELIANCE", "buy", 10)

    service.reset(user.id)

    summary = service.summary(user.id)
    assert summary["cash"] == str(STARTING_CASH)
    assert summary["positions"] == []
    assert summary["realized_pnl"] == "0.00"
    assert service.list_orders(user.id) == []
    assert service.equity_history(user.id) == []


def test_summary_values_positions_at_latest_close(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)
    service.place_order(user.id, "RELIANCE", "buy", 10)
    _bar(session, "RELIANCE", date(2026, 10, 31), 120.0)

    summary = service.summary(user.id)

    position = summary["positions"][0]
    assert position["last_close"] == "120.0000"
    assert position["market_value"] == "1200.00"
    assert position["unrealized_pnl"] == "200.00"
    # equity = 999000 cash + 1200 market value
    assert summary["equity"] == "1000200.00"
    assert summary["as_of"] == "2026-10-31"


def test_fill_records_equity_snapshot(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)
    service.place_order(user.id, "RELIANCE", "buy", 10)

    snapshots = service.equity_history(user.id)
    assert len(snapshots) == 1
    # equity right after the fill = 999000 cash + 1000 market value
    assert Decimal(snapshots[0].equity) == Decimal("1000000.00")
    assert snapshots[0].as_of == date(2026, 10, 30)


def test_client_order_id_race_returns_existing_order(session_factory, monkeypatch):
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)
    service = WalletService(session)
    winner = service.place_order(user.id, "RELIANCE", "buy", 10, client_order_id="race-1")

    real_commit = session.commit
    calls = {"n": 0}

    def flaky_commit():
        calls["n"] += 1
        if calls["n"] == 1:
            raise SAIntegrityError("INSERT INTO paper_orders ...", {}, Exception("dup"))

    monkeypatch.setattr(session, "commit", flaky_commit)

    loser = service.place_order(user.id, "RELIANCE", "buy", 10, client_order_id="race-1")

    assert loser.id == winner.id
    monkeypatch.setattr(session, "commit", real_commit)
    summary = service.summary(user.id)
    assert summary["cash"] == "999000.00"
    assert summary["positions"][0]["quantity"] == 10
