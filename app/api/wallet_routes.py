"""Paper-trading wallet API. Every order is simulated; nothing here routes
real money, talks to a broker, or fetches live quotes. Fills use stored,
delayed daily bars only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.rate_limit_dependency import enforce_rate_limit
from app.auth.dependencies import get_current_user
from app.db.database import get_session
from app.services.wallet import WalletInputError, WalletService

router = APIRouter()

SIMULATION_LABEL = "paper-trading"


class WalletOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(min_length=1, max_length=4)
    quantity: int = Field(gt=0)
    client_order_id: str | None = Field(default=None, max_length=64)


def _order_payload(order) -> dict[str, object]:
    return {
        "id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "status": order.status,
        "fill_price": str(order.fill_price) if order.fill_price is not None else None,
        "fill_bar_date": order.fill_bar_date.isoformat() if order.fill_bar_date else None,
        "reject_code": order.reject_code,
        "client_order_id": order.client_order_id,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "simulation": SIMULATION_LABEL,
    }


@router.get("/wallet", dependencies=[Depends(enforce_rate_limit)])
def get_wallet(current_user=Depends(get_current_user)) -> dict[str, object]:
    session = get_session()
    try:
        summary = WalletService(session).summary(current_user.id)
    finally:
        session.close()
    return {**summary, "simulation": SIMULATION_LABEL}


@router.post(
    "/wallet/orders",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
def place_wallet_order(
    request: WalletOrderRequest,
    current_user=Depends(get_current_user),
) -> dict[str, object]:
    session = get_session()
    try:
        order = WalletService(session).place_order(
            user_id=current_user.id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            client_order_id=request.client_order_id,
        )
        payload = _order_payload(order)
    except WalletInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    finally:
        session.close()
    return payload


@router.get("/wallet/orders", dependencies=[Depends(enforce_rate_limit)])
def list_wallet_orders(current_user=Depends(get_current_user)) -> dict[str, object]:
    session = get_session()
    try:
        orders = WalletService(session).list_orders(current_user.id)
        payload = [_order_payload(order) for order in orders]
    finally:
        session.close()
    return {"orders": payload, "simulation": SIMULATION_LABEL}


@router.post("/wallet/reset", dependencies=[Depends(enforce_rate_limit)])
def reset_wallet(current_user=Depends(get_current_user)) -> dict[str, object]:
    session = get_session()
    try:
        service = WalletService(session)
        service.reset(current_user.id)
        summary = service.summary(current_user.id)
    finally:
        session.close()
    return {**summary, "simulation": SIMULATION_LABEL}


@router.get("/wallet/equity", dependencies=[Depends(enforce_rate_limit)])
def wallet_equity_history(current_user=Depends(get_current_user)) -> dict[str, object]:
    session = get_session()
    try:
        snapshots = WalletService(session).equity_history(current_user.id)
        payload = [
            {
                "at": snap.at.isoformat() if snap.at else None,
                "equity": str(snap.equity),
                "as_of": snap.as_of.isoformat() if snap.as_of else None,
            }
            for snap in snapshots
        ]
    finally:
        session.close()
    return {"snapshots": payload, "simulation": SIMULATION_LABEL}
