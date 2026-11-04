"""Price alert evaluation.

Alert rules fire when the latest stored daily close crosses the rule's
target in the rule's direction, using the previous stored close as the
baseline:

- above: previous close < target <= latest close
- below: previous close > target >= latest close

A crossing needs two consecutive closes; a lone bar never fires a rule.
Creating a rule pins its baseline_bar_date to the symbol's latest stored
bar, so historical prices that are already past the target never fire as
a "new" crossing - only bars newer than the baseline can fire. The
baseline is bookkeeping, not a trigger: last_triggered_bar_date stays
empty until the rule actually fires. A rule never fires twice for the
same bar date, so repeated or retried ingestion for the same day does
not duplicate notifications, and the rules are locked with
SELECT ... FOR UPDATE during evaluation so concurrent ingestions of the
same symbol cannot double-fire either. Firing does not deactivate the
rule: it re-arms for the next crossing on a newer bar.

Evaluation reads stored bars only - it never calls a market data
provider. Delivery goes through the Notifier seam; the default is
LogNotifier (log-only, no email) until external delivery is approved."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AlertRule, MarketBarRecord, Notification
from app.services.bar_eligibility import max_eligible_bar_date
from app.services.notifications import Notifier, get_notifier

ALERT_KIND = "price_alert"


def _recent_closes(session: Session, symbol: str, limit: int = 2, now=None) -> list[tuple]:
    # Only bars eligible as completed closes: never future-dated, never
    # a not-yet-settled same-day bar.
    stmt = (
        select(MarketBarRecord.date, MarketBarRecord.close)
        .where(
            MarketBarRecord.symbol == symbol,
            MarketBarRecord.date <= max_eligible_bar_date(now),
        )
        .order_by(MarketBarRecord.date.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).all())


class AlertService:
    def __init__(self, session: Session, notifier: Notifier | None = None, now=None) -> None:
        self.session = session
        self.notifier = notifier or get_notifier()
        self._now = now

    def _crossed(self, rule: AlertRule, bars: list[tuple]) -> tuple | None:
        """Return the triggering (bar_date, close) or None."""
        if not bars:
            return None
        if len(bars) < 2:
            return None  # a lone bar has no baseline and never fires
        bar_date, close = bars[0]
        close = Decimal(close)
        target = Decimal(rule.target_price)
        prev_close = Decimal(bars[1][1])
        if rule.direction == "above":
            hit = prev_close < target <= close
        else:
            hit = prev_close > target >= close
        if not hit:
            return None
        gate = max(
            (d for d in (rule.baseline_bar_date, rule.last_triggered_bar_date) if d is not None),
            default=None,
        )
        if gate is not None and gate >= bar_date:
            return None
        return bar_date, close

    def evaluate_symbol(self, symbol: str) -> int:
        """Evaluate all active rules for one symbol. Returns triggers fired."""
        stmt = (
            select(AlertRule)
            .where(
                AlertRule.symbol == symbol,
                AlertRule.active.is_(True),
            )
            .with_for_update()
        )
        rules = list(self.session.execute(stmt).scalars().all())
        if not rules:
            return 0
        bars = _recent_closes(self.session, symbol, now=self._now)
        fired = 0
        for rule in rules:
            crossing = self._crossed(rule, bars)
            if crossing is None:
                continue
            bar_date, close = crossing
            rule.last_triggered_bar_date = bar_date
            target_text = f"{Decimal(rule.target_price):,.2f}"
            title = f"{symbol} crossed {rule.direction} {target_text}"
            body = (
                f"{symbol} closed at {close:,.2f} on {bar_date}, crossing "
                f"{rule.direction} your alert target of {target_text}. "
                "This is a simulated alert on stored daily closes, not "
                "investment advice."
            )
            self.session.add(
                Notification(
                    user_id=rule.user_id,
                    kind=ALERT_KIND,
                    title=title,
                    body=body,
                    seen=False,
                )
            )
            self.notifier.send(user_id=rule.user_id, title=title, body=body)
            fired += 1
        if fired:
            self.session.commit()
        return fired


class AlertInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def latest_bar_date(session: Session, symbol: str) -> date | None:
    stmt = (
        select(MarketBarRecord.date)
        .where(MarketBarRecord.symbol == symbol)
        .order_by(MarketBarRecord.date.desc())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def create_rule(
    session: Session, user_id: int, symbol: str, direction: str, target_price: Decimal
) -> AlertRule:
    from app.market_data.symbols import lookup_symbol

    normalized = symbol.strip().upper()
    if direction not in ("above", "below"):
        raise AlertInputError("BAD_DIRECTION", "direction must be 'above' or 'below'")
    if target_price <= 0:
        raise AlertInputError("BAD_TARGET", "target price must be positive")
    if lookup_symbol(normalized) is None:
        raise AlertInputError("UNKNOWN_SYMBOL", f"unknown symbol: {normalized}")
    # Baseline at creation: history already past the target must never
    # fire as a new crossing, so evaluation starts after the latest
    # stored bar. This is not a trigger - last_triggered_bar_date stays
    # empty until the rule actually fires.
    rule = AlertRule(
        user_id=user_id,
        symbol=normalized,
        direction=direction,
        target_price=target_price,
        active=True,
        baseline_bar_date=latest_bar_date(session, normalized),
    )
    session.add(rule)
    session.commit()
    return rule


def list_rules(session: Session, user_id: int) -> list[AlertRule]:
    stmt = (
        select(AlertRule)
        .where(AlertRule.user_id == user_id)
        .order_by(AlertRule.created_at.desc())
    )
    return list(session.execute(stmt).scalars().all())


def deactivate_rule(session: Session, user_id: int, rule_id: int) -> AlertRule:
    rule = session.get(AlertRule, rule_id)
    if rule is None or rule.user_id != user_id:
        raise AlertInputError("NOT_FOUND", "alert rule not found")
    rule.active = False
    session.commit()
    return rule


def list_notifications(session: Session, user_id: int) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(100)
    )
    return list(session.execute(stmt).scalars().all())


def mark_notification_seen(session: Session, user_id: int, notification_id: int) -> Notification:
    note = session.get(Notification, notification_id)
    if note is None or note.user_id != user_id:
        raise AlertInputError("NOT_FOUND", "notification not found")
    note.seen = True
    session.commit()
    return note
