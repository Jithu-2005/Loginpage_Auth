
from fastapi.testclient import TestClient
from app.main import app
from app.routers import google

client = TestClient(app)

def test_google_login_returns_503_when_not_configured(monkeypatch):
    monkeypatch.setattr(google.settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(google.settings, "GOOGLE_CLIENT_SECRET", "")

    response = client.get(
        "/auth/google/login",
        follow_redirects=False,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Google OAuth is not configured"
