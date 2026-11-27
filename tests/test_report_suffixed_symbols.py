from datetime import date, datetime, timezone

from app.db.models import MarketBarRecord, WatchlistItem
from scripts.report_suffixed_symbols import find_suffixed_symbols


def test_suffix_report_is_read_only_and_counts_by_table(session_factory):
    with session_factory() as db:
        for day, sym in enumerate(["RELIANCE.NS", "RELIANCE.NS", "RELIANCE", "BRK.B", "VOD.L"], start=1):
            db.add(MarketBarRecord(symbol=sym, date=date(2026, 11, day),
                                   open=1, high=1, low=1, close=1, volume=1, source_provider="t",
                                   ingested_at=datetime(2026, 11, 2, tzinfo=timezone.utc)))
        db.commit()
        before = db.query(MarketBarRecord).count()
        result = find_suffixed_symbols(db)
        assert db.query(MarketBarRecord).count() == before and not db.dirty and not db.new
    bars = result["market_bars"]
    assert bars["suffixed"] == {"RELIANCE.NS": 2, "VOD.L": 1}  # BRK.B is a US share class, plain RELIANCE is fine
    assert bars["bare_form_if_normalized"] == {"RELIANCE.NS": "RELIANCE"}
