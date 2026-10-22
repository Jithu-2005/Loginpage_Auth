from fastapi.testclient import TestClient

# Note: importing app.main loads settings and requires a valid .env first.
from app.main import app

client = TestClient(app)

def test_health_check():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
def test_users_me_requires_authentication():
    response = client.get("/users/me")
    assert response.status_code == 401

def test_users_me_rejects_invalid_token():
    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid_token"}
    )

    assert response.status_code == 401

def test_refresh_rejects_invalid_token():
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid_refresh_token"}
    )

    assert response.status_code == 401
from datetime import timedelta
from app.core.security import create_token


def test_users_me_rejects_expired_token():
    expired_token = create_token(
        subject="1",
        token_type="access",
        expires_delta=timedelta(seconds=-10),
    )

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401

from app.core.security import create_access_token


def test_refresh_rejects_access_token():
    access_token = create_access_token(user_id=1)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401
