from __future__ import annotations


def register_payload(**overrides):
    payload = {
        "email": "new.user@example.com",
        "password": "sup3r-secret",
        "full_name": "New User",
    }
    payload.update(overrides)
    return payload


def test_register_creates_account(client):
    response = client.post("/api/v1/auth/register", json=register_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"
    assert body["full_name"] == "New User"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_email(client):
    client.post("/api/v1/auth/register", json=register_payload())

    response = client.post("/api/v1/auth/register", json=register_payload())

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTRATION_FAILED"


def test_register_normalizes_email_case(client):
    client.post("/api/v1/auth/register", json=register_payload(email="Mixed@Example.com"))

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "mixed@example.com", "password": "sup3r-secret"},
    )

    assert response.status_code == 200


def test_login_issues_bearer_token(client):
    client.post("/api/v1/auth/register", json=register_payload())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "new.user@example.com", "password": "sup3r-secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0


def test_login_rejects_wrong_password(client):
    client.post("/api/v1/auth/register", json=register_payload())

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "new.user@example.com", "password": "wr0ng-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_rejects_unknown_email(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "sup3r-secret"},
    )

    assert response.status_code == 401


def test_me_returns_authenticated_user(client, auth_headers):
    headers, user = auth_headers

    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == "trader@example.com"


def test_me_requires_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_rejects_invalid_token(client):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
