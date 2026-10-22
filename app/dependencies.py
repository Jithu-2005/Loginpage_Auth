import time
from collections import defaultdict, deque
from typing import Optional

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.errors import AppError
from app.services import tokens, users

# Adds the "Authorize" button to Swagger UI
bearer_scheme = HTTPBearer(auto_error=False, description="Paste the accessToken returned by /login (without 'Bearer ')")

_hits = defaultdict(deque)
RATE_LIMIT = 20  # requests
RATE_WINDOW = 60  # seconds, per client IP and path


async def rate_limiter(request: Request) -> None:
    """Very small in-memory rate limiter (20 requests / minute / IP / endpoint)."""
    key = f"{request.client.host if request.client else 'unknown'}:{request.url.path}"
    now = time.monotonic()
    hits = _hits[key]
    while hits and now - hits[0] > RATE_WINDOW:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        raise AppError(429, "Too many requests, slow down")
    hits.append(now)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "Missing Bearer token")
    try:
        payload = tokens.verify_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise AppError(401, "Invalid or expired token")

    user = users.find_by_id(payload.get("sub"))
    if not user:
        raise AppError(401, "Invalid or expired token")
    return user
