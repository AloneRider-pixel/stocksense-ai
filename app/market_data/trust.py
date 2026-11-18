"""Local-only data evidence. No scheduler, production DB writes or provider activation."""
from __future__ import annotations

import hashlib
import json
import math
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

SEBI_FEED = "https://www.sebi.gov.in/sebirss.xml"
SOURCE_POLICIES = {
    "sebi_rss": {
        "kind": "regulatory_headlines", "collection": "official_feed",
        "public_display": "review_required", "url": SEBI_FEED,
        "policy_url": "https://www.sebi.gov.in/rss.html",
        "note": "Official RSS supports reader delivery. Full-text republication is not granted here.",
    },
    "nse": {
        "kind": "market_and_corporate_data", "collection": "agreement_required",
        "public_display": "agreement_required",
        "policy_url": "https://www.nse.in/static/market-data/nse-data-policy",
    },
    "bse": {
        "kind": "market_and_corporate_data", "collection": "written_consent_required",
        "public_display": "permission_required",
        "policy_url": "https://beta.bseindia.com/static/about/website_policy.html",
    },
    "yfinance": {
        "kind": "unofficial_market_data", "collection": "research_review_required",
        "public_display": "not_cleared",
        "policy_url": "https://ranaroussi.github.io/yfinance/",
    },
    "twelvedata": {
        "kind": "market_data", "collection": "plan_and_exchange_dependent",
        "public_display": "plan_and_exchange_dependent",
        "note": "Business display depends on plan and exchange terms. Redistribution is a separate licensing question.",
        "policy_url": "https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage",
    },
    "rbi_dbie": {
        "kind": "macro_reference", "collection": "review_required",
        "public_display": "review_required", "url": "https://data.rbi.org.in/DBIE/",
        "note": "Primary macro source candidate, not an approved automated adapter.",
    },
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def parse_sebi_feed(raw: bytes, *, fetched_at: datetime) -> dict:
    """Store headline/link metadata only; zero items never means no regulatory events."""
    fetched_at = _utc(fetched_at)
    if len(raw) > 2_000_000:
        raise ValueError("feed exceeds 2 MB limit")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD/entity declarations are not supported")
    root = ET.fromstring(raw)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("expected RSS channel")
    records, rejected, seen = [], [], set()
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        u = urlsplit(link)
        if not title or len(title) > 2000 or u.scheme != "https" or u.hostname not in {"www.sebi.gov.in", "sebi.gov.in"} or u.username or u.password:
            rejected.append("missing_title_or_untrusted_link")
            continue
        try:
            published = _utc(parsedate_to_datetime(item.findtext("pubDate") or ""))
        except (ValueError, TypeError, AttributeError):
            rejected.append("missing_or_invalid_publication_time")
            continue
        if published > fetched_at + timedelta(minutes=5):
            rejected.append("future_publication_time")
            continue
        key = hashlib.sha256(link.encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "id": key, "title": title, "url": link, "source": "sebi_rss",
            "published_at": published.isoformat(), "fetched_at": fetched_at.isoformat(),
            "status": "headline_only", "public_display": "review_required",
        })
    return {
        "schema_version": 1, "source": "sebi_rss", "source_url": SEBI_FEED,
        "fetched_at": fetched_at.isoformat(), "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "collection_status": "items_received" if records else "empty_or_all_rejected",
        "coverage_warning": "This feed is not a complete market-news or company-announcement universe.",
        "records": records, "rejected": rejected,
    }


def validate_daily_bar(bar: dict, *, expected_session: date, source: str) -> dict:
    """Caller supplies the calendar's expected completed session, never weekday guesswork."""
    errors = []
    try:
        session = date.fromisoformat(bar["date"])
        if session.isoformat() != bar["date"]:
            raise ValueError("non-canonical date")
    except (ValueError, TypeError, KeyError):
        session = None
        errors.append("invalid_session_date")
    values = {}
    for field in ("open", "high", "low", "close", "volume"):
        raw = bar.get(field)
        if isinstance(raw, bool) or not isinstance(raw, (float, int)) or not math.isfinite(raw):
            errors.append(f"invalid_{field}")
        else:
            values[field] = raw
    if all(k in values for k in ("open", "high", "low", "close")):
        o, h, low, c = (values[k] for k in ("open", "high", "low", "close"))
        if min(o, h, low, c) <= 0 or not low <= min(o, c) <= max(o, c) <= h:
            errors.append("invalid_ohlc_bounds")
    if "volume" in values and (values["volume"] < 0 or int(values["volume"]) != values["volume"]):
        errors.append("invalid_volume")
    if not bar.get("symbol") or not bar.get("exchange") or not bar.get("currency"):
        errors.append("missing_instrument_identity")
    if bar.get("adjustment") not in {"raw", "split_adjusted", "total_return"}:
        errors.append("unknown_adjustment_basis")
    if session and session > expected_session:
        errors.append("not_a_completed_session")
    policy = SOURCE_POLICIES.get(source)
    if not policy:
        errors.append("unknown_source")
    stale = bool(session and session < expected_session)
    return {
        "quality": "rejected" if errors else "stale" if stale else "valid",
        "errors": errors, "warnings": ["zero_volume_check_instrument_type"] if values.get("volume") == 0 else [],
        "expected_session": expected_session.isoformat(),
        "public_display": policy["public_display"] if policy else "not_cleared",
        "usable_for_current_signals": not errors and not stale,
        "note": "Quality validation is not a license or a cross-source price confirmation.",
    }


def snapshot_json(snapshot: dict) -> str:
    return json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
