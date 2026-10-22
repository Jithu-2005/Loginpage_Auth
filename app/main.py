import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.errors import AppError
from app.routes import auth

logger = logging.getLogger("auth-api")

app = FastAPI(
    title="Auth API",
    version="1.0.0",
    description=(
        "Login with **Mobile OTP**, **Google (Gmail)** and **GitHub**.\n\n"
        "Use the **Authorize** button and paste the `accessToken` returned by `/api/auth/login`."
    ),
    swagger_ui_parameters={"persistAuthorization": True},
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/docs")


# ---- Error handling: every error is returned as {"error": "..."} ----
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status, content={"error": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body")
    message = f"{field}: {first['msg']}" if field else first["msg"]
    return JSONResponse(status_code=400, content={"error": message})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
