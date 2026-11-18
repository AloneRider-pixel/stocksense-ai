from datetime import date, datetime, timezone

from app.db.models import MarketBarRecord


def test_data_health_requires_authentication(client):
    response = client.get('/api/v1/data-health')
    assert response.status_code in (401, 403)


def test_data_health_reports_missing_not_zero(client, auth_headers, session_factory, monkeypatch):
    import app.api.data_health_routes as route
    monkeypatch.setattr(route, 'get_session', session_factory)
    headers, _ = auth_headers
    response = client.get('/api/v1/data-health', headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data['stored_sources'] == []
    assert data['live_quotes_verified'] is False
    assert data['headline_collector'] == 'local_candidate_not_connected'
    assert any(source['id'] == 'bse' and source['collection'] == 'written_consent_required'
               for source in data['source_policies'])


def test_data_health_uses_stored_evidence_without_provider_calls(client, auth_headers, session_factory, monkeypatch):
    import app.api.data_health_routes as route
    monkeypatch.setattr(route, 'get_session', session_factory)
    with session_factory() as session:
        for symbol in ['AAA', 'BBB']:
            session.add(MarketBarRecord(symbol=symbol, date=date(2026, 11, 17), open=100,
                high=110, low=90, close=105, volume=100, source_provider='yfinance_nse',
                ingested_at=datetime(2026, 11, 18, 12, tzinfo=timezone.utc)))
        session.commit()
    headers, _ = auth_headers
    data = client.get('/api/v1/data-health', headers=headers).json()
    source = data['stored_sources'][0]
    assert source['stored_rows'] == 2
    assert source['symbols'] == 2
    assert source['latest_session'] == '2026-11-17'
    assert source['public_display'] == 'not_cleared'
    assert source['freshness'] == 'unverified_calendar_not_integrated'
    with session_factory() as session:
        assert session.query(MarketBarRecord).count() == 2
