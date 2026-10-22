"""
OTP service with two modes (SMS_PROVIDER in .env):

  messagecentral -> Message Central VerifyNow (V3). Flow:
                    generate token -> POST /verification/v3/send -> GET /verification/v3/validateOtp
                    Message Central generates, sends, expires and checks the OTP.
  console        -> OTP generated locally and printed in the terminal (no account needed).
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

import httpx
import phonenumbers

from app import config
from app.errors import AppError


def _use_message_central() -> bool:
    return config.SMS_PROVIDER == "messagecentral"


# =====================================================================
#  MODE 1: Message Central
# =====================================================================
_token_cache = {"token": None, "expires_at": 0.0}
_pending = {}  # phone -> {"verification_id": str, "last_sent_at": float}


def _http() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=config.MC_BASE_URL, timeout=15.0)


def _map_mc_code(code, message: Optional[str] = None) -> AppError:
    """Message Central response codes -> HTTP errors of our API."""
    text = f" ({message})" if message else ""
    try:
        c = int(code)
    except (TypeError, ValueError):
        c = None

    if c == 702:
        return AppError(401, "Invalid OTP")
    if c == 700:
        return AppError(401, "OTP verification failed")
    if c == 705:
        return AppError(400, "OTP has expired, request a new one")
    if c == 703:
        return AppError(400, "This OTP was already used, request a new one")
    if c == 505:
        return AppError(400, "OTP session not found, request a new OTP")
    if c == 506:
        return AppError(429, "An OTP request is already in progress, please wait")
    if c == 800:
        return AppError(429, "Maximum OTP attempts reached, try again later")
    if c == 511:
        return AppError(400, "Country code is not supported")
    if c == 501:
        return AppError(500, "Message Central customer ID is invalid")
    if c == 400:
        return AppError(400, f"Bad request to Message Central{text}")
    return AppError(502, f"Message Central error {code}{text}")


def _failure_code(body):
    """Message Central can report a failure in body.responseCode or body.data.responseCode."""
    if not isinstance(body, dict):
        return None
    inner = body.get("data")
    candidates = [body.get("responseCode"), inner.get("responseCode") if isinstance(inner, dict) else None]
    for c in candidates:
        if c is None:
            continue
        try:
            if int(c) != 200:
                return c
        except (TypeError, ValueError):
            return c
    return None


def _error_message(body) -> Optional[str]:
    if not isinstance(body, dict):
        return None
    inner = body.get("data")
    return body.get("message") or (inner.get("errorMessage") if isinstance(inner, dict) else None)


def _json(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def _token_expiry(token: str) -> float:
    try:
        segment = token.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
        if payload.get("exp"):
            return float(payload["exp"]) - 60  # refresh 1 minute early
    except Exception:  # not a decodable JWT -> fallback below
        pass
    return time.time() + 30 * 60


async def _get_token(force: bool = False) -> str:
    if not config.MC_CUSTOMER_ID or not config.MC_PASSWORD:
        raise AppError(
            501,
            "Message Central is not configured. Set MESSAGECENTRAL_CUSTOMER_ID and "
            "MESSAGECENTRAL_PASSWORD in .env",
        )
    if not force and _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    params = {
        "customerId": config.MC_CUSTOMER_ID,
        "key": base64.b64encode(config.MC_PASSWORD.encode()).decode(),
        "scope": "NEW",
    }
    if config.MC_COUNTRY:
        params["country"] = config.MC_COUNTRY
    if config.MC_EMAIL:
        params["email"] = config.MC_EMAIL

    try:
        async with _http() as client:
            resp = await client.get("/auth/v1/authentication/token", params=params)
        token = (_json(resp) or {}).get("token")
        if resp.status_code >= 400 or not token:
            raise ValueError("no token")
    except Exception:
        raise AppError(
            502,
            "Message Central authentication failed. Check MESSAGECENTRAL_CUSTOMER_ID "
            "and MESSAGECENTRAL_PASSWORD",
        )

    _token_cache["token"] = token
    _token_cache["expires_at"] = _token_expiry(token)
    return token


async def _mc_call(method: str, url: str, params: dict, retry: bool = True) -> dict:
    token = await _get_token()
    try:
        async with _http() as client:
            resp = await client.request(method, url, params=params, headers={"authToken": token})
    except httpx.HTTPError as exc:
        raise AppError(502, f"Could not reach Message Central: {exc}")

    # Token expired -> get a new one and retry once
    if resp.status_code == 401 and retry:
        _token_cache["token"] = None
        await _get_token(force=True)
        return await _mc_call(method, url, params, retry=False)

    body = _json(resp)
    failed = _failure_code(body)
    if resp.status_code >= 400 or failed is not None:
        raise _map_mc_code(failed if failed is not None else resp.status_code, _error_message(body))
    return body


async def _mc_send(phone: str) -> None:
    try:
        parsed = phonenumbers.parse(phone, None)
    except phonenumbers.NumberParseException:
        parsed = None
    if parsed is None or not phonenumbers.is_valid_number(parsed):
        raise AppError(400, "Invalid phone number")

    existing = _pending.get(phone)
    now = time.time()
    if existing and now - existing["last_sent_at"] < config.OTP_RESEND_COOLDOWN_SECONDS:
        wait = int(config.OTP_RESEND_COOLDOWN_SECONDS - (now - existing["last_sent_at"])) + 1
        raise AppError(429, f"Please wait {wait}s before requesting another OTP")

    body = await _mc_call(
        "POST",
        "/verification/v3/send",
        {
            "countryCode": str(parsed.country_code),
            "mobileNumber": str(parsed.national_number),
            "flowType": "SMS",
            "otpLength": config.OTP_LENGTH,
        },
    )
    verification_id = ((body or {}).get("data") or {}).get("verificationId")
    if not verification_id:
        raise AppError(502, "Message Central did not return a verificationId")
    _pending[phone] = {"verification_id": str(verification_id), "last_sent_at": now}


async def _mc_check(phone: str, code: str) -> None:
    record = _pending.get(phone)
    if not record:
        raise AppError(400, "No OTP requested for this number")

    body = await _mc_call(
        "GET",
        "/verification/v3/validateOtp",
        {"verificationId": record["verification_id"], "code": str(code)},
    )
    status = ((body or {}).get("data") or {}).get("verificationStatus")
    if status != "VERIFICATION_COMPLETED":
        raise AppError(401, "Invalid OTP")
    _pending.pop(phone, None)  # one-time use


# =====================================================================
#  MODE 2: console (local OTP, printed in the terminal)
# =====================================================================
_store = {}  # phone -> {"hash", "expires_at", "attempts", "last_sent_at"}


def _hash(phone: str, otp: str) -> str:
    return hmac.new(config.JWT_SECRET.encode(), f"{phone}:{otp}".encode(), hashlib.sha256).hexdigest()


def _generate_otp() -> str:
    return str(secrets.randbelow(10 ** config.OTP_LENGTH)).zfill(config.OTP_LENGTH)


def _local_send(phone: str) -> Optional[str]:
    existing = _store.get(phone)
    now = time.time()
    if existing and now - existing["last_sent_at"] < config.OTP_RESEND_COOLDOWN_SECONDS:
        wait = int(config.OTP_RESEND_COOLDOWN_SECONDS - (now - existing["last_sent_at"])) + 1
        raise AppError(429, f"Please wait {wait}s before requesting another OTP")

    otp = _generate_otp()
    _store[phone] = {
        "hash": _hash(phone, otp),
        "expires_at": now + config.OTP_TTL_SECONDS,
        "attempts": 0,
        "last_sent_at": now,
    }
    print(f"\n📱 [OTP for {phone}] {otp}  (expires in 5 minutes)\n", flush=True)
    return otp if config.OTP_DEV_MODE else None


def _local_check(phone: str, otp: str) -> None:
    record = _store.get(phone)
    if not record:
        raise AppError(400, "No OTP requested for this number")
    if time.time() > record["expires_at"]:
        _store.pop(phone, None)
        raise AppError(400, "OTP has expired, request a new one")
    if record["attempts"] >= config.OTP_MAX_ATTEMPTS:
        _store.pop(phone, None)
        raise AppError(429, "Too many wrong attempts, request a new OTP")

    record["attempts"] += 1
    if not hmac.compare_digest(record["hash"], _hash(phone, str(otp))):
        raise AppError(401, "Invalid OTP")
    _store.pop(phone, None)  # one-time use


# =====================================================================
#  Public API (used by routes)
# =====================================================================
async def send_otp(phone: str) -> Optional[str]:
    """Returns the OTP only in console + dev mode, otherwise None."""
    if _use_message_central():
        await _mc_send(phone)
        return None  # never expose the OTP when Message Central sends it
    return _local_send(phone)


async def verify_otp(phone: str, otp: str) -> None:
    if _use_message_central():
        return await _mc_check(phone, otp)
    return _local_check(phone, otp)
