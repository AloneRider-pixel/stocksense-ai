"""Read-only evidence about stored data. Never triggers provider network calls."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.auth.dependencies import get_current_user
from app.db.database import get_session
from app.db.models import MarketBarRecord
from app.market_data.trust import SOURCE_POLICIES

router = APIRouter(prefix="/data-health", tags=["data health"])


def _time(value) -> str | None:
    if value is None:
        return None
    # Stored SQLite values can lack tzinfo; do not invent a timezone for those rows.
    return value.isoformat()


@router.get("")
def data_health(current_user=Depends(get_current_user)) -> dict:
    session = get_session()
    try:
        rows = session.execute(select(
            MarketBarRecord.source_provider,
            func.count(MarketBarRecord.id),
            func.count(func.distinct(MarketBarRecord.symbol)),
            func.max(MarketBarRecord.date),
            func.max(MarketBarRecord.ingested_at),
        ).group_by(MarketBarRecord.source_provider)).all()
    finally:
        session.close()
    sources = []
    for provider, count, symbols, latest, ingested in rows:
        policy_id = "yfinance" if provider == "yfinance_nse" else "twelvedata" if provider in {"twelve_data", "twelvedata"} else None
        policy = SOURCE_POLICIES.get(policy_id, {})
        sources.append({
            "provider": provider, "stored_rows": count, "symbols": symbols,
            "latest_session": str(latest) if latest else None,
            "last_ingested_at": _time(ingested),
            "public_display": policy.get("public_display", "not_cleared"),
            "policy_url": policy.get("policy_url"),
            "freshness": "unverified_calendar_not_integrated",
            "warning": "Storage counts are not proof of current, complete or cross-source-verified prices.",
        })
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(), "stored_sources": sources,
        "coverage": "stored_rows_only", "live_quotes_verified": False,
        "headline_collector": "local_candidate_not_connected",
        "limitations": [
            "No approved session calendar is integrated here; do not infer freshness from collection time.",
            "Public-display rights have not been cleared by this check.",
            "SEBI RSS is regulatory headlines only; company filings and broad market news are not connected.",
            "This endpoint does not certify source accuracy or commercial readiness.",
        ],
        "source_policies": [{"id": key, **value} for key, value in SOURCE_POLICIES.items()],
    }
