"""watchlist_items: create on fresh installs, verify on adopted databases

Revision ID: 0007_watchlist_items
Revises: 0006_alert_rule_baseline

The legacy create_all startup always created watchlist_items, but no earlier
migration does - so databases installed after alembic was introduced would
silently miss the table while adopted (pre-migration) databases already have
it. This migration closes the divergence:

- table absent (fresh install): create it with the exact legacy shape
  (verified against the production-verified legacy schema spec);
- table present (adopted database): verify its structure matches that shape
  and fail loudly on any difference - never a blind CREATE IF NOT EXISTS
  that would hide drift. Existing rows are never touched.

downgrade() is intentionally a no-op: on adopted databases this table
predates alembic and holds user data, so dropping it must be a deliberate
manual action, never an automatic reversal.
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0007_watchlist_items"
down_revision = "0006_alert_rule_baseline"
branch_labels = None
depends_on = None

_EXPECTED_COLUMNS = [
    ("id", "integer", True),
    ("user_id", "integer", True),
    ("symbol", "character varying(32)", True),
    ("created_at", "timestamp with time zone", True),
]
_EXPECTED_UNIQUE = [["symbol", "user_id"]]
_EXPECTED_INDEXES = {
    "ix_watchlist_items_user_id": False,
    "uq_watchlist_user_symbol": True,
    "watchlist_items_pkey": True,
}


def _create() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"])


def _verify_existing(bind) -> list[str]:
    diffs: list[str] = []
    rows = bind.execute(
        text(
            "SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod), a.attnotnull "
            "FROM pg_attribute a JOIN pg_class c ON a.attrelid = c.oid "
            "JOIN pg_namespace n ON c.relnamespace = n.oid "
            "WHERE n.nspname = 'public' AND c.relname = 'watchlist_items' "
            "AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum"
        )
    ).fetchall()
    actual_cols = [(r[0], r[1], bool(r[2])) for r in rows]
    for (name, typ, nn), (aname, atyp, ann) in zip(
        _EXPECTED_COLUMNS, actual_cols + [None] * max(0, len(_EXPECTED_COLUMNS) - len(actual_cols))
    ):
        if (aname, atyp, ann) != (name, typ, nn):
            diffs.append(f"column {name}: expected {(name, typ, nn)}, found {(aname, atyp, ann)}")
    if len(actual_cols) != len(_EXPECTED_COLUMNS):
        diffs.append(f"column count {len(actual_cols)} != expected {len(_EXPECTED_COLUMNS)}")

    constraints = bind.execute(
        text(
            "SELECT con.contype, "
            "ARRAY(SELECT att.attname FROM unnest(con.conkey) WITH ORDINALITY AS o(attnum, n) "
            "JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = o.attnum "
            "ORDER BY o.n), con.confrelid::regclass::text, con.confupdtype, con.confdeltype "
            "FROM pg_constraint con JOIN pg_class c ON con.conrelid = c.oid "
            "JOIN pg_namespace n ON c.relnamespace = n.oid "
            "WHERE n.nspname = 'public' AND c.relname = 'watchlist_items'"
        )
    ).fetchall()
    pk = next((list(r[1]) for r in constraints if r[0] == "p"), [])
    if pk != ["id"]:
        diffs.append(f"primary key {pk} != expected ['id']")
    uniques = sorted(sorted(r[1]) for r in constraints if r[0] == "u")
    if uniques != _EXPECTED_UNIQUE:
        diffs.append(f"unique constraints {uniques} != expected {_EXPECTED_UNIQUE}")
    fks = [r for r in constraints if r[0] == "f"]
    if len(fks) != 1 or list(fks[0][1]) != ["user_id"] or fks[0][2] != "users" or fks[0][4] != "c":
        diffs.append(
            f"foreign keys {[(list(r[1]), r[2], r[3], r[4]) for r in fks]} "
            "!= expected user_id -> users(id) ON DELETE CASCADE"
        )

    indexes = {
        r[0]: bool(r[1])
        for r in bind.execute(
            text(
                "SELECT i.relname, ix.indisunique FROM pg_index ix "
                "JOIN pg_class c ON ix.indrelid = c.oid JOIN pg_class i ON ix.indexrelid = i.oid "
                "JOIN pg_namespace n ON c.relnamespace = n.oid "
                "WHERE n.nspname = 'public' AND c.relname = 'watchlist_items'"
            )
        ).fetchall()
    }
    if indexes != _EXPECTED_INDEXES:
        diffs.append(f"indexes {indexes} != expected {_EXPECTED_INDEXES}")
    return diffs


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(text("SELECT to_regclass('public.watchlist_items')")).scalar()
    if not exists:
        _create()
        return
    diffs = _verify_existing(bind)
    if diffs:
        raise RuntimeError(
            "watchlist_items already exists but does not match the expected legacy "
            "schema; refusing to treat the migration as applied. Differences: " + json.dumps(diffs)
        )


def downgrade() -> None:
    # No-op on purpose: on adopted databases watchlist_items predates alembic
    # and holds user data; dropping it is a deliberate manual action only.
    pass
