from fastapi import APIRouter, Depends, HTTPException, Request
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.services.token_service import issue_tokens

router = APIRouter(prefix="/auth/google", tags=["Google OAuth"])
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
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")

    token = await oauth.google.authorize_access_token(request)
    profile = token.get("userinfo")
    if not profile:
        profile = await oauth.google.userinfo(token=token)

    provider_user_id = str(profile.get("sub", ""))
    if not provider_user_id:
        raise HTTPException(status_code=400, detail="Google did not return a user ID")

    email = profile.get("email")
    # Link by provider identity only. Do not automatically link an existing account
    # just because the provider returns the same email address.
    account = db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    if account:
        user = db.get(User, account.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="This account is inactive")
    else:
        user = User(email=email, full_name=profile.get("name"))
        db.add(user)
        db.flush()
        db.add(OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id=provider_user_id,
            provider_email=email,
        ))
        db.commit()
        db.refresh(user)

    # For local development this returns tokens in JSON. For a browser app, prefer
    # redirecting to a frontend callback and deliver tokens via a secure one-time code.
    return issue_tokens(user)
