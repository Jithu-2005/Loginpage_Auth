from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.database.session import Base, engine
# Import models so SQLAlchemy registers all tables before create_all.
from app import models  # noqa: F401
from app.routers import github, google, otp, tokens, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Convenient for local learning. For production, use Alembic migrations instead.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    same_site="lax",
    https_only=not settings.DEBUG,
)

app.include_router(otp.router)
app.include_router(google.router)
app.include_router(github.router)
app.include_router(tokens.router)
app.include_router(users.router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "Student Authentication API is running"}
