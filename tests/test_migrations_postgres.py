"""Migration lifecycle on real Postgres: empty DB, upgrade from the previous
production head (0003), idempotent re-run, and fail-closed startup when the
database is unreachable. Skipped unless STOCKSENSE_TEST_PG_DSN is set."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid

import psycopg
import pytest

DSN = os.environ.get("STOCKSENSE_TEST_PG_DSN")

pytestmark = pytest.mark.skipif(
    not DSN, reason="STOCKSENSE_TEST_PG_DSN not set - needs a scratch Postgres"
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _admin_url() -> str:
    return DSN.replace("+psycopg", "") if DSN else ""


def _scratch_db() -> str:
    """Create a uniquely named scratch database and return its name."""
    name = "migtest_" + uuid.uuid4().hex[:12]
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


def _alembic(db_url: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=db_url)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _tables(db_url: str) -> set[str]:
    with psycopg.connect(db_url.replace("+psycopg", "")) as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    return {r[0] for r in rows}


@pytest.fixture()
def scratch_db():
    name = _scratch_db()
    yield name, _db_url(name)
    _drop_db(name)


def test_upgrade_head_on_empty_database(scratch_db):
    _, db_url = scratch_db
    result = _alembic(db_url, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    tables = _tables(db_url)
    for expected in (
        "users",
        "market_bars",
        "scanner_bars",
        "paper_accounts",
        "paper_positions",
        "paper_orders",
        "paper_equity_snapshots",
        "alert_rules",
        "notifications",
    ):
        assert expected in tables, f"missing table {expected}"
    with psycopg.connect(db_url.replace("+psycopg", "")) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    assert version[0] == "0006_alert_rule_baseline"


def test_upgrade_from_previous_production_head(scratch_db):
    """An existing 0003 database (pre-wallet schema) upgrades cleanly."""
    _, db_url = scratch_db
    result = _alembic(db_url, "upgrade", "0003_scanner_bars")
    assert result.returncode == 0, result.stderr
    assert "paper_accounts" not in _tables(db_url)
    result = _alembic(db_url, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    tables = _tables(db_url)
    assert "paper_accounts" in tables
    assert "alert_rules" in tables


def test_upgrade_head_is_idempotent(scratch_db):
    """Re-running at container restart is a no-op, not an error."""
    _, db_url = scratch_db
    assert _alembic(db_url, "upgrade", "head").returncode == 0
    second = _alembic(db_url, "upgrade", "head")
    assert second.returncode == 0, second.stderr


def test_failed_migration_aborts_startup():
    """The container start command must not boot the server when migration
    fails: `python -m app.db.migrate && uvicorn ...` exits non-zero and never
    reaches the server."""
    bad_url = "postgresql+psycopg://postgres:wrong@127.0.0.1:1/never"
    result = subprocess.run(
        ["sh", "-c", f"{sys.executable} -m app.db.migrate && echo SERVER_BOOTED"],
        cwd=REPO_ROOT,
        env=dict(os.environ, DATABASE_URL=bad_url),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "SERVER_BOOTED" not in result.stdout


def test_bare_postgres_scheme_is_normalized():
    from app.core.config import Settings

    for bare, qualified in (
        ("postgres://u:p@db.example:5432/app", "postgresql+psycopg://u:p@db.example:5432/app"),
        ("postgresql://u:p@db.example:5432/app", "postgresql+psycopg://u:p@db.example:5432/app"),
    ):
        s = Settings(database_url=bare, jwt_secret="x" * 32)
        assert s.database_url == qualified
    untouched = Settings(
        database_url="sqlite:////tmp/x.db", jwt_secret="x" * 32
    )
    assert untouched.database_url == "sqlite:////tmp/x.db"
