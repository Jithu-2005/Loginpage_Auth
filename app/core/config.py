from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Student Authentication API"
    DEBUG: bool = False

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/auth/github/callback"

    SMS_PROVIDER: str = "message_central"
    MESSAGE_CENTRAL_CUSTOMER_ID: str = ""
    MESSAGE_CENTRAL_EMAIL: str = ""
    MESSAGE_CENTRAL_KEY: str = ""
    MESSAGE_CENTRAL_COUNTRY_CODE: str = "91"

    SESSION_SECRET_KEY: str = "development-only-change-me"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
