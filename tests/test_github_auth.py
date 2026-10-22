
from fastapi.testclient import TestClient

from app.main import app
from app.routers import github

client = TestClient(app)


def test_github_login_returns_503_when_not_configured(monkeypatch):
    monkeypatch.setattr(github.settings, "GITHUB_CLIENT_ID", "")
    monkeypatch.setattr(github.settings, "GITHUB_CLIENT_SECRET", "")

    response = client.get(
        "/auth/github/login",
        follow_redirects=False,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "GitHub OAuth is not configured"
