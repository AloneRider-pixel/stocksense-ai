"""Nifty 500 scanner endpoints (relative strength, industries, breakouts, explain, rule backtest)."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.rate_limit_dependency import enforce_rate_limit
from app.auth.dependencies import get_current_user
from app.db.database import get_session
from app.core.config import settings
from app.db.models import ScannerBar, ScannerRun, ScannerSignal
from app.services import scanner as sc

def require_scanner_enabled() -> None:
    """Every scanner endpoint is off unless explicitly enabled (data-provider terms unverified)."""
    if not settings.scanner_enabled:
        raise HTTPException(status_code=403, detail={"code": "SCANNER_DISABLED", "message": "The scanner is disabled on this server."})


router = APIRouter(prefix="/scanner", tags=["scanner"], dependencies=[Depends(require_scanner_enabled)])

DISCLAIMER = (
    "Research and education only. Not investment advice; not a SEBI-registered research analyst. "
    "Daily bars from Yahoo Finance via yfinance may be delayed or incomplete. Universe: NSE Indices "
    "Nifty 500 constituent list snapshot; 'industry' is NSE's industry classification."
)
_CACHE_TTL = 600.0
_cache: dict[str, object] = {"data": None, "expires": 0.0, "excluded": {}}
_ingest: dict = {"running": False, "last": None, "last_started": None}
_load_lock = threading.Lock()


def _load() -> tuple[dict[str, pd.DataFrame], pd.DataFrame | None]:
    with _load_lock:  # concurrent first requests share one database read
        return _load_locked()


def _load_locked() -> tuple[dict[str, pd.DataFrame], pd.DataFrame | None]:
    now = time.time()
    if _cache["data"] is not None and now < float(_cache["expires"]):
        return _cache["data"]  # type: ignore[return-value]
    session = get_session()
    try:
        rows = session.execute(
            select(ScannerBar.symbol, ScannerBar.date, ScannerBar.high, ScannerBar.low, ScannerBar.close, ScannerBar.volume)
            .order_by(ScannerBar.symbol, ScannerBar.date)
        ).all()
    finally:
        session.close()
    frame = pd.DataFrame(rows, columns=["symbol", "date", "high", "low", "close", "volume"])
    bars = {s: g.drop(columns="symbol").reset_index(drop=True) for s, g in frame.groupby("symbol")} if len(frame) else {}
    bench = bars.pop(sc.BENCHMARK, None)
    bars, excluded = sc.quality_filter(bars, bench)
    _cache["excluded"] = excluded
    _cache["data"], _cache["expires"] = (bars, bench), now + _CACHE_TTL
    return bars, bench


def _ready() -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, sc.UniverseEntry]]:
    bars, bench = _load()
    if bench is None or not bars:
        raise HTTPException(status_code=503, detail={"code": "SCANNER_DATA_NOT_LOADED", "message": "Scanner data has not been loaded yet. Start the data load and try again in a few minutes."})
    if not sc.universe_available():
        raise HTTPException(status_code=503, detail={"code": "SCANNER_UNIVERSE_MISSING", "message": "The Nifty 500 list has not been loaded on this server."})
    return bars, bench, {e.symbol: e for e in sc.load_universe()}


def log_current_signals(observed_at: datetime | None = None, live: bool = True) -> int:
    """Record one immutable observation run and the signals seen in it.

    A run is "forward" only if it is live and its bar date is the latest completed
    session at observed_at (IST); entry is then the first session strictly after
    observed_at. Backfilled, recomputed (live=False) or stale-bar runs are stored as
    "retrospective" and never count toward the headline. A bar date that already has a
    run is skipped, so nothing is re-observed or edited.
    """
    observed_at = observed_at or datetime.now(timezone.utc)
    bars, bench = _load()
    if bench is None or not bars or not sc.universe_available():
        return 0
    universe = {e.symbol: e for e in sc.load_universe()}
    as_of = pd.to_datetime(bench["date"].iloc[-1]).date()
    session = get_session()
    try:
        last = session.scalar(select(ScannerRun).order_by(ScannerRun.as_of.desc()).limit(1))
        if last is not None and last.as_of >= as_of:
            return 0
        rs, bo = sc.RSParams(), sc.BreakoutParams()
        origin, reason = sc.classify_run(observed_at, as_of, live)
        signals = sc.current_signals(bars, bench, universe, rs, bo)
        run = ScannerRun(
            as_of=as_of,
            observed_at=observed_at,
            origin=origin,
            origin_reason=reason,
            entry_not_before=(sc.entry_not_before(observed_at) if origin == "forward" else sc._next_weekday(as_of)),
            formula_version=sc.FORMULA_VERSION,
            config=json.dumps({"rs": {"windows": rs.windows, "rotation_lookback_days": rs.rotation_lookback_days},
                               "breakout": bo.__dict__, "max_daily_move": sc.MAX_DAILY_MOVE, "data_source": sc.DATA_SOURCE}),
            excluded=json.dumps(_cache["excluded"]),
            universe_count=len(universe),
            ranked_count=len(sc.relative_strength(bars, bench, universe, rs)),
        )
        session.add(run)
        session.flush()
        for sig in signals:
            session.add(ScannerSignal(run_id=run.id, source_bar_date=as_of, symbol=sig["symbol"], kind=sig["kind"],
                                      close=float(sig["close"]), inputs=json.dumps(sig["inputs"])))
        session.commit()
        return len(signals)
    finally:
        session.close()


@router.get("/coverage", dependencies=[Depends(enforce_rate_limit)])
def coverage(current_user=Depends(get_current_user)) -> dict[str, object]:
    bars, bench = _load()
    universe = sc.load_universe() if sc.universe_available() else []
    excluded = _cache["excluded"]
    usable = sum(1 for df in bars.values() if len(df) >= 253)
    session = get_session()
    try:
        total_rows = session.scalar(select(func.count()).select_from(ScannerBar)) or 0
    finally:
        session.close()
    return {
        "universe_size": len(universe),
        "symbols_with_data": len(bars),
        "symbols_with_12m_history": usable,
        "benchmark_loaded": bench is not None,
        "stored_rows": total_rows,
        "as_of": str(bench["date"].iloc[-1])[:10] if bench is not None and len(bench) else None,
        "excluded_by_quality_check": len(excluded),  # type: ignore[arg-type]
        "excluded_examples": [{"symbol": k, "reason": v} for k, v in list(excluded.items())[:8]],  # type: ignore[union-attr]
        "refresh_enabled": settings.scanner_refresh_enabled,
        "loading": _ingest["running"],
        "last_load": _ingest["last"],
        "disclaimer": DISCLAIMER,
    }


@router.post("/refresh", dependencies=[Depends(enforce_rate_limit)])
def refresh(current_user=Depends(get_current_user)) -> dict[str, object]:
    """Start a background load of the Nifty 500 bars. Off unless SCANNER_REFRESH_ENABLED, one at a time, with a cooldown."""
    if not settings.scanner_refresh_enabled:
        raise HTTPException(status_code=403, detail={"code": "SCANNER_REFRESH_DISABLED", "message": "Data refresh is disabled on this server."})
    if _ingest["running"]:
        return {"status": "already_running"}
    started = _ingest["last_started"]
    cooldown = timedelta(minutes=settings.scanner_refresh_cooldown_minutes)
    if started is not None and datetime.now(timezone.utc) - started < cooldown:
        raise HTTPException(status_code=429, detail={"code": "SCANNER_REFRESH_COOLDOWN", "message": "Data was refreshed recently; try again later."})
    _ingest["running"] = True
    _ingest["last_started"] = datetime.now(timezone.utc)

    def work() -> None:
        from app.market_data.scanner_ingest import ingest_universe

        try:
            _ingest["last"] = ingest_universe()
            _cache["expires"] = 0.0
            log_current_signals()
        except Exception as exc:  # surfaced via /coverage
            _ingest["last"] = {"error": str(exc)}
        finally:
            _cache["expires"] = 0.0
            _ingest["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return {"status": "started"}


@router.get("/rs", dependencies=[Depends(enforce_rate_limit)])
def rs_ranking(
    industry: str | None = Query(default=None),
    min_rating: int = Query(default=1, ge=1, le=99),
    limit: int = Query(default=100, ge=1, le=500),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    bars, bench, universe = _ready()
    params = sc.RSParams()
    rows = sc.relative_strength(bars, bench, universe, params)
    ranked = len(rows)
    rows = [r for r in rows if r["rs_rating"] >= min_rating and (industry is None or r["industry"] == industry)]
    return {
        "results": rows[:limit],
        "ranked": ranked,
        "universe": len(universe),
        "as_of": str(bench["date"].iloc[-1])[:10],
        "method": "Weighted excess return vs NIFTY 50 over " + ", ".join(f"{w}d x{wt:g}" for w, wt in params.windows)
        + ", converted to a 1-99 percentile among ranked stocks. StockSense's own formula.",
        "disclaimer": DISCLAIMER,
    }


@router.get("/industries", dependencies=[Depends(enforce_rate_limit)])
def industries(current_user=Depends(get_current_user)) -> dict[str, object]:
    bars, bench, universe = _ready()
    params = sc.RSParams()
    return {
        "results": sc.industry_rotation(bars, bench, universe, params),
        "method": f"Median RS rating of each industry's ranked stocks now vs {params.rotation_lookback_days} trading days ago "
        "(industries with fewer than 3 ranked stocks omitted).",
        "as_of": str(bench["date"].iloc[-1])[:10],
        "disclaimer": DISCLAIMER,
    }


@router.get("/breadth", dependencies=[Depends(enforce_rate_limit)])
def market_breadth(current_user=Depends(get_current_user)) -> dict[str, object]:
    bars, bench, _ = _ready()
    return {**sc.breadth(bars), "universe_loaded": len(bars), "as_of": str(bench["date"].iloc[-1])[:10], "disclaimer": DISCLAIMER}


@router.get("/breakouts", dependencies=[Depends(enforce_rate_limit)])
def breakout_scan(
    lookback_days: int = Query(default=55, ge=10, le=250),
    min_rel_volume: float = Query(default=1.5, ge=0, le=20),
    max_pct_below_52w_high: float | None = Query(default=None, ge=0, le=100),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    bars, bench, universe = _ready()
    params = sc.BreakoutParams(lookback_days, min_rel_volume, max_pct_below_52w_high)
    return {
        "results": sc.breakouts(bars, universe, params),
        "params": params.__dict__,
        "method": f"Latest close above the highest high of the prior {lookback_days} sessions, volume at least "
        f"{min_rel_volume:g}x its prior 20-session average.",
        "as_of": str(bench["date"].iloc[-1])[:10],
        "disclaimer": DISCLAIMER,
    }


@router.get("/changes", dependencies=[Depends(enforce_rate_limit)])
def what_changed(current_user=Depends(get_current_user)) -> dict[str, object]:
    bars, bench, universe = _ready()
    return {**sc.changes(bars, bench, universe), "as_of": str(bench["date"].iloc[-1])[:10], "disclaimer": DISCLAIMER}


@router.get("/scorecard", dependencies=[Depends(enforce_rate_limit)])
def scorecard(current_user=Depends(get_current_user)) -> dict[str, object]:
    """Record of logged signals at 5/20/60 trading days after entry vs NIFTY 50. Signed-in only.

    Only FORWARD runs count toward the headline. Retrospective runs are listed separately.
    Entry is the next session's close after the signal bar.
    """
    bars, bench, _ = _ready()
    session = get_session()
    try:
        runs = {r.id: r for r in session.scalars(select(ScannerRun)).all()}
        rows = session.execute(
            select(ScannerSignal.run_id, ScannerSignal.source_bar_date, ScannerSignal.symbol, ScannerSignal.kind, ScannerSignal.inputs)
            .order_by(ScannerSignal.source_bar_date.desc())
        ).all()
    finally:
        session.close()
    scored, summary = [], {}
    for run_id, d, symbol, kind, inputs in rows:
        run = runs[run_id]
        df = bars.get(symbol)
        res = sc.score_signal(d.isoformat(), df, bench, entry_floor=run.entry_not_before.isoformat()) if df is not None else {"d5": None, "d20": None, "d60": None}
        scored.append({
            "source_bar_date": d.isoformat(), "observed_at": run.observed_at.isoformat(), "symbol": symbol, "kind": kind,
            "origin": run.origin, "origin_reason": run.origin_reason, "entry_not_before": run.entry_not_before.isoformat(), "formula_version": run.formula_version,
            "status": "current" if run.formula_version == sc.FORMULA_VERSION else "superseded formula " + run.formula_version,
            "inputs": json.loads(inputs), **res,
        })
    for kind in {r["kind"] for r in scored}:
        for h in ("d5", "d20", "d60"):
            vals = [r[h]["vs_nifty_pct"] for r in scored if r["kind"] == kind and r["origin"] == "forward" and r["status"] == "current" and r[h]]
            summary.setdefault(kind, {})[h] = (
                {"scored": len(vals), "beat_nifty": sum(v > 0 for v in vals), "median_vs_nifty_pct": round(float(sorted(vals)[len(vals) // 2]), 2)} if vals else {"scored": 0}
            )
    return {
        "forward_signals": sum(1 for r in scored if r["origin"] == "forward"),
        "retrospective_signals": sum(1 for r in scored if r["origin"] == "retrospective"),
        "runs": [{"observed_at": r.observed_at.isoformat(), "as_of": r.as_of.isoformat(), "origin": r.origin, "origin_reason": r.origin_reason, "entry_not_before": r.entry_not_before.isoformat(), "formula_version": r.formula_version,
                  "excluded_count": len(json.loads(r.excluded)), "universe_count": r.universe_count, "ranked_count": r.ranked_count}
                 for r in sorted(runs.values(), key=lambda r: r.observed_at, reverse=True)],
        "summary_forward_only": summary,
        "recent": scored[:100],
        "method": "Each live refresh stores an immutable run (observed time UTC, bar date, rules version, config, data exclusions) and its signals with raw input values. A run is forward only if it was live and its bar date was the latest completed session when observed (IST); entry is the close of the first session strictly after the observation. Imported, backfilled, recomputed, delayed or stale-bar runs are retrospective and kept out of the headline. Horizons are 5/20/60 trading days from entry, vs NIFTY 50 (weekends handled, exchange holidays not modelled). Nothing is edited or deleted; misses stay. Runs from a changed rules version are labelled superseded, not rewritten.",
        "disclaimer": DISCLAIMER,
    }


@router.get("/stock/{symbol}", dependencies=[Depends(enforce_rate_limit)])
def explain(symbol: str, current_user=Depends(get_current_user)) -> dict[str, object]:
    bars, bench, universe = _ready()
    result = sc.explain_stock(symbol.strip().upper(), bars, bench, universe)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_ENOUGH_DATA", "message": "Not enough stored history for this symbol."})
    return result


class BacktestRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    entry: str = "breakout"
    entry_n: int = Field(default=55, ge=2, le=400)
    entry_fast: int = Field(default=20, ge=2, le=400)
    entry_threshold_pct: float = Field(default=10.0, ge=-50, le=200)
    exit: str = "below_sma"
    exit_n: int = Field(default=20, ge=2, le=400)
    exit_stop_pct: float = Field(default=10.0, ge=0.5, le=50)
    cost_bps: float = Field(default=10.0, ge=0, le=500)
    slippage_bps: float = Field(default=10.0, ge=0, le=500)


@router.post("/backtest", dependencies=[Depends(enforce_rate_limit)])
def rule_backtest(req: BacktestRequest, current_user=Depends(get_current_user)) -> dict[str, object]:
    bars, bench, _ = _ready()
    df = bars.get(req.symbol.strip().upper())
    if df is None:
        raise HTTPException(status_code=404, detail={"code": "UNKNOWN_SYMBOL", "message": "Symbol is not in the loaded scanner universe."})
    rule = sc.RuleSpec(**req.model_dump(exclude={"symbol"}))
    try:
        result = sc.backtest_rule(df, bench, rule)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "INVALID_RULE", "message": str(exc)}) from exc
    result["symbol"] = req.symbol.strip().upper()
    result["disclaimer"] = DISCLAIMER
    return result
