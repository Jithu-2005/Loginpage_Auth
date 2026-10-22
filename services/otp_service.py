
import base64
import logging
import re
import time

import httpx
from fastapi import HTTPException

from config import settings


BASE_URL = "https://cpaas.messagecentral.com"
OTP_EXPIRY_SECONDS = 300

# Local development only. Use Redis or a database in production.
# phone number -> (verification ID, auth token, expiry timestamp)
_pending_verifications: dict[str, tuple[str, str, float]] = {}


def _credentials_configured() -> bool:
    return all(
        [
            settings.MESSAGE_CENTRAL_CUSTOMER_ID,
            settings.MESSAGE_CENTRAL_EMAIL,
            settings.MESSAGE_CENTRAL_KEY,
            settings.MESSAGE_CENTRAL_COUNTRY_CODE,
        ]
    )


def _normalize_phone(phone_number: str) -> str:
    """Return the mobile number without its country calling code."""
    digits = re.sub(r"\D", "", phone_number)
    country_code = settings.MESSAGE_CENTRAL_COUNTRY_CODE.strip()

    if digits.startswith(country_code):
        digits = digits[len(country_code):]

    if not digits or not digits.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number",
        )

    return digits


def _get_auth_token(client: httpx.Client) -> str:
    """Request an authentication token from Message Central."""
    key = settings.MESSAGE_CENTRAL_KEY.strip()

    # Validate the configured key locally without logging its value.
    try:
        base64.b64decode(key, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        logging.error("Message Central key is not valid Base64.")
        raise HTTPException(
            status_code=503,
            detail="Message Central authentication key configuration is invalid.",
        ) from exc

    try:
        response = client.get(
            f"{BASE_URL}/auth/v1/authentication/token",
            params={
                "customerId": settings.MESSAGE_CENTRAL_CUSTOMER_ID.strip(),
                "key": key,
                "scope": "NEW",
                "country": settings.MESSAGE_CENTRAL_COUNTRY_CODE.strip(),
                "email": settings.MESSAGE_CENTRAL_EMAIL.strip(),
            },
            headers={"accept": "*/*"},
            timeout=20.0,
        )
        response.raise_for_status()

    except httpx.HTTPStatusError as exc:
        logging.error(
            "Message Central token request returned HTTP %s.",
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Message Central rejected the authentication request.",
        ) from exc

    except httpx.HTTPError as exc:
        logging.error(
            "Message Central authentication request failed: %s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Could not communicate with Message Central authentication.",
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Message Central returned an unexpected authentication response.",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail="Unexpected Message Central authentication response.",
        )

    # Log the error only, never credentials or tokens.
    error = payload.get("error") or payload.get("message")
    if error:
        logging.error(
            "Message Central token error: %s",
            str(error)[:300],
        )

    token = payload.get("token")

    if not token:
        logging.error(
            "Message Central authentication response did not contain "
            "the expected 'token' field. Response fields: %s",
            list(payload.keys()),
        )
        raise HTTPException(
            status_code=502,
            detail="Message Central did not issue an authentication token.",
        )

    return str(token)


def send_otp(phone_number: str) -> None:
    """Request an SMS OTP and save its verification details."""
    if not _credentials_configured():
        raise HTTPException(
            status_code=503,
            detail="Message Central OTP is not configured.",
        )

    mobile_number = _normalize_phone(phone_number)

    try:
        with httpx.Client(timeout=20.0) as client:
            auth_token = _get_auth_token(client)

            response = client.post(
                f"{BASE_URL}/verification/v3/send",
                params={
                    "countryCode": settings.MESSAGE_CENTRAL_COUNTRY_CODE.strip(),
                    "customerId": settings.MESSAGE_CENTRAL_CUSTOMER_ID.strip(),
                    "mobileNumber": mobile_number,
                    "flowType": "SMS",
                    "otpLength": 6,
                },
                headers={"authToken": auth_token},
            )
            response.raise_for_status()

            payload = response.json()

        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=502,
                detail="Unexpected Message Central OTP response.",
            )

        data = payload.get("data") or {}
        verification_id = data.get("verificationId")

        if str(payload.get("responseCode")) != "200" or not verification_id:
            logging.error(
                "Message Central OTP send unsuccessful: responseCode=%s, message=%s",
                payload.get("responseCode"),
                payload.get("message"),
            )
            raise HTTPException(
                status_code=502,
                detail="Could not send verification code.",
            )

        _pending_verifications[mobile_number] = (
            str(verification_id),
            auth_token,
            time.time() + OTP_EXPIRY_SECONDS,
        )

        logging.info("Message Central OTP request accepted.")

    except HTTPException:
        raise

    except httpx.HTTPStatusError as exc:
        logging.error(
            "Message Central OTP send returned HTTP %s.",
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Message Central rejected the OTP request.",
        ) from exc

    except (httpx.HTTPError, ValueError) as exc:
        logging.exception("Message Central OTP send failed.")
        raise HTTPException(
            status_code=502,
            detail="Could not communicate with Message Central.",
        ) from exc


def verify_otp(phone_number: str, code: str) -> bool:
    """Validate an OTP using the saved verification ID."""
    if not _credentials_configured():
        raise HTTPException(
            status_code=503,
            detail="Message Central OTP is not configured.",
        )

    mobile_number = _normalize_phone(phone_number)
    stored = _pending_verifications.get(mobile_number)

    if stored is None:
        logging.warning("No pending OTP verification was found.")
        return False

    verification_id, auth_token, expires_at = stored

    if time.time() >= expires_at:
        _pending_verifications.pop(mobile_number, None)
        return False

    if not code.isdigit():
        return False

    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{BASE_URL}/verification/v3/validateOtp",
                params={
                    "verificationId": verification_id,
                    "code": code,
                    "flowType": "SMS",
                },
                headers={"authToken": auth_token},
            )

        if response.status_code == 401:
            logging.error(
                "Message Central returned HTTP 401 for OTP validation. "
                "Check the documented token/header requirements."
           )
            raise HTTPException(
                status_code=502,
                detail="Message Central authentication failed during OTP verification.",
            )
        

        if response.status_code in (400, 404, 409, 422):
            logging.warning(
                "Message Central rejected OTP validation: HTTP %s.",
                response.status_code,
            )
            return False

        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=502,
                detail="Unexpected Message Central validation response.",
            )

        data = payload.get("data") or {}

        verified = (
            str(payload.get("responseCode")) == "200"
            and data.get("verificationStatus") == "VERIFICATION_COMPLETED"
        )

        if verified:
            # Prevent reuse after successful verification.
            _pending_verifications.pop(mobile_number, None)

        return verified

    except HTTPException:
        raise

    except httpx.HTTPStatusError as exc:
        logging.warning(
            "Message Central validation returned HTTP %s.",
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Message Central rejected the verification request.",
        ) from exc

    except (httpx.HTTPError, ValueError) as exc:
        logging.exception("Message Central OTP validation failed.")
        raise HTTPException(
            status_code=502,
            detail="Could not communicate with Message Central.",
        ) from exc
