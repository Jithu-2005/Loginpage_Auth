import re
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import RedirectResponse

from app.dependencies import get_current_user, rate_limiter
from app.errors import AppError
from app.schemas import ErrorResponse, LoginRequest, OtpSendRequest, OtpSendResponse, TokenResponse, UserOut
from app.services import oauth, otp, tokens, users

router = APIRouter()

E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def _public_user(user: dict) -> dict:
    return {k: user.get(k) for k in ("id", "provider", "email", "name", "avatar", "phone")}


def _login_response(user: dict) -> dict:
    return {
        "accessToken": tokens.sign_access_token(user),
        "tokenType": "Bearer",
        "user": _public_user(user),
    }


# ---------- 1. Send OTP ----------
@router.post(
    "/otp/send",
    summary="Send a mobile OTP",
    response_model=OtpSendResponse,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limiter)],
)
async def send_otp(body: OtpSendRequest):
    """
    Sends a one-time password to the phone number.

    - `SMS_PROVIDER=console`: OTP is printed in the terminal and returned as `devOtp` (when `OTP_DEV_MODE=true`).
    - `SMS_PROVIDER=messagecentral`: real SMS sent by Message Central; the OTP is never returned.
    """
    if not E164.match(body.phone):
        raise AppError(400, "phone must be in E.164 format, e.g. +919876543210")
    dev_otp = await otp.send_otp(body.phone)
    return {"message": "OTP sent", "devOtp": dev_otp}


# ---------- 2. Unified login ----------
LOGIN_EXAMPLES = {
    "mobile_otp": {
        "summary": "Mobile OTP",
        "value": {"provider": "mobile_otp", "phone": "+919876543210", "otp": "123456"},
    },
    "google": {
        "summary": "Google (ID token)",
        "value": {"provider": "google", "idToken": "<google-id-token>"},
    },
    "github": {
        "summary": "GitHub (OAuth code)",
        "value": {"provider": "github", "code": "<github-oauth-code>"},
    },
}


@router.post(
    "/login",
    summary="Login (mobile OTP / Google / GitHub)",
    response_model=TokenResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        501: {"model": ErrorResponse, "description": "Provider not configured"},
    },
    dependencies=[Depends(rate_limiter)],
)
async def login(body: LoginRequest = Body(..., openapi_examples=LOGIN_EXAMPLES)):
    """
    One endpoint for all login methods; `provider` decides which one runs.

    - **mobile_otp**: send `phone` + `otp`
    - **google**: send Google `idToken` (or `code`)
    - **github**: send GitHub OAuth `code`
    """
    if body.provider == "mobile_otp":
        if not body.phone or not E164.match(body.phone) or not body.otp:
            raise AppError(400, "phone (E.164) and otp are required")
        await otp.verify_otp(body.phone, body.otp)
        profile = {"provider": "mobile_otp", "provider_id": body.phone, "phone": body.phone}

    elif body.provider == "google":
        if body.idToken:
            profile = await oauth.google_login_with_id_token(body.idToken)
        elif body.code:
            profile = await oauth.google_login_with_code(body.code)
        else:
            raise AppError(400, "idToken or code is required for google login")

    else:  # github
        if not body.code:
            raise AppError(400, "code is required for github login")
        profile = await oauth.github_login_with_code(body.code)

    return _login_response(users.find_or_create(profile))


# ---------- 3. Browser redirect flows (open these URLs in a browser tab) ----------
@router.get("/google", summary="Start Google login (open in browser)", status_code=302)
async def google_start():
    """Swagger "Try it out" cannot follow redirects - open `/api/auth/google` directly in a browser tab."""
    return RedirectResponse(oauth.google_auth_url(), status_code=302)


@router.get("/google/callback", summary="Google OAuth callback", response_model=TokenResponse)
async def google_callback(code: Optional[str] = Query(None), state: Optional[str] = Query(None), error: Optional[str] = Query(None)):
    if error:
        raise AppError(400, f"Google login failed: {error}")
    oauth.consume_state(state)
    if not code:
        raise AppError(400, "Missing code")
    profile = await oauth.google_login_with_code(code)
    return _login_response(users.find_or_create(profile))


@router.get("/github", summary="Start GitHub login (open in browser)", status_code=302)
async def github_start():
    """Open `/api/auth/github` directly in a browser tab."""
    return RedirectResponse(oauth.github_auth_url(), status_code=302)


@router.get("/github/callback", summary="GitHub OAuth callback", response_model=TokenResponse)
async def github_callback(code: Optional[str] = Query(None), state: Optional[str] = Query(None), error: Optional[str] = Query(None)):
    if error:
        raise AppError(400, f"GitHub login failed: {error}")
    oauth.consume_state(state)
    if not code:
        raise AppError(400, "Missing code")
    profile = await oauth.github_login_with_code(code)
    return _login_response(users.find_or_create(profile))


# ---------- 4. Protected route ----------
@router.get(
    "/me",
    summary="Get current user (protected)",
    response_model=UserOut,
    responses={401: {"model": ErrorResponse}},
)
async def me(user: dict = Depends(get_current_user)):
    return _public_user(user)
