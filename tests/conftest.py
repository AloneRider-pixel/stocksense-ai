from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.service import AuthService
from app.db.models import Base


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def client(monkeypatch, session_factory):
    import app.api.routes as api_routes
    import app.auth.dependencies as auth_dependencies
    import app.auth.routes as auth_routes

    for module in (api_routes, auth_routes, auth_dependencies):
        monkeypatch.setattr(module, "get_session", session_factory)

    from app.main import app

    return TestClient(app)


@pytest.fixture()
def auth_headers(session_factory):
    session = session_factory()
    try:
        user = AuthService(session).register(
            email="trader@example.com",
            password="sup3r-secret",
            full_name="Test Trader",
        )
        token = AuthService.issue_token(user)
        return {"Authorization": f"Bearer {token}"}, user
    finally:
        session.close()
