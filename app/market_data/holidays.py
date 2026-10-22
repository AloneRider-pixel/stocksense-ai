"""NSE trading-calendar helpers (Asia/Kolkata).

Static holiday list for 2026 (NSE trading holidays, weekdays only); update
NSE_HOLIDAYS_2026 when the exchange publishes a new circular. Weekends are
always non-trading. Used to label forecast horizons honestly ("next trading
day") rather than pretending every calendar day is a session.
"""

from __future__ import annotations

from datetime import date, timedelta

NSE_HOLIDAYS_2026: frozenset[date] = frozenset(
    date.fromisoformat(d)
    for d in (
        "2026-01-26",  # Republic Day
        "2026-03-03",  # Holi
        "2026-03-26",  # Ram Navami
        "2026-03-31",  # Mahavir Jayanti
        "2026-04-03",  # Good Friday
        "2026-04-14",  # Dr. Ambedkar Jayanti
        "2026-05-01",  # Maharashtra Day
        "2026-05-28",  # Bakri Id (tentative)
        "2026-06-26",  # Muharram (tentative)
        "2026-08-15",  # Independence Day (Saturday; listed for completeness)
        "2026-09-04",  # Id-e-Milad (tentative)
        "2026-10-02",  # Mahatma Gandhi Jayanti
        "2026-10-20",  # Dussehra (tentative)
        "2026-11-08",  # Diwali (Laxmi Pujan; tentative)
        "2026-11-09",  # Diwali (Balipratipada; tentative)
        "2026-11-24",  # Guru Nanak Jayanti (tentative)
        "2026-12-25",  # Christmas
    )
)

MARKET_TIMEZONE = "Asia/Kolkata"


def is_trading_day(day: date) -> bool:
    """True when the NSE is open on `day` (weekday and not a listed holiday)."""
    return day.weekday() < 5 and day not in NSE_HOLIDAYS_2026


def next_trading_day(day: date) -> date:
    """First trading day strictly after `day`."""
    candidate = day + timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate
