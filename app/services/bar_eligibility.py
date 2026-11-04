"""When a stored daily bar qualifies as a completed close.

Paper fills, wallet valuation and price alerts may only use bars that
are complete and knowable:

- Never future-dated: a bar dated after today (Asia/Kolkata) is data
  that cannot exist yet and is ignored everywhere.
- Never mid-session: a bar dated today only qualifies once our
  settlement buffer has passed (16:00 IST). The NSE equity continuous
  session runs 09:15-15:30 IST per the exchange's published market
  timings (nseindia.com/static/market-data/market-timings); 16:00 IST
  is our own conservative buffer for provider publication lag, not an
  official NSE settlement guarantee. Before the buffer, a same-day bar
  is treated as an incomplete session, not a close.

Weekends and trading holidays need no calendar here: eligibility is a
date ceiling, so on a closed day the latest qualifying bar is simply
the previous session's. Clock correctness matters: the check trusts
the server clock (Asia/Kolkata); a wrong clock shifts the boundary, so
the clock is injectable for tests and ops should keep NTP honest.

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
