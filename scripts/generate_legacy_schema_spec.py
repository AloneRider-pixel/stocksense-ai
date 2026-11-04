"""Regenerate app/db/legacy_schema_spec.json from the legacy models snapshot.

Creates the legacy schema with Base.metadata.create_all() from
app/db/legacy_models_snapshot.py (the exact models of the last pre-migration
deploy, commit 8d4faef) on a scratch Postgres database, introspects it with
app.db.schema_spec, and writes the spec the adoption gate compares against.

Usage: STOCKSENSE_SPEC_PG_DSN=postgresql+psycopg://postgres:postgres@localhost:5432/postgres \
       python scripts/generate_legacy_schema_spec.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import psycopg
from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.db.legacy_models_snapshot import Base  # noqa: E402
from app.db.schema_spec import SPEC_PATH, introspect_schema  # noqa: E402

DSN = os.environ.get("STOCKSENSE_SPEC_PG_DSN")
if not DSN:
    sys.exit("STOCKSENSE_SPEC_PG_DSN not set - needs a scratch Postgres")

admin_url = DSN.replace("+psycopg", "")
name = "specgen_" + uuid.uuid4().hex[:12]
with psycopg.connect(admin_url, autocommit=True) as conn:
    conn.execute(f'CREATE DATABASE "{name}"')
try:
    base, sep, query = DSN.partition("?")
    path_base, _, _ = base.rpartition("/")
    engine = create_engine(f"{path_base}/{name}" + (f"?{query}" if sep else ""))
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        schema = introspect_schema(conn)
    engine.dispose()
finally:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')

payload = {
    "generated_from": (
        "app/db/legacy_models_snapshot.py (model definitions byte-identical to "
        "app/db/models.py at commit 8d4faef, the last pre-migration deploy) via "
        "Base.metadata.create_all()"
    ),
    "generated_by": "scripts/generate_legacy_schema_spec.py",
    "verified_against_production": (
        "matches the live database introspection (PostgreSQL 18.6, Neon project "
        "stocksense-ai) taken read-only via the owner console on 2026-11-04"
    ),
    "schema": schema,
}
SPEC_PATH.write_text(json.dumps(payload, indent=2) + "\n")
print(f"wrote {SPEC_PATH} with {len(schema['tables'])} tables: {sorted(schema['tables'])}")
