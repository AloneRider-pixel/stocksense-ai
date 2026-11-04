"""paper trading wallet: accounts, orders, positions, equity snapshots

Revision ID: 0004_paper_wallet
Revises: 0003_scanner_bars
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_paper_wallet"
down_revision = "0003_scanner_bars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cash", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_paper_accounts_user_id"),
    )
    op.create_index("ix_paper_accounts_user_id", "paper_accounts", ["user_id"])
    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("fill_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("fill_bar_date", sa.Date(), nullable=True),
        sa.Column("reject_code", sa.String(length=40), nullable=True),
        sa.Column("client_order_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "client_order_id", name="uq_paper_orders_client"),
    )
    op.create_index("ix_paper_orders_account_id", "paper_orders", ["account_id"])
    op.create_index("ix_paper_orders_status", "paper_orders", ["status"])
    op.create_index("ix_paper_orders_created_at", "paper_orders", ["created_at"])
    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("avg_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(18, 2), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "symbol", name="uq_paper_positions_symbol"),
    )
    op.create_index("ix_paper_positions_account_id", "paper_positions", ["account_id"])
    op.create_table(
        "paper_equity_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("paper_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("equity", sa.Numeric(18, 2), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=True),
    )
    op.create_index(
        "ix_paper_equity_snapshots_account_id",
        "paper_equity_snapshots",
        ["account_id"],
    )
    op.create_index("ix_paper_equity_snapshots_at", "paper_equity_snapshots", ["at"])


def downgrade() -> None:
    op.drop_table("paper_equity_snapshots")
    op.drop_table("paper_positions")
    op.drop_table("paper_orders")
    op.drop_table("paper_accounts")
