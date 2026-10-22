from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.public_rate_limit import enforce_public_rate_limit
from app.api.rate_limit_dependency import enforce_rate_limit
from app.api.schemas import (
    PredictionHistoryItem,
    PredictionRequest,
    PredictionResponse,
)
from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.db.database import get_session
from app.db.repository import MarketDataRepository, PredictionRepository, WatchlistRepository
from app.market_data.factory import get_provider_for_symbol
from app.market_data.symbols import describe_symbol
from app.market_data.yfinance_provider import YFinanceError
from app.services.indicators import compute_indicators
from app.services.screener import screen_universe
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.twelve_data import TwelveDataError
from app.services.cache import PredictionCache
from app.services.predictor import Predictor

router = APIRouter()
predictor = Predictor()
cache = PredictionCache()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "stocksense-ai"}


_overview_cache: dict[str, object] = {"payload": None, "expires": 0.0}
_OVERVIEW_CACHE_TTL_SECONDS = 600.0
_OVERVIEW_EMPTY_CACHE_TTL_SECONDS = 60.0
_OVERVIEW_INGEST_BUDGET = 8


def _latest_bars(repository: MarketDataRepository, symbol: str) -> list:
    return repository.list_history(symbol, limit=2)


@router.get(
    "/public/market-overview",
    dependencies=[Depends(enforce_public_rate_limit)],
)
def public_market_overview() -> dict[str, object]:
    """Landing-page snapshot: latest stored close for each configured symbol.

    Unauthenticated and cached briefly in-process. When a symbol has no stored
    bars (or they are stale), a small per-request budget of provider calls
    backfills it; failures fall back to whatever is stored.
    """
    now = time.time()
    cached = _overview_cache.get("payload")
    if cached is not None and now < float(_overview_cache.get("expires", 0.0)):
        return cached  # type: ignore[return-value]

    session = get_session()
    snapshots: list[dict[str, object]] = []
    ingest_budget = _OVERVIEW_INGEST_BUDGET
    try:
        repository = MarketDataRepository(session)
        provider = None
        for symbol in settings.all_symbol_list:
            stored = _latest_bars(repository, symbol)
            last_ingested = stored[-1].ingested_at if stored else None
            if last_ingested is not None and last_ingested.tzinfo is None:
                # SQLite returns naive datetimes even for timezone-aware columns.
                last_ingested = last_ingested.replace(tzinfo=timezone.utc)
            stale = (
                not stored
                or last_ingested
                < datetime.now(timezone.utc)
                - timedelta(minutes=settings.market_data_refresh_interval_minutes)
            )
            if stale and ingest_budget > 0:
                try:
                    provider = get_provider_for_symbol(symbol)
                    bars = provider.history(symbol, limit=2)
                    if bars:
                        repository.upsert_many(
                            [
                                {
                                    "date": date.fromisoformat(bar.date),
                                    "symbol": bar.symbol,
                                    "open": bar.open,
                                    "high": bar.high,
                                    "low": bar.low,
                                    "close": bar.close,
                                    "volume": bar.volume,
                                    "source_provider": getattr(
                                        provider,
                                        "name",
                                        provider.__class__.__name__,
                                    ),
                                }
                                for bar in bars
                            ]
                        )
                        stored = _latest_bars(repository, symbol)
                    ingest_budget -= 1
                except (TwelveDataError, YFinanceError, ValueError):
                    # A broken provider should not fail every remaining symbol.
                    ingest_budget = 0

            if not stored:
                continue
            latest = stored[-1]
            change_pct = None
            if len(stored) >= 2 and stored[-2].close:
                previous = float(stored[-2].close)
                change_pct = round(
                    ((float(latest.close) - previous) / previous) * 100,
                    2,
                )
            info = describe_symbol(latest.symbol)
            snapshots.append(
                {
                    "symbol": latest.symbol,
                    "name": info.name,
                    "exchange": info.exchange,
                    "currency": info.currency,
                    "timezone": info.timezone,
                    "date": latest.date.isoformat(),
                    "close": float(latest.close),
                    "change_pct": change_pct,
                }
            )
    finally:
        session.close()

    payload = {
        "symbols": snapshots,
        "data_source": "Twelve Data (US) and Yahoo Finance (NSE) daily bars",
        "refreshed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": (
            "Market data may be delayed. Predictions are illustrative and are "
            "not investment advice."
        ),
    }
    missing = len(settings.all_symbol_list) - len(snapshots)
    ttl = (
        _OVERVIEW_CACHE_TTL_SECONDS
        if snapshots and missing == 0
        else _OVERVIEW_EMPTY_CACHE_TTL_SECONDS
    )
    _overview_cache["payload"] = payload
    _overview_cache["expires"] = now + ttl
    return payload


_accuracy_cache: dict[str, object] = {"payload": None, "key": None, "expires": 0.0}
_ACCURACY_CACHE_TTL_SECONDS = 600.0


@router.get(
    "/public/accuracy",
    dependencies=[Depends(enforce_public_rate_limit)],
)
def public_accuracy(
    symbol: str | None = Query(default=None, max_length=32),
) -> dict[str, object]:
    """Live track record: stored predictions scored against realized closes.

    Unauthenticated, cached briefly, and compared against a last-close
    persistence baseline so the model has to beat "tomorrow = today" to show
    value. Sample sizes are part of the payload on purpose.
    """
    key = (symbol or "").strip().upper() or None
    now = time.time()
    cached = _accuracy_cache.get("payload")
    if (
        cached is not None
        and _accuracy_cache.get("key") == key
        and now < float(_accuracy_cache.get("expires", 0.0))
    ):
        return cached  # type: ignore[return-value]

    session = get_session()
    try:
        summaries = PredictionRepository(session).public_accuracy(symbol=key)
    finally:
        session.close()

    total = sum(int(row["evaluated_predictions"]) for row in summaries)
    overall: dict[str, object] = {"evaluated_predictions": total}
    for field in (
        "mae",
        "mape_pct",
        "directional_accuracy_pct",
        "baseline_mae",
        "baseline_mape_pct",
        "baseline_directional_accuracy_pct",
        "improvement_vs_persistence_pct",
    ):
        weighted = [
            (float(row[field]), int(row["evaluated_predictions"]))
            for row in summaries
            if row[field] is not None
        ]
        denominator = sum(weight for _, weight in weighted)
        overall[field] = (
            round(sum(value * weight for value, weight in weighted) / denominator, 4)
            if denominator
            else None
        )
    if summaries:
        overall["first_prediction_date"] = min(
            str(row["first_prediction_date"]) for row in summaries
        )
        overall["last_prediction_date"] = max(
            str(row["last_prediction_date"]) for row in summaries
        )

    payload = {
        "status": "ok" if total else "insufficient_data",
        "overall": overall,
        "symbols": summaries,
        "methodology": (
            "Every prediction served by the API is stored when it is made and "
            "reconciled against the next available market close. Only "
            "reconciled predictions are counted. The baseline is last-close "
            "persistence (predicting no change); a model must beat it to add "
            "value. This is a live track record, not a backtest."
        ),
        "disclaimer": (
            "Predictions are illustrative and are not investment advice. "
            "Past forecast error does not guarantee future performance."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _accuracy_cache["payload"] = payload
    _accuracy_cache["key"] = key
    _accuracy_cache["expires"] = now + _ACCURACY_CACHE_TTL_SECONDS
    return payload


_latest_predictions_cache: dict[str, object] = {"payload": None, "expires": 0.0}
_LATEST_PREDICTIONS_CACHE_TTL_SECONDS = 300.0


@router.get(
    "/public/predictions/latest",
    dependencies=[Depends(enforce_public_rate_limit)],
)
def public_latest_predictions() -> dict[str, object]:
    """Most recent stored prediction per symbol, anonymized.

    These are predictions the API actually served and persisted; each one is
    later reconciled against the realized close for the accuracy endpoint.
    """
    now = time.time()
    cached = _latest_predictions_cache.get("payload")
    if cached is not None and now < float(
        _latest_predictions_cache.get("expires", 0.0)
    ):
        return cached  # type: ignore[return-value]

    session = get_session()
    try:
        latest = PredictionRepository(session).latest_per_symbol()
    finally:
        session.close()

    payload = {
        "predictions": [
            {
                "symbol": record.symbol,
                "prediction_date": record.prediction_date.isoformat(),
                "predicted_close": float(record.predicted_close),
                "expected_change_pct": float(record.expected_change_pct),
                "model": record.model,
            }
            for record in latest
        ],
        "disclaimer": (
            "Predictions are illustrative and are not investment advice."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _latest_predictions_cache["payload"] = payload
    _latest_predictions_cache["expires"] = (
        now + _LATEST_PREDICTIONS_CACHE_TTL_SECONDS
    )
    return payload


@router.get(
    "/backtest/{symbol}",
    dependencies=[Depends(enforce_rate_limit)],
)
def backtest_symbol(
    symbol: str,
    limit: int = Query(default=500, ge=120, le=2000),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """Walk-forward long/flat strategy vs buy-and-hold on stored daily bars.

    Fully disclosed: walk-forward out-of-sample predictions decide a
    long-or-flat position for the next bar; no transaction costs, no
    shorting, no leverage. Illustrative evaluation, not trading advice.
    """
    from app.services.backtest import run_backtest

    normalized = symbol.strip().upper()
    session = get_session()
    try:
        repository = MarketDataRepository(session)
        stored = repository.list_history(normalized, limit=limit)
    finally:
        session.close()

    if len(stored) < 120:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "INSUFFICIENT_HISTORY",
                "message": (
                    f"Not enough stored bars for '{normalized}' to backtest "
                    "(need at least 120)."
                ),
            },
        )

    import pandas as pd

    bars = pd.DataFrame(
        [
            {
                "date": row.date.isoformat(),
                "close": float(row.close),
                "volume": int(row.volume),
            }
            for row in stored
        ]
    )
    try:
        result = run_backtest(bars)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BACKTEST_INPUT_ERROR", "message": str(exc)},
        ) from exc

    return {
        "symbol": normalized,
        "metrics": result.metrics,
        "equity_curve": result.equity_curve,
        "assumptions": (
            "Walk-forward out-of-sample predictions; long when the model "
            "predicts an up move, flat otherwise. No transaction costs, no "
            "shorting, no leverage. Daily bars may be delayed."
        ),
        "disclaimer": (
            "Backtest results are illustrative and are not investment "
            "advice. Past performance does not guarantee future results."
        ),
    }


def _ingest_symbol(symbol: str, limit: int) -> dict[str, int | str]:
    session = get_session()
    try:
        repository = MarketDataRepository(session)
        prediction_repository = PredictionRepository(session)
        service = MarketDataIngestionService(
            get_provider_for_symbol(symbol),
            repository,
            prediction_repository,
        )
        return service.ingest(symbol, limit=limit)
    finally:
        session.close()


@router.post(
    "/stocks/{symbol}/ingest",
    dependencies=[Depends(enforce_rate_limit)],
)
def ingest_market_data(
    symbol: str,
    limit: int = Query(default=500, ge=20, le=5000),
) -> dict[str, int | str]:
    try:
        return _ingest_symbol(symbol, limit)
    except (ValueError, TwelveDataError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MARKET_DATA_PROVIDER_ERROR",
                "message": str(exc),
            },
        ) from exc


@router.get(
    "/stocks/{symbol}/history",
    dependencies=[Depends(enforce_rate_limit)],
)
def stock_history(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=5000),
) -> list[dict[str, object]]:
    normalized = symbol.strip().upper()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "MARKET_DATA_INPUT_ERROR",
                "message": "Symbol is required.",
            },
        )

    session = get_session()
    try:
        repository = MarketDataRepository(session)
        stored = repository.list_history(normalized, limit=limit)
        last_ingested = stored[-1].ingested_at if stored else None
        if last_ingested is not None and last_ingested.tzinfo is None:
            # SQLite returns naive datetimes even for timezone-aware columns.
            last_ingested = last_ingested.replace(tzinfo=timezone.utc)
        stale = (
            not stored
            or last_ingested
            < datetime.now(timezone.utc)
            - timedelta(minutes=settings.market_data_refresh_interval_minutes)
        )

        if len(stored) < limit or stale:
            try:
                provider = get_provider_for_symbol(normalized)
                bars = provider.history(normalized, limit=limit)
                if bars:
                    repository.upsert_many(
                        [
                            {
                                "date": date.fromisoformat(bar.date),
                                "symbol": bar.symbol,
                                "open": bar.open,
                                "high": bar.high,
                                "low": bar.low,
                                "close": bar.close,
                                "volume": bar.volume,
                                "source_provider": getattr(
                                    provider,
                                    "name",
                                    provider.__class__.__name__,
                                ),
                            }
                            for bar in bars
                        ]
                    )
                    PredictionRepository(session).evaluate_pending(normalized)
                    stored = repository.list_history(normalized, limit=limit)
            except (TwelveDataError, YFinanceError, ValueError) as exc:
                if not stored:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={
                            "code": "MARKET_DATA_PROVIDER_ERROR",
                            "message": str(exc),
                        },
                    ) from exc

        if not stored:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SYMBOL_NOT_FOUND",
                    "message": f"No market data found for symbol '{normalized}'.",
                },
            )

        return [
            {
                "date": row.date.isoformat(),
                "symbol": row.symbol,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
                "source_provider": row.source_provider,
            }
            for row in stored
        ]
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Market data is temporarily unavailable.",
            },
        ) from exc
    finally:
        session.close()


@router.get("/metrics", dependencies=[Depends(enforce_rate_limit)])
def metrics() -> dict[str, object]:
    metrics_path = Path("models/metrics.json")
    if not metrics_path.exists():
        return {
            "status": "not_available",
            "message": "Run the training module first.",
        }

    return json.loads(metrics_path.read_text(encoding="utf-8"))


@router.post(
    "/predict",
    response_model=PredictionResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
def predict(
    request: PredictionRequest,
    current_user=Depends(get_current_user),
) -> PredictionResponse:
    symbol = request.symbol.upper()
    history = [bar.model_dump() for bar in request.history]
    prediction_date = history[-1]["date"]
    cache_key = predictor.cache_key(symbol, history)

    cached = cache.get(cache_key)
    if cached is not None:
        cached["cached"] = True
        cached["persisted"] = False
        return PredictionResponse(**cached)

    try:
        result = predictor.predict(symbol=symbol, history=history)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "PREDICTION_INPUT_ERROR",
                "message": str(exc),
            },
        ) from exc

    result["prediction_date"] = prediction_date
    cache.set(cache_key, result)

    persisted = False
    session = get_session()
    try:
        PredictionRepository(session).add(
            user_id=current_user.id,
            symbol=symbol,
            prediction_date=prediction_date,
            predicted_close=float(result["predicted_close"]),
            expected_change_pct=float(result["expected_change_pct"]),
            model=str(result["model"]),
            cached=False,
        )
        persisted = True
    except SQLAlchemyError:
        session.rollback()
    finally:
        session.close()

    result["persisted"] = persisted
    return PredictionResponse(**result)


@router.get(
    "/predictions",
    response_model=list[PredictionHistoryItem],
    dependencies=[Depends(enforce_rate_limit)],
)
def prediction_history(
    symbol: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
    current_user=Depends(get_current_user),
) -> list[PredictionHistoryItem]:
    session = get_session()
    try:
        repository = PredictionRepository(session)
        records = repository.list_recent(
            user_id=current_user.id,
            symbol=symbol.upper() if symbol else None,
            limit=limit,
        )
        baseline = repository.baseline_closes_for(records)
        items = []
        for record in records:
            item = PredictionHistoryItem.model_validate(record)
            item.baseline_close = baseline.get((record.symbol, record.prediction_date))
            items.append(item)
        return items
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Prediction history is temporarily unavailable.",
            },
        ) from exc
    finally:
        session.close()


@router.get(
    "/predictions/evaluation",
    dependencies=[Depends(enforce_rate_limit)],
)
def prediction_evaluation(
    symbol: str | None = Query(default=None, max_length=32),
    current_user=Depends(get_current_user),
) -> dict[str, float | int | None]:
    session = get_session()
    try:
        repository = PredictionRepository(session)
        return repository.evaluation_summary(
            user_id=current_user.id,
            symbol=symbol.upper() if symbol else None,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Prediction evaluation is temporarily unavailable.",
            },
        ) from exc
    finally:
        session.close()


@router.get(
    "/stocks/{symbol}/indicators",
    dependencies=[Depends(enforce_rate_limit)],
)
def stock_indicators(
    symbol: str,
    limit: int = Query(default=150, ge=60, le=1500),
) -> dict[str, object]:
    """Computed indicator series (SMA/EMA/RSI/MACD/Bollinger) over stored bars.

    Values are derived only from past and current bars (no lookahead). Leading
    entries are null until each indicator has enough history.
    """
    normalized = symbol.strip().upper()
    session = get_session()
    try:
        repository = MarketDataRepository(session)
        stored = repository.list_history(normalized, limit=limit)
        if len(stored) < 60:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "INSUFFICIENT_HISTORY",
                    "message": (
                        f"Not enough stored bars for '{normalized}' to compute "
                        "indicators (need at least 60)."
                    ),
                },
            )
        bars = [
            {
                "date": row.date.isoformat(),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
            }
            for row in stored
        ]
    finally:
        session.close()

    info = describe_symbol(normalized)
    payload = compute_indicators(bars)
    payload["symbol"] = normalized
    payload["exchange"] = info.exchange
    payload["currency"] = info.currency
    return payload


@router.get(
    "/symbols",
    dependencies=[Depends(enforce_rate_limit)],
)
def list_symbols() -> list[dict[str, str]]:
    """Configured symbol universe with exchange and currency metadata."""
    return [
        {
            "symbol": info.symbol,
            "name": info.name,
            "exchange": info.exchange,
            "currency": info.currency,
            "timezone": info.timezone,
        }
        for info in (describe_symbol(s) for s in settings.all_symbol_list)
    ]


@router.get(
    "/watchlist",
    dependencies=[Depends(enforce_rate_limit)],
)
def get_watchlist(current_user=Depends(get_current_user)) -> dict[str, object]:
    session = get_session()
    try:
        symbols = WatchlistRepository(session).list_symbols(current_user.id)
    finally:
        session.close()
    return {"symbols": symbols}


@router.post(
    "/watchlist",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
def add_to_watchlist(
    payload: dict[str, str],
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    symbol = str(payload.get("symbol", "")).strip().upper()
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WATCHLIST_INPUT_ERROR", "message": "Symbol is required."},
        )
    if symbol not in settings.all_symbol_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "SYMBOL_NOT_SUPPORTED",
                "message": (
                    f"'{symbol}' is not in the configured universe. "
                    "Watchlists track symbols the platform has real data for."
                ),
            },
        )
    session = get_session()
    try:
        created = WatchlistRepository(session).add(current_user.id, symbol)
        symbols = WatchlistRepository(session).list_symbols(current_user.id)
    finally:
        session.close()
    return {"added": created, "symbols": symbols}


@router.delete(
    "/watchlist/{symbol}",
    dependencies=[Depends(enforce_rate_limit)],
)
def remove_from_watchlist(
    symbol: str,
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    session = get_session()
    try:
        removed = WatchlistRepository(session).remove(current_user.id, symbol.strip().upper())
        symbols = WatchlistRepository(session).list_symbols(current_user.id)
    finally:
        session.close()
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "WATCHLIST_ITEM_NOT_FOUND",
                "message": f"'{symbol.strip().upper()}' is not on the watchlist.",
            },
        )
    return {"removed": True, "symbols": symbols}


_screener_cache: dict[str, object] = {"payload": None, "key": None, "expires": 0.0}
_SCREENER_CACHE_TTL_SECONDS = 60.0


@router.get(
    "/screener",
    dependencies=[Depends(enforce_rate_limit)],
)
def screener(
    exchange: str | None = Query(default=None),
    min_change_pct: float | None = Query(default=None),
    max_change_pct: float | None = Query(default=None),
    min_rsi: float | None = Query(default=None, ge=0, le=100),
    max_rsi: float | None = Query(default=None, ge=0, le=100),
    above_sma20: bool | None = Query(default=None),
    min_volume: int | None = Query(default=None, ge=0),
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    """Scan the configured universe on real computed metrics from stored bars."""
    cache_key = (exchange, min_change_pct, max_change_pct, min_rsi, max_rsi, above_sma20, min_volume)
    now = time.time()
    if (
        _screener_cache.get("payload") is not None
        and _screener_cache.get("key") == cache_key
        and now < float(_screener_cache.get("expires", 0.0))
    ):
        return _screener_cache["payload"]  # type: ignore[return-value]

    session = get_session()
    try:
        repository = MarketDataRepository(session)
        histories = {
            symbol: [
                {
                    "date": row.date.isoformat(),
                    "close": row.close,
                    "volume": row.volume,
                }
                for row in repository.list_history(symbol, limit=120)
            ]
            for symbol in settings.all_symbol_list
        }
    finally:
        session.close()

    results = screen_universe(
        histories,
        exchange=exchange,
        min_change_pct=min_change_pct,
        max_change_pct=max_change_pct,
        min_rsi=min_rsi,
        max_rsi=max_rsi,
        above_sma20=above_sma20,
        min_volume=min_volume,
    )
    payload = {
        "results": results,
        "scanned": sum(1 for bars in histories.values() if len(bars) >= 21),
        "universe": len(settings.all_symbol_list),
        "disclaimer": "Metrics are computed from stored daily bars, which may be delayed.",
    }
    _screener_cache["payload"] = payload
    _screener_cache["key"] = cache_key
    _screener_cache["expires"] = now + _SCREENER_CACHE_TTL_SECONDS
    return payload
