"""separate alert rule baseline from last-triggered bookkeeping

Revision ID: 0006_alert_rule_baseline
Revises: 0005_price_alerts
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_alert_rule_baseline"
down_revision = "0005_price_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alert_rules", sa.Column("baseline_bar_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("alert_rules", "baseline_bar_date")
