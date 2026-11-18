import asyncio
import threading

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_pending_bootstrap_serves_liveness_and_blocks_market(monkeypatch, session_factory):
    import app.demo as demo
    import app.main as main
    import app.db.database as database
    import app.auth.dependencies as auth
    import app.auth.routes as auth_routes

    release = threading.Event()
    entered = threading.Event()

    def blocked_seed():
        entered.set()
        assert release.wait(5), 'test must release bootstrap'

    monkeypatch.setattr(settings, 'environment', 'development')
    monkeypatch.setattr(settings, 'demo_mode', True)
    monkeypatch.setattr(main, 'init_db', lambda: None)
    monkeypatch.setattr(database, 'get_session', session_factory)
    monkeypatch.setattr(auth, 'get_session', session_factory)
    monkeypatch.setattr(auth_routes, 'get_session', session_factory)
    monkeypatch.setattr(demo, 'seed_demo_environment', blocked_seed)
    try:
        with TestClient(app) as client:
            assert entered.wait(2)
            assert client.get('/health/live').json() == {'status': 'ok'}
            response = client.get('/health/ready')
            assert response.status_code == 503
            assert response.json()['checks']['bootstrap'] == 'pending'
            response = client.get('/api/v1/stocks/AAPL/history', headers={'Origin': 'http://localhost:5173'})
            assert response.headers['Access-Control-Allow-Origin'] == 'http://localhost:5173'
            assert response.status_code == 503
            assert response.headers['Retry-After'] == '15'
            assert response.json()['error']['code'] == 'BOOTSTRAP_UNAVAILABLE'
            # Auth is alive and the demo account exists while market work waits.
            response = client.post('/api/v1/auth/login', json={
                'email': settings.demo_user_email, 'password': settings.demo_user_password})
            assert response.status_code == 200
            release.set()
    finally:
        release.set()
        app.state.bootstrap_status = 'ready'


def test_background_bootstrap_failure_is_visible_and_blocks_routes(monkeypatch):
    import app.demo as demo
    from app.main import _finish_demo_bootstrap

    def fail():
        raise RuntimeError('synthetic bootstrap failure')

    monkeypatch.setattr(demo, 'seed_demo_environment', fail)
    try:
        asyncio.run(_finish_demo_bootstrap(app))
        assert app.state.bootstrap_status == 'failed'
        client = TestClient(app)
        assert client.get('/health/live').status_code == 200
        assert client.get('/health/ready').status_code == 503
        response = client.get('/api/v1/predictions')
        assert response.status_code == 503
        assert 'Retry-After' not in response.headers
    finally:
        app.state.bootstrap_status = 'ready'


def test_completed_bootstrap_releases_normal_auth_checks(monkeypatch):
    import app.demo as demo
    from app.main import _finish_demo_bootstrap

    monkeypatch.setattr(demo, 'seed_demo_environment', lambda: None)
    asyncio.run(_finish_demo_bootstrap(app))
    assert app.state.bootstrap_status == 'ready'
    response = TestClient(app).get('/api/v1/predictions')
    assert response.status_code == 401


def test_readiness_returns_unavailable_for_failed_dependency(monkeypatch):
    import app.main as main

    class BrokenEngine:
        def connect(self):
            raise RuntimeError('synthetic unavailable DB')

    monkeypatch.setattr(main, 'engine', BrokenEngine())
    app.state.bootstrap_status = 'ready'
    response = TestClient(app).get('/health/ready')
    assert response.status_code == 503
    assert response.json()['checks']['database'] == 'unavailable'


def test_initial_database_failure_is_visible_not_silent(monkeypatch):
    import app.main as main

    def fail():
        raise RuntimeError('synthetic init failure')

    monkeypatch.setattr(settings, 'environment', 'development')
    monkeypatch.setattr(settings, 'demo_mode', False)
    monkeypatch.setattr(main, 'init_db', fail)
    try:
        with TestClient(app) as client:
            assert client.get('/health/live').status_code == 200
            assert client.get('/health/ready').status_code == 503
            assert client.get('/api/v1/predictions').status_code == 503
    finally:
        app.state.bootstrap_status = 'ready'


def test_production_never_starts_demo_bootstrap(monkeypatch):
    import app.main as main
    import app.demo as demo

    monkeypatch.setattr(settings, 'environment', 'production')
    monkeypatch.setattr(settings, 'demo_mode', True)
    monkeypatch.setattr(main, 'init_db', lambda: (_ for _ in ()).throw(AssertionError('production init_db')))
    monkeypatch.setattr(demo, 'seed_demo_environment', lambda: (_ for _ in ()).throw(AssertionError('production demo')))
    with TestClient(app) as client:
        assert app.state.bootstrap_status == 'ready'
        assert client.get('/health/live').status_code == 200
        assert client.get('/api/v1/predictions').status_code == 401
