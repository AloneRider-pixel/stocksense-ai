"""market data and prediction evaluation

Revision ID: 0002_market_data_evaluation
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_market_data_evaluation"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_bars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("source_provider", sa.String(length=64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("symbol", "date", name="uq_market_bars_symbol_date"),
    )
    op.create_index("ix_market_bars_symbol", "market_bars", ["symbol"])
    op.create_index("ix_market_bars_date", "market_bars", ["date"])
    op.create_index("ix_market_bars_ingested_at", "market_bars", ["ingested_at"])

    op.alter_column(
        "prediction_records",
        "symbol",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
    )

    op.add_column(
        "prediction_records",
        sa.Column("prediction_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "prediction_records",
        sa.Column("actual_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "prediction_records",
        sa.Column("actual_close", sa.Float(), nullable=True),
    )
    op.add_column(
        "prediction_records",
        sa.Column("absolute_error", sa.Float(), nullable=True),
    )
    op.add_column(
        "prediction_records",
        sa.Column("percentage_error", sa.Float(), nullable=True),
    )
    op.add_column(
        "prediction_records",
        sa.Column("direction_correct", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "prediction_records",
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        "UPDATE prediction_records SET prediction_date = CAST(created_at AS DATE) "
        "WHERE prediction_date IS NULL"
    )

    with op.batch_alter_table("prediction_records") as batch:
        batch.alter_column(
            "prediction_date",
            existing_type=sa.Date(),
            nullable=False,
        )

    op.create_index(
        "ix_prediction_records_prediction_date",
        "prediction_records",
        ["prediction_date"],
    )
    op.create_index(
        "ix_prediction_records_actual_date",
        "prediction_records",
        ["actual_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prediction_records_actual_date",
        table_name="prediction_records",
    )
    op.drop_index(
        "ix_prediction_records_prediction_date",
        table_name="prediction_records",
    )

    for column in (
        "evaluated_at",
        "direction_correct",
        "percentage_error",
        "absolute_error",
        "actual_close",
        "actual_date",
        "prediction_date",
    ):
        op.drop_column("prediction_records", column)

    op.alter_column(
        "prediction_records",
        "symbol",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
    )

    op.drop_index(
        "ix_market_bars_ingested_at",
        table_name="market_bars",
    )
    op.drop_index(
        "ix_market_bars_date",
        table_name="market_bars",
    )
    op.drop_index(
        "ix_market_bars_symbol",
        table_name="market_bars",
    )
    op.drop_table("market_bars")
