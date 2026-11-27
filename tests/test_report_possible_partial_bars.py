from datetime import date, datetime, timezone
from decimal import Decimal

from app.db.models import MarketBarRecord, PaperOrder, PredictionRecord
from scripts.report_possible_partial_bars import find_possible_partial


def _bar(sym, d, ingested):
    return MarketBarRecord(symbol=sym, date=d, open=1, high=1, low=1, close=1, volume=1,
                           source_provider="test", ingested_at=ingested)


def test_report_flags_bars_the_rule_would_refuse_and_linked_rows(session_factory):
    utc = timezone.utc
    with session_factory() as db:
        db.add_all([
            _bar("RELIANCE", date(2026, 11, 26), datetime(2026, 11, 26, 6, 0, tzinfo=utc)),   # 11:30 IST, session open
            _bar("RELIANCE", date(2026, 11, 25), datetime(2026, 11, 26, 6, 0, tzinfo=utc)),   # previous day, fine
            _bar("TCS", date(2026, 11, 26), datetime(2026, 11, 26, 12, 0, tzinfo=utc)),       # 17:30 IST, after margin
            _bar("GOLD", date(2026, 11, 26), datetime(2026, 11, 26, 15, 0, tzinfo=utc)),         # current UTC date
            _bar("GOLD", date(2026, 11, 24), datetime(2026, 11, 26, 15, 0, tzinfo=utc)),
        ])
        db.add(PredictionRecord(symbol="RELIANCE", prediction_date=date(2026, 11, 26), predicted_close=1,
                                expected_change_pct=0, model="m"))
        db.add(PredictionRecord(symbol="GOLD", prediction_date=date(2026, 11, 20), predicted_close=1,
                                expected_change_pct=0, model="m", actual_date=date(2026, 11, 26), actual_close=1))
        db.add(PredictionRecord(symbol="TCS", prediction_date=date(2026, 11, 26), predicted_close=1,
                                expected_change_pct=0, model="m"))
        db.add(PaperOrder(account_id=1, symbol="GOLD", side="buy", quantity=1, status="filled",
                          fill_price=Decimal("1"), fill_bar_date=date(2026, 11, 26)))
        db.commit()
        r = find_possible_partial(db)
    assert r["flagged"] == {"RELIANCE": {date(2026, 11, 26)}, "GOLD": {date(2026, 11, 26)}}
    assert len(r["predictions"]) == 2  # RELIANCE (made on) and GOLD (evaluated against); TCS not flagged
    assert len(r["fills"]) == 1
    assert r["bars_checked"] == 5 and r["naive_ingested_at"] == 5  # sqlite drops tzinfo; counted and treated as UTC
    assert "does NOT mean none affected" in r["limits"]


def test_report_counts_unsupported_symbols_and_still_checks_the_rest(session_factory):
    utc = timezone.utc
    with session_factory() as db:
        db.add_all([
            _bar("VOD.L", date(2026, 11, 26), datetime(2026, 11, 26, 6, 0, tzinfo=utc)),
            _bar("RELIANCE", date(2026, 11, 26), datetime(2026, 11, 26, 6, 0, tzinfo=utc)),
        ])
        db.commit()
        r = find_possible_partial(db)
    assert r["unsupported_symbols"] == ["VOD.L"]
    assert list(r["flagged"]) == ["RELIANCE"]
    assert r["bars_checked"] == 2
