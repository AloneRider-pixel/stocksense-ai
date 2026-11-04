"""align fresh installs with the legacy schema: drop stray server defaults

Revision ID: 0008_align_legacy_defaults
Revises: 0007_watchlist_items

Migrations 0001-0003 declared three server-side defaults that the legacy
create_all startup never created - so databases installed through alembic
have them and production (created by create_all) does not:

- users.is_active DEFAULT true
- prediction_records.cached DEFAULT false
- scanner_runs.origin_reason DEFAULT ''

The application sets all three fields in Python, so the defaults are dead
weight; production is the surviving truth. This migration converges fresh
installs onto the legacy shape. On adopted production databases none of the
defaults exist and the migration writes nothing. Each drop is gated on the
current default matching the known stray value exactly; anything else fails
loudly instead of guessing. Column ordinal order in prediction_records also
differs between the two histories; it is semantically meaningless and left
as-is (documented in docs/deployment.md).
"""

import json

from alembic import op
from sqlalchemy import text

revision = "0008_align_legacy_defaults"
down_revision = "0007_watchlist_items"
branch_labels = None
depends_on = None

_STRAY_DEFAULTS = [
    ("users", "is_active", "true"),
    ("prediction_records", "cached", "false"),
    ("scanner_runs", "origin_reason", "''::character varying"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for table, column, expected in _STRAY_DEFAULTS:
        current = bind.execute(
            text(
                "SELECT pg_get_expr(d.adbin, d.adrelid) "
                "FROM pg_attrdef d "
                "JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum "
                "JOIN pg_class c ON a.attrelid = c.oid "
                "JOIN pg_namespace n ON c.relnamespace = n.oid "
                "WHERE n.nspname = 'public' AND c.relname = :table AND a.attname = :column"
            ),
            {"table": table, "column": column},
        ).scalar()
        if current is None:
            continue  # adopted legacy database: nothing to align, write nothing
        if current != expected:
            raise RuntimeError(
                f"{table}.{column} has unexpected server default {current!r}; "
                f"expected {expected!r} or none. Refusing to alter. "
                f"Context: {json.dumps({'table': table, 'column': column})}"
            )
        op.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP DEFAULT'))


def downgrade() -> None:
    # No-op: re-adding server defaults would diverge fresh installs from the
    # production (legacy) shape again.
    pass
