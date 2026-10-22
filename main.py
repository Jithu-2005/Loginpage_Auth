from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from database import Base, engine
from routers.auth import router as auth_router
from routers.github import router as github_router
from routers.google import router as google_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Convenient for a learning project. For production, use Alembic migrations.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Multi-Method Authentication API",
    description="Mobile OTP (Twilio Verify), Google OIDC, and GitHub OAuth.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie="multi_auth_session",
    same_site="lax",
    https_only=settings.COOKIE_SECURE,
    max_age=600,
)

app.include_router(auth_router, prefix="/auth", tags=["OTP and Session"])
app.include_router(google_router, prefix="/auth/google", tags=["Google OIDC"])
app.include_router(github_router, prefix="/auth/github", tags=["GitHub OAuth"])


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
