"""Startup migration entrypoint with safe alembic adoption.

Production databases predate alembic: they were created by the app's old
Base.metadata.create_all() startup and carry no alembic_version row, so a
blind `alembic upgrade head` starts at the base revision and crashes on
DuplicateTable (observed on the first deploy attempt). This entrypoint runs
instead of bare alembic at container start:

- a database already versioned by alembic upgrades to head normally;
- an empty database upgrades to head (fresh install);
- an unversioned database with tables is adopted only when its structure
  exactly matches the committed legacy schema spec (the create_all schema of
  the last pre-migration deploy): it is stamped at the pre-migration head and
  then upgraded. No rows are modified; stamping writes only alembic_version.
- any other state (drifted, partial, or unknown schema) fails closed with a
  non-zero exit and a printed diff. The deploy is cancelled and the previous
  version keeps serving; no destructive action is ever taken here.

A Postgres advisory lock serializes concurrent container starts so two
instances can never race the adoption or the upgrade.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.db.schema_spec import (
    LEGACY_HEAD_REVISION,
    diff_against_spec,
    introspect_schema,
    load_legacy_spec,
)

logger = logging.getLogger("stocksense.db.migrate")

ADVISORY_LOCK_KEY = 862_414_421

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _alembic_config(url: str) -> Config:
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _run_locked(conn, url: str) -> int:
    cfg = _alembic_config(url)

    version_table = conn.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
    versions: list[str] = []
    if version_table:
        versions = [r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))]
    if versions:
        logger.info("alembic_version at %s; upgrading to head", versions)
        command.upgrade(cfg, "head")
        return 0

    tables = {
        r[0]
        for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    } - {"alembic_version"}

    if not tables:
        logger.info("empty database; running full upgrade to head")
        command.upgrade(cfg, "head")
        return 0

    logger.info(
        "unversioned database with tables %s; verifying against legacy spec", sorted(tables)
    )
    diffs = diff_against_spec(introspect_schema(conn), load_legacy_spec())
    if diffs:
        message = (
            "Database has tables but does not match the legacy pre-migration schema; "
            "refusing to stamp a baseline. Failing closed: no migration ran, no data "
            "changed. Differences:\n" + json.dumps(diffs, indent=2)
        )
        logger.error(message)
        print(message, file=sys.stderr)
        return 2

    logger.info(
        "schema matches legacy spec; stamping %s and upgrading to head", LEGACY_HEAD_REVISION
    )
    command.stamp(cfg, LEGACY_HEAD_REVISION)
    command.upgrade(cfg, "head")
    return 0


def run() -> int:
    url = settings.database_url
    if url.startswith("sqlite"):
        command.upgrade(_alembic_config(url), "head")
        return 0

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
            try:
                return _run_locked(conn, url)
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY})
    finally:
        engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(run())


if __name__ == "__main__":
    main()
