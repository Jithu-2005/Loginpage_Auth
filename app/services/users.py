"""In-memory user store. Replace with a real DB (MongoDB / PostgreSQL) for production."""
import uuid
from datetime import datetime, timezone

_users = {}  # id -> user dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_or_create(profile: dict) -> dict:
    """profile keys: provider, provider_id, email, name, avatar, phone"""
    for user in _users.values():
        if user["provider"] == profile["provider"] and user["provider_id"] == profile["provider_id"]:
            user["last_login_at"] = _now()
            return user

    user = {
        "id": str(uuid.uuid4()),
        "provider": profile["provider"],
        "provider_id": profile["provider_id"],
        "email": profile.get("email"),
        "name": profile.get("name"),
        "avatar": profile.get("avatar"),
        "phone": profile.get("phone"),
        "created_at": _now(),
        "last_login_at": _now(),
    }
    _users[user["id"]] = user
    return user


def find_by_id(user_id: str):
    return _users.get(user_id)
