"""scanner bars for the Nifty 500 universe

Revision ID: 0003_scanner_bars
Revises: 0002_market_data_evaluation
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_scanner_bars"
down_revision = "0002_market_data_evaluation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scanner_bars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.UniqueConstraint("symbol", "date", name="uq_scanner_bars_symbol_date"),
    )
    op.create_index("ix_scanner_bars_symbol", "scanner_bars", ["symbol"])
    op.create_table(
        "scanner_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("origin_reason", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("entry_not_before", sa.Date(), nullable=False),
        sa.Column("formula_version", sa.String(length=32), nullable=False),
        sa.Column("config", sa.Text(), nullable=False),
        sa.Column("excluded", sa.Text(), nullable=False),
        sa.Column("universe_count", sa.Integer(), nullable=False),
        sa.Column("ranked_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_scanner_runs_as_of", "scanner_runs", ["as_of"])
    op.create_table(
        "scanner_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("scanner_runs.id"), nullable=False),
        sa.Column("source_bar_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("inputs", sa.Text(), nullable=False),
        sa.UniqueConstraint("run_id", "symbol", "kind", name="uq_scanner_signals_run"),
    )
    op.create_index("ix_scanner_signals_run_id", "scanner_signals", ["run_id"])
    op.create_index("ix_scanner_signals_source_bar_date", "scanner_signals", ["source_bar_date"])


def downgrade() -> None:
    op.drop_table("scanner_signals")
    op.drop_table("scanner_runs")
    op.drop_index("ix_scanner_bars_symbol", table_name="scanner_bars")
    op.drop_table("scanner_bars")
