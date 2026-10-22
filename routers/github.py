import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from config import settings
from database import get_db
from services.oauth_service import get_or_create_oauth_user
from services.token_service import create_access_token

router = APIRouter()
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
    if not (settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET):
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")
    return await oauth.github.authorize_redirect(request, settings.GITHUB_REDIRECT_URI)


@router.get("/callback")
async def github_callback(request: Request, db: Session = Depends(get_db)):
    if not (settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET):
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")
    try:
        token = await oauth.github.authorize_access_token(request)
        access_token = token["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            profile_response = await client.get("https://api.github.com/user", headers=headers)
            profile_response.raise_for_status()
            profile = profile_response.json()

            email = profile.get("email")
            if not email:
                emails_response = await client.get("https://api.github.com/user/emails", headers=headers)
                emails_response.raise_for_status()
                email_items = emails_response.json()
                primary_verified = next(
                    (item.get("email") for item in email_items
                     if item.get("primary") and item.get("verified")),
                    None,
                )
                email = primary_verified

        if not profile.get("id"):
            raise HTTPException(status_code=401, detail="GitHub identity is missing ID")

        user = get_or_create_oauth_user(
            db,
            provider="github",
            provider_user_id=str(profile["id"]),
            name=profile.get("name") or profile.get("login"),
            verified_email=email,
        )
        return JSONResponse({
            "message": "GitHub authentication successful",
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
    except Exception as exc:
        raise HTTPException(status_code=400, detail="GitHub sign-in failed") from exc
