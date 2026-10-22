from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    OTP_MODE: str = "development"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    SESSION_SECRET_KEY: str
    COOKIE_SECURE: bool = False

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://127.0.0.1:8000/auth/google/callback"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://127.0.0.1:8000/auth/github/callback"
    
    MESSAGE_CENTRAL_CUSTOMER_ID: str = ""
    MESSAGE_CENTRAL_EMAIL: str = ""
    MESSAGE_CENTRAL_KEY: str = ""
    MESSAGE_CENTRAL_COUNTRY_CODE: str = "91"

    # TWILIO_ACCOUNT_SID: str = ""
    # TWILIO_AUTH_TOKEN: str = ""
    # TWILIO_VERIFY_SERVICE_SID: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
