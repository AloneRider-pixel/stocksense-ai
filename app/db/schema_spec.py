"""Structural schema introspection and comparison for the alembic adoption gate.

The gate compares a live database against the committed legacy schema spec
(legacy_schema_spec.json, generated from app/db/legacy_models_snapshot.py).
Only a database whose structure exactly matches that spec may be stamped with
the pre-migration head; anything else fails closed. Comparison is structural:
tables, columns (name/type/nullability, in ordinal order), primary keys,
unique constraints, foreign keys, and index names/uniqueness. Column order,
column default
expressions and index definitions are intentionally excluded: their text
representation varies with the SQLAlchemy/Postgres version that issued the
DDL, while every difference that would make a stamp unsafe shows up in the
structural shape.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

LEGACY_HEAD_REVISION = "0003_scanner_bars"

SPEC_PATH = Path(__file__).with_name("legacy_schema_spec.json")

_COLUMNS_SQL = text(
    """
    SELECT c.relname AS table_name,
           a.attname AS column_name,
           pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
           a.attnotnull AS not_null
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version'
      AND a.attnum > 0 AND NOT a.attisdropped
    ORDER BY c.relname, a.attnum
    """
)

_CONSTRAINTS_SQL = text(
    """
    SELECT c.relname AS table_name, con.contype,
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
                     ORDER BY ord.n) END AS ref_cols
    FROM pg_constraint con
    JOIN pg_class c ON con.conrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public' AND con.contype IN ('p', 'u', 'f')
      AND c.relname <> 'alembic_version'
    ORDER BY 1, 2, 3
    """
)

_INDEXES_SQL = text(
    """
    SELECT c.relname AS table_name, i.relname AS index_name, ix.indisunique
    FROM pg_index ix
    JOIN pg_class c ON ix.indrelid = c.oid
    JOIN pg_class i ON ix.indexrelid = i.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version'
    ORDER BY 1, 2
    """
)


def introspect_schema(conn) -> dict:
    """Return the structural schema of the public schema as plain data."""
    tables: dict[str, dict] = {}
    for table, column, data_type, not_null in conn.execute(_COLUMNS_SQL):
        tables.setdefault(
            table, {"columns": [], "primary_key": [], "unique": [], "fks": [], "indexes": {}}
        )["columns"].append([column, data_type, bool(not_null)])
    for table, contype, cols, ref_table, ref_cols in conn.execute(_CONSTRAINTS_SQL):
        entry = tables.setdefault(
            table, {"columns": [], "primary_key": [], "unique": [], "fks": [], "indexes": {}}
        )
        if contype == "p":
            entry["primary_key"] = list(cols)
        elif contype == "u":
            entry["unique"].append(sorted(cols))
        else:
            entry["fks"].append([list(cols), ref_table, list(ref_cols)])
    for table, index_name, is_unique in conn.execute(_INDEXES_SQL):
        tables.setdefault(
            table, {"columns": [], "primary_key": [], "unique": [], "fks": [], "indexes": {}}
        )["indexes"][index_name] = bool(is_unique)
    for entry in tables.values():
        entry["unique"] = sorted(map(list, entry["unique"]))
        entry["fks"] = sorted(entry["fks"], key=lambda f: (f[1], f[0]))
    return dict(sorted(tables.items()))


def load_legacy_spec() -> dict:
    payload = json.loads(SPEC_PATH.read_text())
    return payload["tables"]


def diff_against_spec(actual: dict, spec_tables: dict) -> list[str]:
    """Human-readable differences; empty list means exact structural match."""
    diffs: list[str] = []
    for table in sorted(set(actual) | set(spec_tables)):
        if table not in spec_tables:
            diffs.append(f"unexpected table: {table}")
            continue
        if table not in actual:
            diffs.append(f"missing table: {table}")
            continue
        a, s = actual[table], spec_tables[table]
        if a["columns"] != s["columns"]:
            a_cols = {c[0]: c for c in a["columns"]}
            s_cols = {c[0]: c for c in s["columns"]}
            for name in sorted(set(a_cols) | set(s_cols)):
                if name not in s_cols:
                    diffs.append(f"{table}: unexpected column {name}")
                elif name not in a_cols:
                    diffs.append(f"{table}: missing column {name}")
                elif a_cols[name][1:] != s_cols[name][1:]:
                    diffs.append(
                        f"{table}.{name}: type/nullable {a_cols[name][1:]} "
                        f"!= expected {s_cols[name][1:]}"
                    )
        if a["primary_key"] != s["primary_key"]:
            diffs.append(f"{table}: primary key {a['primary_key']} != expected {s['primary_key']}")
        if a["unique"] != s["unique"]:
            diffs.append(f"{table}: unique constraints {a['unique']} != expected {s['unique']}")
        if a["fks"] != s["fks"]:
            diffs.append(f"{table}: foreign keys {a['fks']} != expected {s['fks']}")
        if a["indexes"] != s["indexes"]:
            diffs.append(
                f"{table}: indexes {sorted(a['indexes'])} != expected {sorted(s['indexes'])}"
            )
    return diffs
