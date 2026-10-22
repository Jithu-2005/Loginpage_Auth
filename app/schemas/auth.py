from pydantic import BaseModel, ConfigDict, Field


class OTPRequest(BaseModel):
    phone_number: str = Field(
        min_length=8,
        max_length=30,
        description="Phone number in international format, e.g. +919876543210",
    )


class OTPVerify(BaseModel):
    phone_number: str = Field(min_length=8, max_length=30)
    code: str = Field(min_length=4, max_length=10)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    phone_number: str | None = None
    email: str | None = None
    full_name: str | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
