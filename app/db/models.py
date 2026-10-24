from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class MarketBarRecord(Base):
    __tablename__ = "market_bars"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_market_bars_symbol_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    source_provider: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class PredictionRecord(Base):
    __tablename__ = "prediction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    prediction_date: Mapped[date] = mapped_column(Date, index=True)
    predicted_close: Mapped[float] = mapped_column(Float)
    expected_change_pct: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(64))
    cached: Mapped[bool] = mapped_column(Boolean, default=False)

    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    actual_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    absolute_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentage_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    direction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class ScannerBar(Base):
    """Daily bars for the Nifty 500 scanner universe.

    Kept separate from ``market_bars`` so the scanner's much larger universe
    never touches the forecast/evaluation data.
    """

    __tablename__ = "scanner_bars"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_scanner_bars_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    date: Mapped[date] = mapped_column(Date)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)


class ScannerRun(Base):
    """One immutable observation run: when signals were computed and with what rules/data checks."""

    __tablename__ = "scanner_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    as_of: Mapped[date] = mapped_column(Date, index=True)  # latest bar date used
    origin: Mapped[str] = mapped_column(String(16))  # "forward" (live, prompt) or "retrospective"
    origin_reason: Mapped[str] = mapped_column(String(160), default="")
    entry_not_before: Mapped[date] = mapped_column(Date)  # entry = close of first session on/after this date
    formula_version: Mapped[str] = mapped_column(String(32))
    config: Mapped[str] = mapped_column(Text)  # JSON: RS and breakout parameters
    excluded: Mapped[str] = mapped_column(Text)  # JSON: symbol -> reason, as of this run
    universe_count: Mapped[int] = mapped_column(Integer)
    ranked_count: Mapped[int] = mapped_column(Integer)


class ScannerSignal(Base):
    """Signal as observed in a run. Rows are only ever inserted, never edited or deleted."""

    __tablename__ = "scanner_signals"
    __table_args__ = (UniqueConstraint("run_id", "symbol", "kind", name="uq_scanner_signals_run"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scanner_runs.id"), index=True)
    source_bar_date: Mapped[date] = mapped_column(Date, index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(24))
    close: Mapped[float] = mapped_column(Float)
    inputs: Mapped[str] = mapped_column(Text)  # JSON snapshot of the numbers behind the signal
