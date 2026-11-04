from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.db.models import AlertRule, MarketBarRecord, Notification, User
from app.services.alerts import AlertService


class RecordingNotifier:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, user_id: int, title: str, body: str) -> None:
        self.sent.append({"user_id": user_id, "title": title, "body": body})


def _user(session) -> User:
    user = User(email="alerter@example.com", password_hash="x", full_name="Alerter")
    session.add(user)
    session.commit()
    return user


def _rule(session, user, symbol="RELIANCE", direction="above", target="2500", active=True):
    rule = AlertRule(
        user_id=user.id,
        symbol=symbol,
        direction=direction,
        target_price=Decimal(target),
        active=active,
    )
    session.add(rule)
    session.commit()
    return rule


def _bars(session, symbol, rows):
    for d, close in rows:
        session.add(
            MarketBarRecord(
                symbol=symbol,
                date=d,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
                source_provider="test",
            )
        )
    session.commit()


def _service(session):
    notifier = RecordingNotifier()
    return AlertService(session, notifier=notifier), notifier


def test_above_crossing_fires(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, target="2500")
    # prev 2450 < 2500 <= close 2510 -> fires
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2510)])
    service, notifier = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 1
    notifications = session.query(Notification).all()
    assert len(notifications) == 1
    assert notifications[0].user_id == user.id
    assert notifications[0].kind == "price_alert"
    assert notifications[0].seen is False
    assert "2510" in notifications[0].body
    assert len(notifier.sent) == 1


def test_above_no_crossing_when_both_sides_above(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, target="2500")
    # prev 2550, close 2600 both above -> no crossing
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2550), (date(2026, 10, 30), 2600)])
    service, notifier = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0
    assert session.query(Notification).count() == 0
    assert notifier.sent == []


def test_above_no_fire_when_close_below_target(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, target="2500")
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2480)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0


def test_below_crossing_fires(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="below", target="2500")
    # prev 2550 > 2500 >= close 2490 -> fires
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2550), (date(2026, 10, 30), 2490)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 1


def test_below_no_crossing_when_both_below(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="below", target="2500")
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2400)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0


def test_single_bar_never_fires(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="above", target="2500")
    # no baseline: a lone bar already past the target must not fire
    _bars(session, "RELIANCE", [(date(2026, 10, 30), 2600)])
    service, notifier = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0
    assert db_count(session) == 0
    assert notifier.sent == []


def test_single_bar_never_fires_below(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="below", target="2500")
    _bars(session, "RELIANCE", [(date(2026, 10, 30), 2400)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0


def db_count(session):
    return session.query(Notification).count()


def test_no_duplicate_fire_for_same_bar(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, target="2500")
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2510)])
    service, notifier = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 1
    assert service.evaluate_symbol("RELIANCE") == 0  # same bar date, deduped
    assert session.query(Notification).count() == 1
    assert len(notifier.sent) == 1


def test_rearm_on_newer_crossing_bar(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, target="2500")
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2510)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 1
    # price dips back below and crosses up again on a newer bar
    _bars(session, "RELIANCE", [(date(2026, 10, 31), 2460), (date(2026, 11, 2), 2520)])
    assert service.evaluate_symbol("RELIANCE") == 1
    assert session.query(Notification).count() == 2


def test_inactive_rule_never_fires(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, target="2500", active=False)
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2510)])
    service, notifier = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0
    assert notifier.sent == []


def test_no_bars_means_no_fire(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, target="2500")
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0


def test_rules_for_other_symbols_untouched(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, symbol="TCS", target="4000")
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2510)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0
    assert session.query(Notification).count() == 0


def test_multiple_users_independent(session_factory):
    session = session_factory()
    user1 = _user(session)
    user2 = User(email="a2@example.com", password_hash="x", full_name="Alerter Two")
    session.add(user2)
    session.commit()
    _rule(session, user1, target="2500")
    _rule(session, user2, target="2600")
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2510)])
    service, notifier = _service(session)
    # user1's 2500 rule fires; user2's 2600 rule does not
    assert service.evaluate_symbol("RELIANCE") == 1
    note = session.query(Notification).one()
    assert note.user_id == user1.id
    assert notifier.sent[0]["user_id"] == user1.id


def test_threshold_equality_above_fires_on_close_equal_target(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="above", target="2500")
    # prev 2450 < 2500 <= close 2500 -> fires (close equal to target counts)
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2500)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 1


def test_threshold_equality_above_prev_equal_target_does_not_fire(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="above", target="2500")
    # prev 2500 is not < target -> no crossing even though close 2510 > target
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2500), (date(2026, 10, 30), 2510)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0


def test_threshold_equality_below_fires_on_close_equal_target(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="below", target="2500")
    # prev 2550 > 2500 >= close 2500 -> fires
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2550), (date(2026, 10, 30), 2500)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 1


def test_threshold_equality_below_prev_equal_target_does_not_fire(session_factory):
    session = session_factory()
    user = _user(session)
    _rule(session, user, direction="below", target="2500")
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2500), (date(2026, 10, 30), 2490)])
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0


def test_rule_created_after_history_does_not_backfill(session_factory):
    session = session_factory()
    user = _user(session)
    # history already past the target before the rule exists
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2600)])
    from app.services.alerts import create_rule

    rule = create_rule(
        session, user_id=user.id, symbol="RELIANCE", direction="above",
        target_price=Decimal("2500"),
    )
    assert rule.last_triggered_bar_date == date(2026, 10, 30)  # baseline at creation
    service, notifier = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0  # no backfilled "crossing"
    assert db_count(session) == 0
    assert notifier.sent == []


def test_rule_created_after_history_fires_only_on_newer_crossing(session_factory):
    session = session_factory()
    user = _user(session)
    _bars(session, "RELIANCE", [(date(2026, 10, 29), 2450), (date(2026, 10, 30), 2600)])
    from app.services.alerts import create_rule

    create_rule(
        session, user_id=user.id, symbol="RELIANCE", direction="above",
        target_price=Decimal("2700"),
    )
    service, _ = _service(session)
    assert service.evaluate_symbol("RELIANCE") == 0
    # newer bars cross the 2700 target -> fires once
    _bars(session, "RELIANCE", [(date(2026, 10, 31), 2650), (date(2026, 11, 2), 2710)])
    assert service.evaluate_symbol("RELIANCE") == 1
    assert db_count(session) == 1


def test_create_rule_validation(session_factory):
    session = session_factory()
    user = _user(session)
    import pytest

    from app.services.alerts import AlertInputError, create_rule

    with pytest.raises(AlertInputError):
        create_rule(session, user_id=user.id, symbol="RELIANCE", direction="up", target_price=Decimal("100"))
    with pytest.raises(AlertInputError):
        create_rule(session, user_id=user.id, symbol="RELIANCE", direction="above", target_price=Decimal("0"))
    with pytest.raises(AlertInputError):
        create_rule(session, user_id=user.id, symbol="NOPE123", direction="above", target_price=Decimal("100"))
