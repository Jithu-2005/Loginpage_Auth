import time

import jwt

from app import config


def sign_access_token(user: dict) -> str:
    now = int(time.time())
    payload = {
        "sub": user["id"],
        "provider": user["provider"],
        "iat": now,
        "exp": now + config.JWT_EXPIRES_SECONDS,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def verify_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError if the token is invalid or expired."""
    return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
