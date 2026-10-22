
import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import OTPRequest, OTPVerify, TokenResponse
from app.services.token_service import issue_tokens

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/otp", tags=["Mobile OTP"])

BASE_URL = "https://cpaas.messagecentral.com"

# Development only: stores verification IDs in memory.
# Use Redis or a database with expiration in production.
pending_verifications: dict[str, str] = {}


def message_central_configured() -> bool:
    return all(
        value and value.strip()
        for value in (
            settings.MESSAGE_CENTRAL_CUSTOMER_ID,
            settings.MESSAGE_CENTRAL_EMAIL,
            settings.MESSAGE_CENTRAL_KEY,
        )
    )


def normalize_phone(phone: str) -> tuple[str, str, str]:
    """Return country code, national number, and normalized phone."""
    digits = re.sub(r"\D", "", phone)
    country_code = settings.MESSAGE_CENTRAL_COUNTRY_CODE.strip()

    if not country_code.isdigit():
        raise HTTPException(
            status_code=500,
            detail="Invalid OTP country-code configuration",
        )

    if digits.startswith(country_code) and len(digits) > len(country_code):
        national_number = digits[len(country_code):]
    else:
        national_number = digits

    # India-specific validation for this project.
    if country_code == "91" and not re.fullmatch(r"[6-9]\d{9}", national_number):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid 10-digit Indian mobile number",
        )

    if not national_number:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    normalized = country_code + national_number
    return country_code, national_number, normalized



async def get_auth_token(client: httpx.AsyncClient) -> str:
    try:
        response = await client.get(
            f"{BASE_URL}/auth/v1/authentication/token",
            params={
                "customerId": settings.MESSAGE_CENTRAL_CUSTOMER_ID,
                "key": settings.MESSAGE_CENTRAL_KEY,
                "scope": "NEW",
                "country": settings.MESSAGE_CENTRAL_COUNTRY_CODE,
                "email": settings.MESSAGE_CENTRAL_EMAIL,
            },
            headers={"accept": "*/*"},
        )

        logger.info(
            "Message Central auth HTTP status: %s",
            response.status_code,
        )

        response.raise_for_status()

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("Message Central returned non-JSON authentication data")
            raise HTTPException(
                status_code=502,
                detail="Message Central returned an invalid authentication response",
            ) from exc

        if not isinstance(data, dict):
            logger.error("Message Central authentication response was not an object")
            raise HTTPException(
                status_code=502,
                detail="Invalid Message Central authentication response",
            )

        logger.info(
            "Message Central auth response fields: %s",
            list(data.keys()),
        )

        token = data.get("token")

        if not isinstance(token, str) or not token.strip():
            # Do not log the full response: it may contain sensitive information.
            error = data.get("error")
            logger.error(
                "Message Central returned no token; error_type=%s",
                type(error).__name__ if error is not None else "None",
            )
            raise HTTPException(
                status_code=502,
                detail="Message Central authentication failed",
            )

        return token.strip()

    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Message Central authentication HTTP error: status=%s",
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Message Central rejected the authentication request",
        ) from exc
    except httpx.RequestError as exc:
        logger.error(
            "Message Central authentication connection failed: %s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Could not contact Message Central authentication service",
        ) from exc
def provider_error_detail(response: httpx.Response) -> str:
    """Log provider diagnostics without exposing credentials."""
    try:
        body: Any = response.json()
        message = body.get("message") or body.get("errorMessage")
        if not message and isinstance(body.get("data"), dict):
            message = body["data"].get("errorMessage")
        if message:
            logger.warning(
                "Message Central returned HTTP %s: %s",
                response.status_code,
                str(message)[:300],
            )
    except (ValueError, AttributeError):
        logger.warning(
            "Message Central returned HTTP %s",
            response.status_code,
        )

    return "Message Central request failed. Check server logs and provider credentials."


@router.post("/send")
async def send_otp(payload: OTPRequest) -> dict[str, str]:
    if not message_central_configured():
        raise HTTPException(
            status_code=503,
            detail="OTP service is not configured. Check Message Central settings.",
        )

    country_code, mobile_number, normalized_phone = normalize_phone(
        payload.phone_number
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            auth_token = await get_auth_token(client)

            response = await client.post(
                f"{BASE_URL}/verification/v3/send",
                params={
                    "countryCode": country_code,
                    "customerId": settings.MESSAGE_CENTRAL_CUSTOMER_ID,
                    "mobileNumber": mobile_number,
                    "flowType": "SMS",
                    "otpLength": 6,
                },
                headers={"authToken": auth_token},
            )

            if response.is_error:
                detail = provider_error_detail(response)
                raise HTTPException(status_code=502, detail=detail)

            try:
                result = response.json()
            except ValueError:
                raise HTTPException(
                    status_code=502,
                    detail="Message Central returned an invalid response",
                )

    except HTTPException:
        raise
    except httpx.HTTPError:
        logger.exception("Message Central OTP send request failed")
        raise HTTPException(
            status_code=502,
            detail="Could not contact Message Central to send OTP",
        )

    data = result.get("data") or {}

    if str(result.get("responseCode")) != "200" or not data.get("verificationId"):
        logger.warning(
            "Message Central did not confirm OTP send; responseCode=%s",
            result.get("responseCode"),
        )
        raise HTTPException(
            status_code=502,
            detail="Message Central did not confirm sending the OTP. Check provider account status.",
        )

    pending_verifications[normalized_phone] = str(data["verificationId"])

    return {
        "status": "pending",
        "message": "OTP request accepted by Message Central. Check your phone.",
    }


@router.post("/verify", response_model=TokenResponse)
async def verify_otp(
    payload: OTPVerify,
    db: Session = Depends(get_db),
) -> TokenResponse:
    if not message_central_configured():
        raise HTTPException(
            status_code=503,
            detail="OTP service is not configured. Check Message Central settings.",
        )

    country_code, mobile_number, normalized_phone = normalize_phone(
        payload.phone_number
    )

    verification_id = pending_verifications.get(normalized_phone)

    if not verification_id:
        raise HTTPException(
            status_code=400,
            detail="Please request a new OTP first",
        )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            auth_token = await get_auth_token(client)

            response = await client.get(
                f"{BASE_URL}/verification/v3/validateOtp",
                params={
                    "verificationId": verification_id,
                    "code": payload.code,
                    "flowType": "SMS",
                },
                headers={"authToken": auth_token},
            )

            if response.is_error:
                detail = provider_error_detail(response)
                raise HTTPException(status_code=502, detail=detail)

            try:
                result = response.json()
            except ValueError:
                raise HTTPException(
                    status_code=502,
                    detail="Message Central returned an invalid verification response",
                )

    except HTTPException:
        raise
    except httpx.HTTPError:
        logger.exception("Message Central OTP verification request failed")
        raise HTTPException(
            status_code=502,
            detail="Could not contact Message Central to verify OTP",
        )

    data = result.get("data") or {}

    if (
        str(result.get("responseCode")) != "200"
        or data.get("verificationStatus") != "VERIFICATION_COMPLETED"
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OTP",
        )

    user = db.scalar(
        select(User).where(User.phone_number == normalized_phone)
    )

    if user is None:
        user = User(phone_number=normalized_phone)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account is inactive",
        )

    # Remove the pending verification after successful validation.
    pending_verifications.pop(normalized_phone, None)

    return issue_tokens(user)
