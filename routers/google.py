import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import settings
from database import get_db
from models import User
from services.oauth_service import get_or_create_oauth_user
from services.token_service import create_access_token
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from schemas import GoogleVerifyRequest

router = APIRouter()
oauth = OAuth()

if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@router.get("/login")
async def google_login(request: Request):
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    # Authlib stores and validates OAuth state through the Starlette session.
    return await oauth.google.authorize_redirect(request, settings.GOOGLE_REDIRECT_URI)


@router.post("/verify")
def verify_google_token(
    payload: GoogleVerifyRequest,
    db: Session = Depends(get_db),
):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured",
        )

    try:
        google_user = google_id_token.verify_oauth2_token(
            payload.id_token,
            GoogleRequest(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid, expired, or incorrectly issued Google ID token",
        ) from exc
    except Exception as exc:
        logging.exception("Google ID token verification failed")
        raise HTTPException(
            status_code=502,
            detail="Could not verify the Google ID token",
        ) from exc

    google_sub = google_user.get("sub")

    if not google_sub:
        raise HTTPException(
            status_code=401,
            detail="Google ID token is missing the subject",
        )

    verified_email = (
        google_user.get("email")
        if google_user.get("email_verified") is True
        else None
    )

    user = get_or_create_oauth_user(
        db,
        provider="google",
        provider_user_id=str(google_sub),
        name=google_user.get("name"),
        verified_email=verified_email,
    )

    app_token = create_access_token(user)

    return {
        "message": "Google authentication successful",
        "access_token": app_token,
        "token_type": "bearer",
        "expires_in_seconds": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
        },
    }

@router.get("/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    try:
        token = await oauth.google.authorize_access_token(request)
        google_id_token_value = token.get("id_token")
        userinfo = token.get("userinfo")
        if not userinfo:
            # Authlib usually parses the OIDC ID token into userinfo when the
            # provider metadata and openid scope are configured.
            raise HTTPException(status_code=401, detail="Google identity was not returned")

        if not userinfo.get("sub"):
            raise HTTPException(status_code=401, detail="Google identity is missing subject")

        email = userinfo.get("email") if userinfo.get("email_verified") is True else None
        user = get_or_create_oauth_user(
            db,
            provider="google",
            provider_user_id=str(userinfo["sub"]),
            name=userinfo.get("name"),
            verified_email=email,
        )
        return JSONResponse({
            "message": "Google authentication successful",
            "access_token": create_access_token(user),
            "token_type": "bearer",
            "expires_in_seconds": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
            },
            "note": "For production browser apps, redirect to a frontend using a one-time handoff code rather than placing tokens in URLs.",
        })
    except HTTPException:
        raise
    except Exception:
        
        logging.exception("Google OAuth callback failed")

        raise HTTPException(
            status_code=400,
            detail="Google sign-in failed. Check the FastAPI terminal."
        )
