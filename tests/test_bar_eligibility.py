from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.db.models import Notification
from app.services.alerts import AlertService
from app.services.bar_eligibility import IST, max_eligible_bar_date
from app.services.wallet import WalletService
from tests.test_alerts import _rule, _user
from tests.test_wallet import _bar

TODAY = date(2026, 11, 4)
BEFORE_SETTLE = datetime(2026, 11, 4, 13, 30, tzinfo=IST)   # 1:30pm IST, session open
AFTER_SETTLE = datetime(2026, 11, 4, 16, 30, tzinfo=IST)    # 4:30pm IST, settled


def test_future_date_never_eligible():
    assert max_eligible_bar_date(BEFORE_SETTLE) == date(2026, 11, 3)
    assert max_eligible_bar_date(AFTER_SETTLE) == date(2026, 11, 4)


def test_naive_datetime_treated_as_ist():
    naive = datetime(2026, 11, 4, 17, 0)
    assert max_eligible_bar_date(naive) == date(2026, 11, 4)


def test_wallet_ignores_future_dated_bar(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 11, 3), 1000)
    _bar(session, "RELIANCE", date(2026, 11, 10), 5000)  # future-dated garbage
    service = WalletService(session, now=BEFORE_SETTLE)
    order = service.place_order(user_id=user.id, symbol="RELIANCE", side="buy", quantity=1)
    assert order.status == "filled"
    assert order.fill_price == Decimal("1000.00")  # not the future 5000
    assert order.fill_bar_date == date(2026, 11, 3)


def test_wallet_ignores_unsettled_same_day_bar(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 11, 3), 1000)
    _bar(session, "RELIANCE", date(2026, 11, 4), 1200)  # today, session still open
    service = WalletService(session, now=BEFORE_SETTLE)
    order = service.place_order(user_id=user.id, symbol="RELIANCE", side="buy", quantity=1)
    assert order.fill_price == Decimal("1000.00")
    assert order.fill_bar_date == date(2026, 11, 3)


def test_wallet_uses_same_day_bar_after_settle(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 11, 3), 1000)
    _bar(session, "RELIANCE", date(2026, 11, 4), 1200)
    service = WalletService(session, now=AFTER_SETTLE)
    order = service.place_order(user_id=user.id, symbol="RELIANCE", side="buy", quantity=1)
    assert order.fill_price == Decimal("1200.00")
    assert order.fill_bar_date == date(2026, 11, 4)


def test_staleness_horizon_ignores_future_bars(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 11, 3), 1000)
    _bar(session, "TCS", date(2026, 11, 3), 2000)
    _bar(session, "TCS", date(2026, 11, 10), 9999)  # future-dated
    service = WalletService(session, now=BEFORE_SETTLE)
    order = service.place_order(user_id=user.id, symbol="RELIANCE", side="buy", quantity=1)
    # horizon must be 2026-11-03 (not the future bar), so RELIANCE is not stale
    assert order.status == "filled"


def test_alerts_ignore_future_and_unsettled_bars(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="above", target="1500")
    _bar(session, "RELIANCE", date(2026, 11, 3), 1400)
    _bar(session, "RELIANCE", date(2026, 11, 4), 1600)  # today, unsettled
    service = AlertService(session, now=BEFORE_SETTLE)
    assert service.evaluate_symbol("RELIANCE") == 0  # lone eligible bar: no crossing
    _bar(session, "RELIANCE", date(2026, 11, 10), 9000)  # future-dated
    assert service.evaluate_symbol("RELIANCE") == 0
    assert session.query(Notification).count() == 0


def test_alerts_use_settled_same_day_bar(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="above", target="1500")
    _bar(session, "RELIANCE", date(2026, 11, 3), 1400)
    _bar(session, "RELIANCE", date(2026, 11, 4), 1600)
    service = AlertService(session, now=AFTER_SETTLE)
    assert service.evaluate_symbol("RELIANCE") == 1


def test_snapshot_holders_records_and_dedupes(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 11, 3), 1000)
    service = WalletService(session, now=AFTER_SETTLE)
    service.place_order(user_id=user.id, symbol="RELIANCE", side="buy", quantity=2)
    from app.db.models import PaperEquitySnapshot

    before = session.query(PaperEquitySnapshot).count()
    _bar(session, "RELIANCE", date(2026, 11, 4), 1100)
    assert service.snapshot_holders("RELIANCE") == 1
    assert service.snapshot_holders("RELIANCE") == 0  # same bar date: deduped
    snaps = session.query(PaperEquitySnapshot).order_by(PaperEquitySnapshot.at).all()
    assert len(snaps) == before + 1
    latest = snaps[-1]
    assert latest.as_of == date(2026, 11, 4)
    # cash 998000 + 2 shares at 1100 = 1,000,200
    assert latest.equity == Decimal("1000200.00")


def test_snapshot_holders_ignores_unsettled_bar(session_factory):
    session = session_factory()
    user = _user(session)
    _bar(session, "RELIANCE", date(2026, 11, 3), 1000)
    service = WalletService(session, now=BEFORE_SETTLE)
    service.place_order(user_id=user.id, symbol="RELIANCE", side="buy", quantity=2)
    _bar(session, "RELIANCE", date(2026, 11, 4), 1100)  # unsettled today
    # fill already snapshotted as_of 11-03; the unsettled bar adds nothing
    assert service.snapshot_holders("RELIANCE") == 0
    from app.db.models import PaperEquitySnapshot

    latest = session.query(PaperEquitySnapshot).order_by(PaperEquitySnapshot.at.desc()).first()
    assert latest.as_of == date(2026, 11, 3)
