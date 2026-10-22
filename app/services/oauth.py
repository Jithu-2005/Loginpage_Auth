"""Google and GitHub OAuth helpers. Every login function returns a normalized profile dict."""
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import httpx

from app import config
from app.errors import AppError

# ---- CSRF "state" handling for browser redirect flows ----
_states = {}


def _create_state() -> str:
    state = secrets.token_hex(16)
    _states[state] = time.time() + 10 * 60
    return state


def consume_state(state: Optional[str]) -> None:
    expires = _states.pop(state, None) if state else None
    if not expires or time.time() > expires:
        raise AppError(400, "Invalid or expired OAuth state")


def _require_config(name: str, client_id, client_secret) -> None:
    if not client_id or not client_secret:
        up = name.upper()
        raise AppError(501, f"{name} login is not configured. Set {up}_CLIENT_ID and {up}_CLIENT_SECRET in .env")


# ------------------------------ GOOGLE ------------------------------
def _google_redirect_uri() -> str:
    return f"{config.BASE_URL}/api/auth/google/callback"


def google_auth_url() -> str:
    _require_config("google", config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET)
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": _create_state(),
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def google_login_with_id_token(id_token: str) -> dict:
    """Mobile / SPA flow: the client already has a Google ID token."""
    _require_config("google", config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": id_token})
    except httpx.HTTPError:
        raise AppError(502, "Could not reach Google")

    if resp.status_code != 200:
        raise AppError(401, "Invalid Google ID token")
    data = resp.json()
    if data.get("aud") != config.GOOGLE_CLIENT_ID:
        raise AppError(401, "ID token was not issued for this app")
    if str(data.get("email_verified")).lower() != "true":
        raise AppError(401, "Google email is not verified")

    return {
        "provider": "google",
        "provider_id": data["sub"],
        "email": data.get("email"),
        "name": data.get("name"),
        "avatar": data.get("picture"),
    }


async def google_login_with_code(code: str) -> dict:
    """Browser flow: exchange the authorization code for an ID token."""
    _require_config("google", config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": _google_redirect_uri(),
                    "grant_type": "authorization_code",
                },
            )
    except httpx.HTTPError:
        raise AppError(502, "Could not reach Google")

    id_token = resp.json().get("id_token") if resp.status_code == 200 else None
    if not id_token:
        raise AppError(401, "Google code exchange failed")
    return await google_login_with_id_token(id_token)


# ------------------------------ GITHUB ------------------------------
def github_auth_url() -> str:
    _require_config("github", config.GITHUB_CLIENT_ID, config.GITHUB_CLIENT_SECRET)
    params = {
        "client_id": config.GITHUB_CLIENT_ID,
        "redirect_uri": f"{config.BASE_URL}/api/auth/github/callback",
        "scope": "read:user user:email",
        "state": _create_state(),
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


async def github_login_with_code(code: str) -> dict:
    _require_config("github", config.GITHUB_CLIENT_ID, config.GITHUB_CLIENT_SECRET)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": config.GITHUB_CLIENT_ID,
                    "client_secret": config.GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise AppError(401, token_data.get("error_description") or "GitHub code exchange failed")

            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
            user = (await client.get("https://api.github.com/user", headers=headers)).json()

            email = user.get("email")
            if not email:
                emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
                emails = emails_resp.json() if emails_resp.status_code == 200 else []
                email = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)
    except httpx.HTTPError:
        raise AppError(502, "Could not reach GitHub")

    if "id" not in user:
        raise AppError(401, "GitHub authentication failed")
    return {
        "provider": "github",
        "provider_id": str(user["id"]),
        "email": email,
        "name": user.get("name") or user.get("login"),
        "avatar": user.get("avatar_url"),
    }
