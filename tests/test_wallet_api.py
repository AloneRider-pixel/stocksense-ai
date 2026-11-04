from __future__ import annotations

from datetime import date

from app.auth.service import AuthService
from app.db.models import MarketBarRecord


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


def test_wallet_requires_auth(client):
    assert client.get("/api/v1/wallet").status_code == 401
    assert client.post("/api/v1/wallet/orders", json={}).status_code == 401
    assert client.post("/api/v1/wallet/reset").status_code == 401


def test_new_wallet_starts_with_virtual_cash(client, auth_headers):
    headers, _user = auth_headers
    response = client.get("/api/v1/wallet", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["cash"] == "1000000.00"
    assert body["positions"] == []
    assert body["simulation"] == "paper-trading"


def test_place_order_fill_then_summary(client, auth_headers, session_factory):
    headers, _user = auth_headers
    _bar(session_factory(), "RELIANCE", date(2026, 10, 30), 100.0)

    response = client.post(
        "/api/v1/wallet/orders",
        headers=headers,
        json={"symbol": "reliance", "side": "buy", "quantity": 10},
    )
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "filled"
    assert order["fill_price"] == "100.0000"
    assert order["fill_bar_date"] == "2026-10-30"
    assert order["simulation"] == "paper-trading"

    summary = client.get("/api/v1/wallet", headers=headers).json()
    assert summary["cash"] == "999000.00"
    assert summary["positions"][0]["quantity"] == 10

    orders = client.get("/api/v1/wallet/orders", headers=headers).json()["orders"]
    assert len(orders) == 1
    assert orders[0]["id"] == order["id"]


def test_rejected_order_is_returned_with_code(client, auth_headers, session_factory):
    headers, _user = auth_headers
    _bar(session_factory(), "INFY", date(2026, 10, 30), 50.0)

    response = client.post(
        "/api/v1/wallet/orders",
        headers=headers,
        json={"symbol": "TATAMOTORS", "side": "buy", "quantity": 1},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "rejected"
    assert body["reject_code"] == "NO_STORED_PRICE"


def test_invalid_inputs_are_422(client, auth_headers, session_factory):
    headers, _user = auth_headers
    _bar(session_factory(), "RELIANCE", date(2026, 10, 30), 100.0)

    for payload in (
        {"symbol": "GOLD", "side": "buy", "quantity": 1},
        {"symbol": "USDINR", "side": "buy", "quantity": 1},
        {"symbol": "RELIANCE", "side": "hold", "quantity": 1},
        {"symbol": "RELIANCE", "side": "buy", "quantity": 0},
        {"symbol": "RELIANCE", "side": "buy", "quantity": -2},
    ):
        response = client.post("/api/v1/wallet/orders", headers=headers, json=payload)
        assert response.status_code == 422, payload


def test_double_submit_is_idempotent(client, auth_headers, session_factory):
    headers, _user = auth_headers
    _bar(session_factory(), "RELIANCE", date(2026, 10, 30), 100.0)

    payload = {
        "symbol": "RELIANCE",
        "side": "buy",
        "quantity": 10,
        "client_order_id": "tap-1",
    }
    first = client.post("/api/v1/wallet/orders", headers=headers, json=payload).json()
    second = client.post("/api/v1/wallet/orders", headers=headers, json=payload).json()
    assert first["id"] == second["id"]
    summary = client.get("/api/v1/wallet", headers=headers).json()
    assert summary["cash"] == "999000.00"
    assert summary["positions"][0]["quantity"] == 10


def test_reset_clears_wallet(client, auth_headers, session_factory):
    headers, _user = auth_headers
    _bar(session_factory(), "RELIANCE", date(2026, 10, 30), 100.0)
    client.post(
        "/api/v1/wallet/orders",
        headers=headers,
        json={"symbol": "RELIANCE", "side": "buy", "quantity": 10},
    )

    response = client.post("/api/v1/wallet/reset", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["cash"] == "1000000.00"
    assert body["positions"] == []
    assert client.get("/api/v1/wallet/orders", headers=headers).json()["orders"] == []


def test_equity_history_after_fill(client, auth_headers, session_factory):
    headers, _user = auth_headers
    _bar(session_factory(), "RELIANCE", date(2026, 10, 30), 100.0)
    client.post(
        "/api/v1/wallet/orders",
        headers=headers,
        json={"symbol": "RELIANCE", "side": "buy", "quantity": 10},
    )

    body = client.get("/api/v1/wallet/equity", headers=headers).json()
    assert body["simulation"] == "paper-trading"
    assert len(body["snapshots"]) == 1
    assert body["snapshots"][0]["equity"] == "1000000.00"
    assert body["snapshots"][0]["as_of"] == "2026-10-30"


def test_users_cannot_see_each_others_wallet(client, session_factory):
    session = session_factory()
    user_a = AuthService(session).register(
        email="a@example.com", password="sup3r-secret", full_name="A"
    )
    user_b = AuthService(session).register(
        email="b@example.com", password="sup3r-secret", full_name="B"
    )
    token_a = AuthService.issue_token(user_a)
    token_b = AuthService.issue_token(user_b)
    _bar(session, "RELIANCE", date(2026, 10, 30), 100.0)

    client.post(
        "/api/v1/wallet/orders",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"symbol": "RELIANCE", "side": "buy", "quantity": 10},
    )
    summary_b = client.get(
        "/api/v1/wallet", headers={"Authorization": f"Bearer {token_b}"}
    ).json()
    assert summary_b["cash"] == "1000000.00"
    assert summary_b["positions"] == []
