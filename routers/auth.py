import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User
from schemas import OTPVerifyRequest, OTPSendRequest, TokenResponse, UserResponse
from services.otp_service import send_otp, verify_otp
from services.token_service import create_access_token, decode_access_token

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token subject") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


@router.post("/otp/send", status_code=202)
def otp_send(request: OTPSendRequest):
    # E.164 is the recommended international phone-number format.
    if not re.fullmatch(r"\+[1-9]\d{7,14}", request.phone_number):
        raise HTTPException(status_code=422, detail="Use E.164 format, e.g. +919876543210")
    send_otp(request.phone_number)
    return {"message": "If the number is eligible, a verification code has been sent."}


@router.post("/otp/verify", response_model=TokenResponse)
def otp_verify(request: OTPVerifyRequest, db: Session = Depends(get_db)):
    if not re.fullmatch(r"\+[1-9]\d{7,14}", request.phone_number):
        raise HTTPException(status_code=422, detail="Use E.164 phone-number format")

    if not verify_otp(request.phone_number, request.code):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    user = db.scalar(select(User).where(User.phone_number == request.phone_number))
    if user is None:
        user = User(phone_number=request.phone_number)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    return TokenResponse(
        access_token=create_access_token(user),
        expires_in_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    # Access JWTs are stateless; this endpoint documents client-side logout.
    # The client must discard the token. For immediate server-side revocation,
    # implement short-lived access tokens plus a refresh-token/session store.
    return {"message": "Logged out on client. Discard the access token."}
