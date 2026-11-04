"""price alert rules and in-app notifications

Revision ID: 0005_price_alerts
Revises: 0004_paper_wallet
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_price_alerts"
down_revision = "0004_paper_wallet"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=5), nullable=False),
        sa.Column("target_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("last_triggered_bar_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alert_rules_user_id", "alert_rules", ["user_id"])
    op.create_index("ix_alert_rules_symbol", "alert_rules", ["symbol"])
    op.create_index("ix_alert_rules_active", "alert_rules", ["active"])
    op.create_index("ix_alert_rules_created_at", "alert_rules", ["created_at"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("seen", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_kind", "notifications", ["kind"])
    op.create_index("ix_notifications_seen", "notifications", ["seen"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("alert_rules")
