from __future__ import annotations

import pytest

from app.core.config import settings


@pytest.fixture()
def demo_session(session_factory, monkeypatch):
    import app.demo as demo

    monkeypatch.setattr(demo, "get_session", session_factory)
    monkeypatch.setattr(demo, "init_db", lambda: None)
    monkeypatch.setattr(settings, "demo_mode", True)
    return session_factory


def test_seed_demo_environment_is_idempotent(demo_session, monkeypatch, tmp_path):
    import app.demo as demo

    monkeypatch.setattr(demo, "_ensure_sample_model", lambda: None)
    monkeypatch.setattr(settings, "environment", "development")

    demo.seed_demo_environment()
    demo.seed_demo_environment()

    session = demo_session()
    try:
        from app.auth.service import AuthService
        from app.db.repository import MarketDataRepository

        user = AuthService(session).authenticate(
            email=settings.demo_user_email,
            password=settings.demo_user_password,
        )
        assert user.is_active is True

        bars = MarketDataRepository(session).list_history("DEMO", limit=5000)
        assert len(bars) > 80
    finally:
        session.close()


def test_seed_demo_environment_skips_production(demo_session, monkeypatch):
    import app.demo as demo

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(
        demo,
        "init_db",
        lambda: pytest.fail("init_db must not run in production"),
    )

    demo.seed_demo_environment()
