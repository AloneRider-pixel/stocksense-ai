"""When a stored daily bar qualifies as a completed close.

Paper fills, wallet valuation and price alerts may only use bars that
are complete and knowable:

- Never future-dated: a bar dated after today (Asia/Kolkata) is data
  that cannot exist yet and is ignored everywhere.
- Never mid-session: a bar dated today only qualifies once the NSE
  session has settled (after 16:00 IST; NSE closes 15:30 IST). Before
  that, a same-day bar is an incomplete session, not a close.

Charts and prediction history may still display stored same-day bars;
this gate applies only where a bar is treated as a closing price for
money or alerts. The injectable clock keeps the rules testable."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
SESSION_SETTLE = time(16, 0)  # NSE closes 15:30 IST; bars are final only after 16:00 IST


def max_eligible_bar_date(now: datetime | None = None) -> date:
    """Latest bar date allowed to act as a completed close right now."""
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    local = now.astimezone(IST)
    if local.time() >= SESSION_SETTLE:
        return local.date()
    return local.date() - timedelta(days=1)
