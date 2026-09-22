"""initial StockSense AI schema

Revision ID: 0001_initial
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    op.create_table(
        "prediction_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("predicted_close", sa.Float(), nullable=False),
        sa.Column("expected_change_pct", sa.Float(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_prediction_records_user_id", "prediction_records", ["user_id"])
    op.create_index("ix_prediction_records_symbol", "prediction_records", ["symbol"])
    op.create_index("ix_prediction_records_created_at", "prediction_records", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_prediction_records_created_at", table_name="prediction_records")
    op.drop_index("ix_prediction_records_symbol", table_name="prediction_records")
    op.drop_index("ix_prediction_records_user_id", table_name="prediction_records")
    op.drop_table("prediction_records")

    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
