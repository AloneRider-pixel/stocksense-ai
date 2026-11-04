from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.db.models import AlertRule, MarketBarRecord, Notification


def _bar(session, symbol, day, close):
    session.add(
        MarketBarRecord(
            symbol=symbol,
            date=day,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
            source_provider="test",
        )
    )
    session.commit()


def test_alerts_require_auth(client):
    assert client.get("/api/v1/alerts").status_code == 401
    assert client.post("/api/v1/alerts", json={}).status_code == 401
    assert client.get("/api/v1/notifications").status_code == 401


def test_create_and_list_rule(client, auth_headers):
    headers, _user = auth_headers
    response = client.post(
        "/api/v1/alerts",
        json={"symbol": "reliance", "direction": "above", "target_price": "2500"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["symbol"] == "RELIANCE"
    assert body["direction"] == "above"
    assert body["target_price"] == "2500.0000"
    assert body["active"] is True

    listed = client.get("/api/v1/alerts", headers=headers)
    assert listed.status_code == 200
    rules = listed.json()["rules"]
    assert len(rules) == 1
    assert rules[0]["id"] == body["id"]


def test_create_rule_sets_baseline_from_latest_bar(client, auth_headers, session_factory):
    headers, _user = auth_headers
    session = session_factory()
    _bar(session, "RELIANCE", date(2026, 10, 29), 2450)
    _bar(session, "RELIANCE", date(2026, 10, 30), 2600)
    session.close()
    response = client.post(
        "/api/v1/alerts",
        json={"symbol": "RELIANCE", "direction": "above", "target_price": "2500"},
        headers=headers,
    )
    assert response.status_code == 201
    # history already past target -> baseline pinned to latest bar, no backfill,
    # and the baseline is not presented as a trigger
    assert response.json()["baseline_bar_date"] == "2026-10-30"
    assert response.json()["last_triggered_bar_date"] is None


def test_create_rule_rejects_bad_input(client, auth_headers):
    headers, _user = auth_headers
    for payload, code in (
        ({"symbol": "RELIANCE", "direction": "up", "target_price": "100"}, "BAD_DIRECTION"),
        ({"symbol": "RELIANCE", "direction": "above", "target_price": "0"}, "BAD_TARGET"),
        ({"symbol": "RELIANCE", "direction": "above", "target_price": "abc"}, "BAD_TARGET"),
        ({"symbol": "NOPE123", "direction": "above", "target_price": "100"}, "UNKNOWN_SYMBOL"),
    ):
        response = client.post("/api/v1/alerts", json=payload, headers=headers)
        assert response.status_code == 422, payload
        assert response.json()["error"]["code"] == code


def test_deactivate_rule(client, auth_headers):
    headers, _user = auth_headers
    created = client.post(
        "/api/v1/alerts",
        json={"symbol": "TCS", "direction": "below", "target_price": "4000"},
        headers=headers,
    )
    rule_id = created.json()["id"]
    response = client.post(f"/api/v1/alerts/{rule_id}/deactivate", headers=headers)
    assert response.status_code == 200
    assert response.json()["active"] is False


def test_deactivate_other_users_rule_404(client, auth_headers, session_factory):
    from app.auth.service import AuthService

    session = session_factory()
    other = AuthService(session).register(
        email="other@example.com", password="sup3r-secret", full_name="Other"
    )
    rule = AlertRule(
        user_id=other.id,
        symbol="TCS",
        direction="below",
        target_price=Decimal("4000"),
        active=True,
    )
    session.add(rule)
    session.commit()
    rule_id = rule.id
    session.close()
    headers, _user = auth_headers
    response = client.post(f"/api/v1/alerts/{rule_id}/deactivate", headers=headers)
    assert response.status_code == 404


def test_notifications_list_and_mark_seen(client, auth_headers, session_factory):
    headers, user = auth_headers
    session = session_factory()
    note = Notification(
        user_id=user.id,
        kind="price_alert",
        title="RELIANCE crossed above 2500",
        body="RELIANCE closed at 2510.",
        seen=False,
    )
    session.add(note)
    session.commit()
    note_id = note.id
    session.close()

    listed = client.get("/api/v1/notifications", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["unseen_count"] == 1
    assert body["notifications"][0]["id"] == note_id
    assert body["notifications"][0]["seen"] is False

    seen = client.post(f"/api/v1/notifications/{note_id}/seen", headers=headers)
    assert seen.status_code == 200
    assert seen.json()["seen"] is True

    listed = client.get("/api/v1/notifications", headers=headers)
    assert listed.json()["unseen_count"] == 0


def test_mark_other_users_notification_seen_404(client, auth_headers, session_factory):
    from app.auth.service import AuthService

    session = session_factory()
    other = AuthService(session).register(
        email="other2@example.com", password="sup3r-secret", full_name="Other Two"
    )
    note = Notification(
        user_id=other.id, kind="price_alert", title="t", body="b", seen=False
    )
    session.add(note)
    session.commit()
    note_id = note.id
    session.close()
    headers, _user = auth_headers
    response = client.post(f"/api/v1/notifications/{note_id}/seen", headers=headers)
    assert response.status_code == 404
