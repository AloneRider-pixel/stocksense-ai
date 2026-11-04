"""Structural schema introspection and comparison for the alembic adoption gate.

The gate compares a live database against the committed legacy schema spec
(legacy_schema_spec.json, generated from app/db/legacy_models_snapshot.py).
Only a database whose structure exactly matches that spec may be stamped with
the pre-migration head; anything else fails closed.

Comparison coverage: tables; columns as name + format_type(atttypid, atttypmod)
(full type precision) + NOT NULL + column default expression; primary keys;
unique constraints; check constraints; foreign keys including ON UPDATE /
ON DELETE actions; index names with uniqueness flag and full index definition;
installed extensions. Column ORDER is the one documented exclusion: it carries
no semantic meaning for stamp safety (a repaired column lands last in ordinal
position without changing the schema's behavior). The spec was verified byte-
identical in shape against the production database's own introspection
(PostgreSQL 18.6) on 2026-11-04.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

LEGACY_HEAD_REVISION = "0003_scanner_bars"

SPEC_PATH = Path(__file__).with_name("legacy_schema_spec.json")

_FK_ACTION = {
    "a": "NO ACTION",
    "r": "RESTRICT",
    "c": "CASCADE",
    "n": "SET NULL",
    "d": "SET DEFAULT",
}

_COLUMNS_SQL = text(
    """
    SELECT c.relname AS table_name,
           a.attname AS column_name,
           pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
           a.attnotnull AS not_null,
           coalesce(pg_get_expr(d.adbin, d.adrelid), '') AS column_default
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version'
      AND a.attnum > 0 AND NOT a.attisdropped
    ORDER BY c.relname, a.attnum
    """
)

_CONSTRAINTS_SQL = text(
    """
    SELECT c.relname AS table_name, con.contype, con.conname,
           ARRAY(SELECT att.attname
                 FROM unnest(con.conkey) WITH ORDINALITY AS ord(attnum, n)
                 JOIN pg_attribute att
                   ON att.attrelid = con.conrelid AND att.attnum = ord.attnum
                 ORDER BY ord.n) AS cols,
           CASE WHEN con.contype = 'f' THEN con.confrelid::regclass::text END AS ref_table,
           CASE WHEN con.contype = 'f' THEN
               ARRAY(SELECT att.attname
                     FROM unnest(con.confkey) WITH ORDINALITY AS ord(attnum, n)
                     JOIN pg_attribute att
                       ON att.attrelid = con.confrelid AND att.attnum = ord.attnum
                     ORDER BY ord.n) END AS ref_cols,
           con.confupdtype, con.confdeltype,
           pg_get_constraintdef(con.oid) AS definition
    FROM pg_constraint con
    JOIN pg_class c ON con.conrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public' AND con.contype IN ('p', 'u', 'f', 'c')
      AND c.relname <> 'alembic_version'
    ORDER BY 1, 2, 3
    """
)

_INDEXES_SQL = text(
    """
    SELECT c.relname AS table_name, i.relname AS index_name, ix.indisunique,
           pg_get_indexdef(ix.indexrelid) AS definition
    FROM pg_index ix
    JOIN pg_class c ON ix.indrelid = c.oid
    JOIN pg_class i ON ix.indexrelid = i.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version'
    ORDER BY 1, 2
    """
)

_EXTENSIONS_SQL = text("SELECT extname FROM pg_extension ORDER BY 1")


def _new_table_entry() -> dict:
    return {"columns": [], "primary_key": [], "unique": [], "fks": [], "checks": [], "indexes": {}}


def introspect_schema(conn) -> dict:
    """Return the structural schema of the public schema as plain data."""
    tables: dict[str, dict] = {}
    for table, column, data_type, not_null, default in conn.execute(_COLUMNS_SQL):
        tables.setdefault(table, _new_table_entry())["columns"].append(
            [column, data_type, bool(not_null), default]
        )
    for table, contype, _name, cols, ref_table, ref_cols, upd, dele, definition in conn.execute(
        _CONSTRAINTS_SQL
    ):
        entry = tables.setdefault(table, _new_table_entry())
        if contype == "p":
            entry["primary_key"] = list(cols)
        elif contype == "u":
            entry["unique"].append(sorted(cols))
        elif contype == "f":
            entry["fks"].append(
                [
                    list(cols),
                    ref_table,
                    list(ref_cols),
                    _FK_ACTION.get(upd, upd),
                    _FK_ACTION.get(dele, dele),
                ]
            )
        else:
            entry["checks"].append(definition)
    for table, index_name, is_unique, definition in conn.execute(_INDEXES_SQL):
        tables.setdefault(table, _new_table_entry())["indexes"][index_name] = {
            "unique": bool(is_unique),
            "definition": definition,
        }
    for entry in tables.values():
        entry["unique"] = sorted(map(list, entry["unique"]))
        entry["checks"] = sorted(entry["checks"])
        entry["fks"] = sorted(entry["fks"], key=lambda f: (f[1], f[0]))
    extensions = [r[0] for r in conn.execute(_EXTENSIONS_SQL)]
    return {"tables": dict(sorted(tables.items())), "extensions": extensions}


def load_legacy_spec() -> dict:
    return json.loads(SPEC_PATH.read_text())["schema"]


def _diff_table(name: str, a: dict, s: dict, diffs: list[str]) -> None:
    if a["columns"] != s["columns"]:
        a_cols = {c[0]: c for c in a["columns"]}
        s_cols = {c[0]: c for c in s["columns"]}
        for col in sorted(set(a_cols) | set(s_cols)):
            if col not in s_cols:
                diffs.append(f"{name}: unexpected column {col}")
            elif col not in a_cols:
                diffs.append(f"{name}: missing column {col}")
            elif a_cols[col][1:] != s_cols[col][1:]:
                diffs.append(
                    f"{name}.{col}: type/nullable/default {a_cols[col][1:]} "
                    f"!= expected {s_cols[col][1:]}"
                )
    for key, label in (
        ("primary_key", "primary key"),
        ("unique", "unique constraints"),
        ("checks", "check constraints"),
        ("fks", "foreign keys"),
        ("indexes", "indexes"),
    ):
        if a[key] != s[key]:
            diffs.append(f"{name}: {label} {a[key]} != expected {s[key]}")


def diff_against_spec(actual: dict, spec: dict) -> list[str]:
    """Human-readable differences; empty list means exact structural match."""
    diffs: list[str] = []
    a_tables, s_tables = actual["tables"], spec["tables"]
    for table in sorted(set(a_tables) | set(s_tables)):
        if table not in s_tables:
            diffs.append(f"unexpected table: {table}")
        elif table not in a_tables:
            diffs.append(f"missing table: {table}")
        else:
            _diff_table(table, a_tables[table], s_tables[table], diffs)
    if actual.get("extensions") != spec.get("extensions"):
        diffs.append(f"extensions {actual.get('extensions')} != expected {spec.get('extensions')}")
    return diffs
