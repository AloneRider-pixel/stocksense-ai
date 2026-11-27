from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.db.models import MarketBarRecord, PredictionRecord
from app.db.repository import MarketDataRepository, PredictionRepository, finality_metadata

IST = ZoneInfo("Asia/Kolkata")


def _bar(sym, d, ingested, provider="yfinance"):
    return MarketBarRecord(symbol=sym, date=d, open=1, high=1, low=1, close=1, volume=1,
                           source_provider=provider, ingested_at=ingested)


def _fixture():
    # "Now" is 11:00 IST on 2026-11-26: today's NSE bar is a running session.
    now = datetime(2026, 11, 26, 11, 0, tzinfo=IST)
    # The 25th was captured at 11:00 IST that day (mid-session) and never refetched after the close.
    stale_partial = _bar("RELIANCE", date(2026, 11, 25), datetime(2026, 11, 25, 5, 30, tzinfo=timezone.utc))
    running_today = _bar("RELIANCE", date(2026, 11, 26), datetime(2026, 11, 26, 5, 30, tzinfo=timezone.utc))
    return now, stale_partial, running_today


def test_list_history_excluding_open_session(session_factory):
    now, stale_partial, running_today = _fixture()
    with session_factory() as db:
        db.add_all([stale_partial, running_today])
        db.commit()
        repo = MarketDataRepository(db)
        rows = repo.list_history_excluding_open_session("RELIANCE", now=now)
        assert [r.date for r in rows] == [date(2026, 11, 25)]  # running session gone
        # The stale partial still passes: the read-side rule cannot know it was never refreshed.
        meta = finality_metadata(rows)
        assert meta["latest_bar_date"] == "2026-11-25"
        assert meta["confirmed_final"] is None
        assert meta["source_provider"] == "yfinance"
        assert "Not confirmed final" in meta["note"]
        assert repo.list_history_excluding_open_session("VOD.L", now=now) == []  # unsupported symbol: no rows, no crash


def test_finality_metadata_for_no_rows_is_explicit():
    assert finality_metadata([])["confirmed_final"] is None


def test_prediction_is_not_scored_against_the_running_session(session_factory, monkeypatch):
    import app.market_data.base as base

    real = base.drop_incomplete_bars
    monkeypatch.setattr(base, "drop_incomplete_bars", lambda bars, **kw: real(bars, now=datetime(2026, 11, 26, 11, 0, tzinfo=IST), **{k: v for k, v in kw.items() if k != "now"}))
    with session_factory() as db:
        db.add(_bar("RELIANCE", date(2026, 11, 26), datetime(2026, 11, 26, 5, 30, tzinfo=timezone.utc)))
        db.add(PredictionRecord(symbol="RELIANCE", prediction_date=date(2026, 11, 25), predicted_close=1,
                                expected_change_pct=0, model="m"))
        db.commit()
        assert PredictionRepository(db).evaluate_pending("RELIANCE") == 0
        pred = db.query(PredictionRecord).one()
        assert pred.actual_date is None and pred.actual_close is None


def test_prediction_is_scored_once_the_session_is_over(session_factory, monkeypatch):
    import app.market_data.base as base

    real = base.drop_incomplete_bars
    monkeypatch.setattr(base, "drop_incomplete_bars", lambda bars, **kw: real(bars, now=datetime(2026, 11, 26, 17, 0, tzinfo=IST), **{k: v for k, v in kw.items() if k != "now"}))
    with session_factory() as db:
        db.add(_bar("RELIANCE", date(2026, 11, 26), datetime(2026, 11, 26, 11, 30, tzinfo=timezone.utc)))
        db.add(PredictionRecord(symbol="RELIANCE", prediction_date=date(2026, 11, 25), predicted_close=1,
                                expected_change_pct=0, model="m"))
        db.commit()
        assert PredictionRepository(db).evaluate_pending("RELIANCE") == 1


def test_limit_is_met_even_when_the_open_session_bar_is_dropped(session_factory):
    now = datetime(2026, 11, 26, 11, 0, tzinfo=IST)
    with session_factory() as db:
        for d in range(20, 27):
            db.add(_bar("RELIANCE", date(2026, 11, d), datetime(2026, 11, d, 12, 0, tzinfo=timezone.utc)))
        db.commit()
        rows = MarketDataRepository(db).list_history_excluding_open_session("RELIANCE", limit=3, now=now)
        assert [r.date.day for r in rows] == [23, 24, 25]  # 26th is the open session; still 3 rows


def test_pending_prediction_for_unsupported_symbol_is_reported_unevaluable(session_factory):
    from app.db.models import PredictionRecord

    with session_factory() as db:
        db.add(_bar("VOD.L", date(2026, 11, 20), datetime(2026, 11, 20, tzinfo=timezone.utc)))
        db.add(_bar("VOD.L", date(2026, 11, 21), datetime(2026, 11, 21, tzinfo=timezone.utc)))
        db.add(PredictionRecord(symbol="VOD.L", prediction_date=date(2026, 11, 20), predicted_close=1.0,
                                expected_change_pct=0.0, model="t"))
        db.commit()
        repo = PredictionRepository(db)
        assert repo.evaluate_pending("VOD.L") == 0
        assert repo.last_unevaluable == ["VOD.L"]


def test_evaluation_summary_counts_unsupported_pending_separately_from_scored(session_factory):
    from app.db.models import PredictionRecord

    with session_factory() as db:
        for sym in ("VOD.L", "RELIANCE"):
            db.add(PredictionRecord(user_id=None, symbol=sym, prediction_date=date(2026, 11, 20), predicted_close=1.0,
                                    expected_change_pct=0.0, model="t"))
        db.commit()
        repo = PredictionRepository(db)
        out = repo.unevaluable_pending(user_id=None)
        assert out == {"pending_unevaluable": 1, "pending_unevaluable_symbols": ["VOD.L"]}, out
