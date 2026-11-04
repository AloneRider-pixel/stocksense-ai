"""Paper-trading wallet: simulated orders against stored, delayed daily bars.

Hard rules for this module:
- Everything is simulated. No real-money routing, no broker, no live quotes.
- Fills use the symbol's latest STORED daily close only. If a symbol has no
  stored bar, or its latest bar is behind the most recent trading day the app
  has ingested for the NIFTY 50 universe, the order is rejected rather than
  filled on a wrong or stale price.
- Version 1 scope is INR-quoted NIFTY 50 equities only. Anything else
  (metals, FX, indices, US symbols, unknowns) is refused up front so P&L
  never mixes currencies or units.
- Money is Decimal, quantized to paise (2dp); prices keep 4dp.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import (
    MarketBarRecord,
    PaperAccount,
    PaperEquitySnapshot,
    PaperOrder,
    PaperPosition,
)
from app.market_data.symbols import lookup_symbol, nifty50_symbols
from app.services.bar_eligibility import max_eligible_bar_date

STARTING_CASH = Decimal("1000000.00")  # ₹10,00,000 of virtual money
PAISE = Decimal("0.01")
PRICE_DP = Decimal("0.0001")

SIDE_BUY = "buy"
SIDE_SELL = "sell"
STATUS_FILLED = "filled"
STATUS_REJECTED = "rejected"

REJECT_NO_STORED_PRICE = "NO_STORED_PRICE"
REJECT_STALE_PRICE = "STALE_PRICE"
REJECT_INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
REJECT_INSUFFICIENT_HOLDINGS = "INSUFFICIENT_HOLDINGS"


class WalletInputError(ValueError):
    """Invalid order input (maps to a 422 at the API layer)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _money(value: Decimal) -> Decimal:
    return value.quantize(PAISE, rounding=ROUND_HALF_UP)


def _price(value: Decimal) -> Decimal:
    return value.quantize(PRICE_DP, rounding=ROUND_HALF_UP)


class WalletService:
    def __init__(self, session: Session, now: datetime | None = None) -> None:
        self.session = session
        self._now = now

    def _max_bar_date(self):
        return max_eligible_bar_date(self._now)

    def get_or_create_account(self, user_id: int) -> PaperAccount:
        account = (
            self.session.query(PaperAccount)
            .filter(PaperAccount.user_id == user_id)
            .one_or_none()
        )
        if account is None:
            account = PaperAccount(user_id=user_id, cash=STARTING_CASH)
            self.session.add(account)
            try:
                self.session.commit()
            except IntegrityError:
                # A concurrent request created the same account first.
                self.session.rollback()
                account = (
                    self.session.query(PaperAccount)
                    .filter(PaperAccount.user_id == user_id)
                    .one()
                )
        return account

    def reset(self, user_id: int) -> PaperAccount:
        account = self.get_or_create_account(user_id)
        for model in (PaperEquitySnapshot, PaperOrder, PaperPosition):
            self.session.query(model).filter(model.account_id == account.id).delete()
        account.cash = STARTING_CASH
        self.session.commit()
        return account

    def _latest_bar(self, symbol: str) -> MarketBarRecord | None:
        """Latest bar eligible to act as a completed close.

        Future-dated and not-yet-settled same-day bars never qualify,
        so fills and valuations cannot use a price that is not final."""
        return (
            self.session.query(MarketBarRecord)
            .filter(
                MarketBarRecord.symbol == symbol,
                MarketBarRecord.date <= self._max_bar_date(),
            )
            .order_by(MarketBarRecord.date.desc())
            .first()
        )

    def _latest_ingested_trading_day(self):
        """Most recent eligible close date across the NIFTY 50 universe."""
        return (
            self.session.query(func.max(MarketBarRecord.date))
            .filter(
                MarketBarRecord.symbol.in_(nifty50_symbols()),
                MarketBarRecord.date <= self._max_bar_date(),
            )
            .scalar()
        )

    def _validate_symbol(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        info = lookup_symbol(normalized)
        if (
            info is None
            or info.asset_class != "equity"
            or info.currency != "INR"
            or info.exchange != "NSE"
            or info.is_index
        ):
            raise WalletInputError(
                "UNSUPPORTED_SYMBOL",
                "Paper trading supports NIFTY 50 stocks (INR) only; "
                f"'{normalized}' is not in that universe.",
            )
        return normalized

    def place_order(
        self,
        user_id: int,
        symbol: str,
        side: str,
        quantity: int,
        client_order_id: str | None = None,
    ) -> PaperOrder:
        account = self.get_or_create_account(user_id)
        # Lock the account row so concurrent orders serialize on Postgres.
        account = (
            self.session.query(PaperAccount)
            .filter(PaperAccount.id == account.id)
            # populate_existing is load-bearing: without it SQLAlchemy keeps
            # the pre-lock attribute values and concurrent orders lose updates
            # even though Postgres serializes the row lock.
            .with_for_update()
            .populate_existing()
            .one()
        )

        if client_order_id:
            existing = (
                self.session.query(PaperOrder)
                .filter(
                    PaperOrder.account_id == account.id,
                    PaperOrder.client_order_id == client_order_id,
                )
                .one_or_none()
            )
            if existing is not None:
                return existing

        normalized_side = side.strip().lower()
        if normalized_side not in (SIDE_BUY, SIDE_SELL):
            raise WalletInputError("INVALID_SIDE", "Side must be 'buy' or 'sell'.")
        if not isinstance(quantity, int) or quantity <= 0:
            raise WalletInputError(
                "INVALID_QUANTITY", "Quantity must be a positive whole number of shares."
            )
        normalized_symbol = self._validate_symbol(symbol)

        order = PaperOrder(
            account_id=account.id,
            symbol=normalized_symbol,
            side=normalized_side,
            quantity=quantity,
            status=STATUS_REJECTED,
            client_order_id=client_order_id,
        )

        bar = self._latest_bar(normalized_symbol)
        if bar is None:
            order.reject_code = REJECT_NO_STORED_PRICE
            return self._record(order)

        latest_trading_day = self._latest_ingested_trading_day()
        if latest_trading_day is not None and bar.date < latest_trading_day:
            order.reject_code = REJECT_STALE_PRICE
            return self._record(order)

        price = _price(Decimal(str(bar.close)))

        position = (
            self.session.query(PaperPosition)
            .filter(
                PaperPosition.account_id == account.id,
                PaperPosition.symbol == normalized_symbol,
            )
            .with_for_update()
            .populate_existing()
            .one_or_none()
        )

        if normalized_side == SIDE_BUY:
            cost = _money(price * quantity)
            if Decimal(account.cash) < cost:
                order.reject_code = REJECT_INSUFFICIENT_FUNDS
                return self._record(order)
            account.cash = _money(Decimal(account.cash) - cost)
            if position is None:
                position = PaperPosition(
                    account_id=account.id,
                    symbol=normalized_symbol,
                    quantity=0,
                    avg_cost=Decimal("0"),
                    realized_pnl=Decimal("0"),
                )
                self.session.add(position)
            total_qty = position.quantity + quantity
            position.avg_cost = _price(
                (Decimal(position.avg_cost) * position.quantity + price * quantity)
                / total_qty
            )
            position.quantity = total_qty
        else:
            held = position.quantity if position is not None else 0
            if held < quantity:
                order.reject_code = REJECT_INSUFFICIENT_HOLDINGS
                return self._record(order)
            assert position is not None
            proceeds = _money(price * quantity)
            realized = _money((price - Decimal(position.avg_cost)) * quantity)
            position.realized_pnl = _money(Decimal(position.realized_pnl) + realized)
            position.quantity = held - quantity
            account.cash = _money(Decimal(account.cash) + proceeds)

        order.status = STATUS_FILLED
        order.fill_price = price
        order.fill_bar_date = bar.date
        self.session.add(order)
        self.session.flush()
        self._snapshot_equity(account)
        try:
            self.session.commit()
        except IntegrityError:
            # Lost a concurrent client_order_id race: the other request's
            # order won, so return it instead of double-filling.
            self.session.rollback()
            if client_order_id:
                existing = (
                    self.session.query(PaperOrder)
                    .filter(
                        PaperOrder.account_id == account.id,
                        PaperOrder.client_order_id == client_order_id,
                    )
                    .one_or_none()
                )
                if existing is not None:
                    return existing
            raise
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return order

    def _record(self, order: PaperOrder) -> PaperOrder:
        self.session.add(order)
        self.session.commit()
        return order

    def _positions_value(self, account: PaperAccount) -> tuple[Decimal, object]:
        """Market value of open positions at each symbol's latest stored close."""
        positions = (
            self.session.query(PaperPosition)
            .filter(PaperPosition.account_id == account.id, PaperPosition.quantity > 0)
            .all()
        )
        total = Decimal("0")
        latest_date = None
        for position in positions:
            bar = self._latest_bar(position.symbol)
            if bar is None:
                continue
            total += Decimal(str(bar.close)) * position.quantity
            latest_date = max(latest_date, bar.date) if latest_date else bar.date
        return total, latest_date

    def _snapshot_equity(self, account: PaperAccount) -> None:
        positions_value, as_of = self._positions_value(account)
        equity = _money(Decimal(account.cash) + positions_value)
        self.session.add(
            PaperEquitySnapshot(
                account_id=account.id,
                at=datetime.now(timezone.utc),
                equity=equity,
                as_of=as_of,
            )
        )

    def summary(self, user_id: int) -> dict[str, object]:
        account = self.get_or_create_account(user_id)
        positions = (
            self.session.query(PaperPosition)
            .filter(PaperPosition.account_id == account.id)
            .order_by(PaperPosition.symbol)
            .all()
        )
        items: list[dict[str, object]] = []
        market_value = Decimal("0")
        realized_total = Decimal("0")
        as_of = None
        for position in positions:
            realized_total += Decimal(position.realized_pnl)
            if position.quantity <= 0:
                continue
            bar = self._latest_bar(position.symbol)
            if bar is None:
                continue
            last_close = _price(Decimal(str(bar.close)))
            value = _money(last_close * position.quantity)
            unrealized = _money(
                (last_close - Decimal(position.avg_cost)) * position.quantity
            )
            market_value += value
            as_of = max(as_of, bar.date) if as_of else bar.date
            items.append(
                {
                    "symbol": position.symbol,
                    "quantity": position.quantity,
                    "avg_cost": str(position.avg_cost),
                    "last_close": str(last_close),
                    "bar_date": bar.date.isoformat(),
                    "market_value": str(value),
                    "unrealized_pnl": str(unrealized),
                    "realized_pnl": str(position.realized_pnl),
                }
            )
        cash = _money(Decimal(account.cash))
        return {
            "cash": str(cash),
            "market_value": str(_money(market_value)),
            "equity": str(_money(cash + market_value)),
            "realized_pnl": str(_money(realized_total)),
            "as_of": as_of.isoformat() if as_of else None,
            "positions": items,
        }

    def list_orders(self, user_id: int, limit: int = 100) -> list[PaperOrder]:
        account = self.get_or_create_account(user_id)
        return (
            self.session.query(PaperOrder)
            .filter(PaperOrder.account_id == account.id)
            .order_by(PaperOrder.created_at.desc(), PaperOrder.id.desc())
            .limit(limit)
            .all()
        )

    def snapshot_holders(self, symbol: str) -> int:
        """Record equity snapshots for accounts holding a freshly ingested symbol.

        Called by the ingestion worker after new bars land, so the equity
        curve moves with normal daily ingestion and stays consistent with
        the wallet summary card. One snapshot per account per bar date:
        re-ingesting the same day is a no-op. Valuation uses only
        eligible closes via _positions_value."""
        accounts = (
            self.session.query(PaperPosition.account_id)
            .filter(PaperPosition.symbol == symbol, PaperPosition.quantity > 0)
            .distinct()
            .all()
        )
        created = 0
        for (account_id,) in accounts:
            account = self.session.get(PaperAccount, account_id)
            if account is None:
                continue
            positions_value, as_of = self._positions_value(account)
            if as_of is None:
                continue
            existing = (
                self.session.query(PaperEquitySnapshot)
                .filter(
                    PaperEquitySnapshot.account_id == account_id,
                    PaperEquitySnapshot.as_of == as_of,
                )
                .first()
            )
            if existing is not None:
                continue
            equity = _money(Decimal(account.cash) + positions_value)
            self.session.add(
                PaperEquitySnapshot(
                    account_id=account_id,
                    at=datetime.now(timezone.utc),
                    equity=equity,
                    as_of=as_of,
                )
            )
            created += 1
        if created:
            self.session.commit()
        return created

    def equity_history(self, user_id: int, limit: int = 500) -> list[PaperEquitySnapshot]:
        account = self.get_or_create_account(user_id)
        return (
            self.session.query(PaperEquitySnapshot)
            .filter(PaperEquitySnapshot.account_id == account.id)
            .order_by(PaperEquitySnapshot.at)
            .limit(limit)
            .all()
        )
