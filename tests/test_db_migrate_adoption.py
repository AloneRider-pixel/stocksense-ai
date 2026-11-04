"""Alembic adoption gate on real Postgres.

Covers the production adoption path: databases created by the legacy
create_all startup carry no alembic_version row. The startup entrypoint
(python -m app.db.migrate) must stamp the pre-migration head only on an exact
structural match, apply the remaining migrations without touching data, and
fail closed - leaving the database untouched - on drifted, partial, or
unknown schemas. Skipped unless STOCKSENSE_TEST_PG_DSN is set.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from sqlalchemy import create_engine, text

DSN = os.environ.get("STOCKSENSE_TEST_PG_DSN")

pytestmark = pytest.mark.skipif(
    not DSN, reason="STOCKSENSE_TEST_PG_DSN not set - needs a scratch Postgres"
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY_TABLES = {
    "users",
    "prediction_records",
    "market_bars",
    "scanner_bars",
    "scanner_runs",
    "scanner_signals",
    "watchlist_items",
}
V2_TABLES = {
    "paper_accounts",
    "paper_orders",
    "paper_positions",
    "paper_equity_snapshots",
    "alert_rules",
    "notifications",
}


def _admin_url() -> str:
    return DSN.replace("+psycopg", "") if DSN else ""


def _scratch_db() -> str:
    name = "adopt_" + uuid.uuid4().hex[:12]
    with psycopg.connect(_admin_url(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    return name


def _drop_db(name: str) -> None:
    with psycopg.connect(_admin_url(), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _db_url(name: str) -> str:
    base, sep, query = DSN.partition("?")
    path_base, _, _ = base.rpartition("/")
    url = f"{path_base}/{name}"
    return f"{url}?{query}" if sep else url


def _migrate(db_url: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=db_url)
    return subprocess.run(
        [sys.executable, "-m", "app.db.migrate"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _tables(db_url: str) -> set[str]:
    with psycopg.connect(db_url.replace("+psycopg", "")) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    return {r[0] for r in rows}


def _versions(db_url: str) -> list[str]:
    with psycopg.connect(db_url.replace("+psycopg", "")) as conn:
        reg = conn.execute("SELECT to_regclass('public.alembic_version')").fetchone()[0]
        if not reg:
            return []
        return [r[0] for r in conn.execute("SELECT version_num FROM alembic_version")]


def _create_legacy_schema(db_url: str) -> None:
    from app.db.legacy_models_snapshot import Base

    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def scratch_db():
    name = _scratch_db()
    yield name, _db_url(name)
    _drop_db(name)


def test_empty_database_upgrades_to_head(scratch_db):
    _, db_url = scratch_db
    result = _migrate(db_url)
    assert result.returncode == 0, result.stderr
    assert _versions(db_url) == ["0008_align_legacy_defaults"]
    assert LEGACY_TABLES | V2_TABLES <= _tables(db_url)


def test_exact_legacy_schema_is_adopted_and_data_preserved(scratch_db):
    _, db_url = scratch_db
    _create_legacy_schema(db_url)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, full_name, is_active, created_at)"
                " VALUES ('owner@example.com', 'hash', 'Owner', true, now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO watchlist_items (user_id, symbol, created_at)"
                " VALUES (1, 'RELIANCE', now())"
            )
        )
    engine.dispose()

    result = _migrate(db_url)
    assert result.returncode == 0, result.stderr
    assert _versions(db_url) == ["0008_align_legacy_defaults"]
    tables = _tables(db_url)
    assert LEGACY_TABLES | V2_TABLES <= tables
    with psycopg.connect(db_url.replace("+psycopg", "")) as conn:
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 1
        assert (
            conn.execute("SELECT symbol FROM watchlist_items WHERE user_id = 1").fetchone()[0]
            == "RELIANCE"
        )


def test_adoption_is_idempotent_on_restart(scratch_db):
    _, db_url = scratch_db
    _create_legacy_schema(db_url)
    assert _migrate(db_url).returncode == 0
    second = _migrate(db_url)
    assert second.returncode == 0, second.stderr
    assert _versions(db_url) == ["0008_align_legacy_defaults"]


def test_drifted_legacy_schema_fails_closed(scratch_db):
    """A legacy database missing a column must not be stamped or migrated."""
    _, db_url = scratch_db
    _create_legacy_schema(db_url)
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as conn:
        conn.execute("ALTER TABLE users DROP COLUMN full_name")

    result = _migrate(db_url)
    assert result.returncode == 2
    assert "missing column full_name" in result.stderr
    assert _versions(db_url) == []  # no stamp written
    assert not V2_TABLES & _tables(db_url)  # no v2 tables created


def test_extra_table_fails_closed(scratch_db):
    """Unknown tables mean unknown provenance: manual review, not a stamp."""
    _, db_url = scratch_db
    _create_legacy_schema(db_url)
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as conn:
        conn.execute("CREATE TABLE unexpected_audit (id integer)")

    result = _migrate(db_url)
    assert result.returncode == 2
    assert "unexpected table: unexpected_audit" in result.stderr
    assert _versions(db_url) == []
    assert not V2_TABLES & _tables(db_url)


def test_partial_legacy_schema_fails_closed(scratch_db):
    _, db_url = scratch_db
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE users (id serial PRIMARY KEY, email varchar(320) NOT NULL,"
            " password_hash varchar(512) NOT NULL)"
        )

    result = _migrate(db_url)
    assert result.returncode == 2
    assert "missing table:" in result.stderr
    assert _versions(db_url) == []


def test_empty_version_table_treated_as_unversioned(scratch_db):
    """A leftover empty alembic_version table must not skip the gate."""
    _, db_url = scratch_db
    _create_legacy_schema(db_url)
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num varchar(32) NOT NULL)")

    result = _migrate(db_url)
    assert result.returncode == 0, result.stderr
    assert _versions(db_url) == ["0008_align_legacy_defaults"]
    assert V2_TABLES <= _tables(db_url)


def test_versioned_database_upgrades_without_gate(scratch_db):
    _, db_url = scratch_db
    env = dict(os.environ, DATABASE_URL=db_url)
    assert (
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "0003_scanner_bars"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        ).returncode
        == 0
    )
    result = _migrate(db_url)
    assert result.returncode == 0, result.stderr
    assert _versions(db_url) == ["0008_align_legacy_defaults"]
    assert V2_TABLES <= _tables(db_url)


def test_failed_adoption_can_be_retried_after_fix(scratch_db):
    _, db_url = scratch_db
    _create_legacy_schema(db_url)
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as conn:
        conn.execute("ALTER TABLE users DROP COLUMN full_name")
    assert _migrate(db_url).returncode == 2
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as conn:
        conn.execute("ALTER TABLE users ADD COLUMN full_name varchar(120)")
    result = _migrate(db_url)
    assert result.returncode == 0, result.stderr
    assert _versions(db_url) == ["0008_align_legacy_defaults"]


def test_concurrent_adoption_is_serialized(scratch_db):
    """Two containers starting at once must not race the stamp or upgrade."""
    _, db_url = scratch_db
    _create_legacy_schema(db_url)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, full_name, is_active, created_at)"
                " VALUES ('owner@example.com', 'hash', 'Owner', true, now())"
            )
        )
    engine.dispose()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_migrate, [db_url, db_url]))
    for result in results:
        assert result.returncode == 0, result.stderr
    assert _versions(db_url) == ["0008_align_legacy_defaults"]
    assert V2_TABLES <= _tables(db_url)
    with psycopg.connect(db_url.replace("+psycopg", "")) as conn:
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 1


def _introspect(db_url: str) -> dict:
    from app.db.schema_spec import introspect_schema

    engine = create_engine(db_url)
    with engine.connect() as conn:
        schema = introspect_schema(conn)
    engine.dispose()
    return schema


def test_fresh_and_adopted_final_schemas_match():
    """Fresh install and adopted legacy database must converge to one schema."""
    fresh = _scratch_db()
    adopted = _scratch_db()
    try:
        fresh_url, adopted_url = _db_url(fresh), _db_url(adopted)
        assert _migrate(fresh_url).returncode == 0
        _create_legacy_schema(adopted_url)
        assert _migrate(adopted_url).returncode == 0
        fresh_schema = _introspect(fresh_url)
        adopted_schema = _introspect(adopted_url)

        def normalized(schema: dict) -> dict:
            # Column ordinal position differs between the migration and
            # create_all histories (prediction_records); it is semantically
            # meaningless, so compare columns name-keyed.
            out = {"tables": {}, "extensions": schema["extensions"]}
            for name, entry in schema["tables"].items():
                e = dict(entry)
                e["columns"] = sorted(e["columns"], key=lambda c: c[0])
                out["tables"][name] = e
            return out

        assert normalized(fresh_schema) == normalized(adopted_schema)
    finally:
        _drop_db(fresh)
        _drop_db(adopted)


def test_watchlist_roundtrip_on_fresh_install(scratch_db):
    """The fresh-install path (migration-created table) serves watchlist ops."""
    _, db_url = scratch_db
    assert _migrate(db_url).returncode == 0
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, full_name, is_active, created_at)"
                " VALUES ('owner@example.com', 'hash', 'Owner', true, now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO watchlist_items (user_id, symbol, created_at)"
                " VALUES (1, 'RELIANCE', now())"
            )
        )
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT symbol FROM watchlist_items WHERE user_id = 1")).fetchall()
    assert [r[0] for r in rows] == ["RELIANCE"]
    # unique constraint from the model is enforced (separate transaction: an
    # open writer would deadlock the duplicate insert's unique-index check)
    with pytest.raises(Exception), engine.begin() as dup:
        dup.execute(
            text(
                "INSERT INTO watchlist_items (user_id, symbol, created_at)"
                " VALUES (1, 'RELIANCE', now())"
            )
        )
    engine.dispose()


def test_0007_creates_watchlist_for_migration_only_databases(scratch_db):
    """A database versioned at 0003 (no watchlist table) gains it via 0007."""
    _, db_url = scratch_db
    env = dict(os.environ, DATABASE_URL=db_url)
    assert (
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "0003_scanner_bars"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        ).returncode
        == 0
    )
    assert "watchlist_items" not in _tables(db_url)
    result = _migrate(db_url)
    assert result.returncode == 0, result.stderr
    assert "watchlist_items" in _tables(db_url)
    assert _versions(db_url) == ["0008_align_legacy_defaults"]


def test_0007_fails_loudly_on_drifted_watchlist(scratch_db):
    """Versioned database with a drifted watchlist: verify, never hide."""
    _, db_url = scratch_db
    env = dict(os.environ, DATABASE_URL=db_url)
    assert (
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "0003_scanner_bars"],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        ).returncode
        == 0
    )
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE watchlist_items (id serial PRIMARY KEY,"
            " user_id integer NOT NULL, symbol varchar(64) NOT NULL,"
            " created_at timestamptz NOT NULL)"
        )
    result = _migrate(db_url)
    assert result.returncode != 0
    assert "does not match the expected legacy schema" in result.stderr
    assert _versions(db_url) == ["0003_scanner_bars"]  # chain halted before 0007


def test_advisory_lock_held_during_adoption(scratch_db):
    """A second connection must observe the advisory lock while migrate runs."""
    import time

    _, db_url = scratch_db
    _create_legacy_schema(db_url)
    env = dict(os.environ, DATABASE_URL=db_url)
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.db.migrate"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    key = 862_414_421
    seen = False
    deadline = time.time() + 90
    try:
        with psycopg.connect(db_url.replace("+psycopg", "")) as conn:
            while proc.poll() is None and time.time() < deadline:
                row = conn.execute(
                    "SELECT 1 FROM pg_locks WHERE locktype = 'advisory'"
                    " AND classid = %s AND objid = %s",
                    ((key >> 32) & 0xFFFFFFFF, key & 0xFFFFFFFF),
                ).fetchone()
                if row:
                    seen = True
                    break
                time.sleep(0.025)
    finally:
        out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    assert seen, "advisory lock was never observed during adoption"
