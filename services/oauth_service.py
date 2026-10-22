from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import HTTPException

from models import AuthAccount, User


def get_or_create_oauth_user(
    db: Session,
    *,
    provider: str,
    provider_user_id: str,
    name: str | None,
    verified_email: str | None,
) -> User:
    existing_account = db.scalar(
        select(AuthAccount).where(
            AuthAccount.provider == provider,
            AuthAccount.provider_user_id == provider_user_id,
        )
    )
    if existing_account:
        if not existing_account.user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        return existing_account.user

    # Deliberately do not auto-link an identity to an existing user based only
    # on a matching email. If that email already exists, retain the provider
    # identity but leave email unset until the user securely links accounts.
    safe_email = verified_email
    if safe_email:
        email_exists = db.scalar(select(User.id).where(User.email == safe_email))
        if email_exists:
            safe_email = None

    user = User(name=name, email=safe_email)
    db.add(user)
    db.flush()

    account = AuthAccount(
        user_id=user.id,
        provider=provider,
        provider_user_id=str(provider_user_id),
    )
    db.add(account)
    db.commit()
    db.refresh(user)
    return user
