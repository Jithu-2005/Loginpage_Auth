
from fastapi import APIRouter, Depends, HTTPException, Request
from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx

from app.core.config import settings
from app.database.session import get_db
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.services.token_service import issue_tokens

router = APIRouter(prefix="/auth/github", tags=["GitHub OAuth"])
oauth = OAuth()

if settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET:
    oauth.register(
        name="github",
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )


@router.get("/login")
async def github_login(request: Request):
    if not (
        settings.GITHUB_CLIENT_ID
        and settings.GITHUB_CLIENT_SECRET
    ):
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured",
        )

    return await oauth.github.authorize_redirect(
        request,
        settings.GITHUB_REDIRECT_URI,
    )


@router.get("/callback")
async def github_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    if not (
        settings.GITHUB_CLIENT_ID
        and settings.GITHUB_CLIENT_SECRET
    ):
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured",
        )

    token = await oauth.github.authorize_access_token(request)

    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {
            "Authorization": f"Bearer {token['access_token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        user_response = await client.get(
            "https://api.github.com/user",
            headers=headers,
        )
        user_response.raise_for_status()
        profile = user_response.json()

        emails_response = await client.get(
            "https://api.github.com/user/emails",
            headers=headers,
        )
        emails_response.raise_for_status()
        email_entries = emails_response.json()

    # Only use a verified email for account matching.
    primary_verified = next(
        (
            entry
            for entry in email_entries
            if entry.get("primary") and entry.get("verified")
        ),
        None,
    )

    email = (
        primary_verified.get("email")
        if primary_verified
        else None
    )

    provider_user_id = str(profile.get("id", ""))

    if not provider_user_id:
        raise HTTPException(
            status_code=400,
            detail="GitHub did not return a user ID",
        )

    try:
        # First, check whether this GitHub account is already linked.
        account = db.scalar(
            select(OAuthAccount).where(
                OAuthAccount.provider == "github",
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )

        if account:
            user = db.get(User, account.user_id)

            if not user or not user.is_active:
                raise HTTPException(
                    status_code=403,
                    detail="This account is inactive",
                )

        else:
            # If GitHub provides a verified email matching an existing
            # account, link this GitHub identity to that user.
            user = None

            if email:
                user = db.scalar(
                    select(User).where(User.email == email)
                )

            # Otherwise create a new user.
            if user is None:
                user = User(
                    email=email,
                    full_name=(
                        profile.get("name")
                        or profile.get("login")
                    ),
                )
                db.add(user)
                db.flush()

            elif not user.is_active:
                raise HTTPException(
                    status_code=403,
                    detail="This account is inactive",
                )

            # Save the GitHub identity for future logins.
            db.add(
                OAuthAccount(
                    user_id=user.id,
                    provider="github",
                    provider_user_id=provider_user_id,
                    provider_email=email,
                )
            )

            db.commit()
            db.refresh(user)

        return issue_tokens(user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Account data conflicts with an existing record. "
                "Please retry login or contact support."
            ),
        )
    except Exception:
        db.rollback()
        raise
