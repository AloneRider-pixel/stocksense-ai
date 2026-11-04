"""Price alert and notification API. Alerts are evaluated against stored
daily closes after ingestion; delivery is in-app plus a log-only notifier
(no email) until external delivery is approved."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.rate_limit_dependency import enforce_rate_limit
from app.auth.dependencies import get_current_user
from app.db.database import get_session
from app.services.alerts import (
    AlertInputError,
    create_rule,
    deactivate_rule,
    list_notifications,
    list_rules,
    mark_notification_seen,
)

router = APIRouter()


class AlertRuleRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    direction: str = Field(min_length=1, max_length=5)
    target_price: str = Field(min_length=1, max_length=32)


def _rule_payload(rule) -> dict[str, object]:
    return {
        "id": rule.id,
        "symbol": rule.symbol,
        "direction": rule.direction,
        "target_price": str(rule.target_price),
        "active": rule.active,
        "baseline_bar_date": (
            rule.baseline_bar_date.isoformat() if rule.baseline_bar_date else None
        ),
        "last_triggered_bar_date": (
            rule.last_triggered_bar_date.isoformat() if rule.last_triggered_bar_date else None
        ),
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


def _notification_payload(note) -> dict[str, object]:
    return {
        "id": note.id,
        "kind": note.kind,
        "title": note.title,
        "body": note.body,
        "seen": note.seen,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }


def _input_error(exc: AlertInputError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.code == "NOT_FOUND" else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(status_code=code, detail={"code": exc.code, "message": str(exc)})


@router.post(
    "/alerts",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
def create_alert(
    request: AlertRuleRequest,
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    try:
        target = Decimal(request.target_price)
    except InvalidOperation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BAD_TARGET", "message": "target price must be a number"},
        ) from exc
    session = get_session()
    try:
        rule = create_rule(
            session,
            user_id=current_user.id,
            symbol=request.symbol,
            direction=request.direction,
            target_price=target,
        )
        payload = _rule_payload(rule)
    except AlertInputError as exc:
        raise _input_error(exc) from exc
    finally:
        session.close()
    return payload


@router.get("/alerts", dependencies=[Depends(enforce_rate_limit)])
def list_alerts(current_user=Depends(get_current_user)) -> dict[str, object]:
    session = get_session()
    try:
        rules = list_rules(session, current_user.id)
        payload = [_rule_payload(rule) for rule in rules]
    finally:
        session.close()
    return {"rules": payload}


@router.post("/alerts/{rule_id}/deactivate", dependencies=[Depends(enforce_rate_limit)])
def deactivate_alert(
    rule_id: int,
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    session = get_session()
    try:
        rule = deactivate_rule(session, current_user.id, rule_id)
        payload = _rule_payload(rule)
    except AlertInputError as exc:
        raise _input_error(exc) from exc
    finally:
        session.close()
    return payload


@router.get("/notifications", dependencies=[Depends(enforce_rate_limit)])
def get_notifications(current_user=Depends(get_current_user)) -> dict[str, object]:
    session = get_session()
    try:
        notes = list_notifications(session, current_user.id)
        payload = [_notification_payload(note) for note in notes]
        unseen = sum(1 for note in notes if not note.seen)
    finally:
        session.close()
    return {"notifications": payload, "unseen_count": unseen}


@router.post("/notifications/{notification_id}/seen", dependencies=[Depends(enforce_rate_limit)])
def seen_notification(
    notification_id: int,
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    session = get_session()
    try:
        note = mark_notification_seen(session, current_user.id, notification_id)
        payload = _notification_payload(note)
    except AlertInputError as exc:
        raise _input_error(exc) from exc
    finally:
        session.close()
    return payload
