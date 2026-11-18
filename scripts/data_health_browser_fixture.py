"""Local browser integration fixture. Synthetic records only; no provider network calls."""
import os
from datetime import date, datetime, timezone
from pathlib import Path

import uvicorn

from app.auth.service import AuthService
from app.db.database import get_session, init_db
from app.db.models import MarketBarRecord, User

init_db()
with get_session() as session:
    user = User(email="synthetic-fixture@example.com", password_hash="unusable-fixture-hash", full_name="Synthetic integration fixture", is_active=True)
    session.add(user)
    session.flush()
    session.add(MarketBarRecord(symbol="FIXTURE", date=date(2026, 11, 10), open=100,
        high=110, low=90, close=105, volume=100, source_provider="synthetic-local-integration",
        ingested_at=datetime(2026, 11, 18, 12, tzinfo=timezone.utc)))
    session.commit()
    Path(os.environ["FIXTURE_TOKEN_PATH"]).write_text(AuthService.issue_token(user))

uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
