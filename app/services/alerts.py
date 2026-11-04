"""Price alert evaluation.

Alert rules fire when the latest stored daily close crosses the rule's
target in the rule's direction, using the previous stored close as the
baseline:

- above: previous close < target <= latest close
- below: previous close > target >= latest close

With a single stored bar there is no baseline; the rule fires if the
close is already past the target in the direction (above: close >=
target, below: close <= target). A rule never fires twice for the same
bar date (last_triggered_bar_date), so a re-run of ingestion for the
same day does not duplicate notifications. Firing does not deactivate
the rule: it re-arms for the next crossing on a newer bar.

Evaluation reads stored bars only - it never calls a market data
provider. Delivery goes through the Notifier seam; the default is
LogNotifier (log-only, no email) until external delivery is approved."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AlertRule, MarketBarRecord, Notification
from app.services.notifications import Notifier, get_notifier

ALERT_KIND = "price_alert"


def _recent_closes(session: Session, symbol: str, limit: int = 2) -> list[tuple]:
    stmt = (
        select(MarketBarRecord.date, MarketBarRecord.close)
        .where(MarketBarRecord.symbol == symbol)
        .order_by(MarketBarRecord.date.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).all())


class AlertService:
    def __init__(self, session: Session, notifier: Notifier | None = None) -> None:
        self.session = session
        self.notifier = notifier or get_notifier()

    def _crossed(self, rule: AlertRule, bars: list[tuple]) -> tuple | None:
        """Return the triggering (bar_date, close) or None."""
        if not bars:
            return None
        bar_date, close = bars[0]
        close = Decimal(close)
        target = Decimal(rule.target_price)
        if len(bars) >= 2:
            prev_close = Decimal(bars[1][1])
            if rule.direction == "above":
                hit = prev_close < target <= close
            else:
                hit = prev_close > target >= close
        else:
            hit = close >= target if rule.direction == "above" else close <= target
        if not hit:
            return None
        if rule.last_triggered_bar_date is not None and rule.last_triggered_bar_date >= bar_date:
            return None
        return bar_date, close

    def evaluate_symbol(self, symbol: str) -> int:
        """Evaluate all active rules for one symbol. Returns triggers fired."""
        stmt = select(AlertRule).where(
            AlertRule.symbol == symbol,
            AlertRule.active.is_(True),
        )
        rules = list(self.session.execute(stmt).scalars().all())
        if not rules:
            return 0
        bars = _recent_closes(self.session, symbol)
        fired = 0
        for rule in rules:
            crossing = self._crossed(rule, bars)
            if crossing is None:
                continue
            bar_date, close = crossing
            rule.last_triggered_bar_date = bar_date
            title = f"{symbol} crossed {rule.direction} {rule.target_price}"
            body = (
                f"{symbol} closed at {close} on {bar_date}, crossing "
                f"{rule.direction} your alert target of {rule.target_price}. "
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
