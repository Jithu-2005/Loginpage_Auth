from pydantic import BaseModel, Field


class OTPSendRequest(BaseModel):
    phone_number: str = Field(
        min_length=8, max_length=20,
        description="Phone number in E.164 format, e.g. +919876543210",
        examples=["+919876543210"],
    )


class OTPVerifyRequest(BaseModel):
    phone_number: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=4, max_length=10, pattern=r"^[0-9]+$")

class GoogleVerifyRequest(BaseModel):
    id_token: str = Field(
        min_length=20,
        description="Google ID token, not an access token",
    )

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class UserResponse(BaseModel):
    id: int
    name: str | None
    email: str | None
    phone_number: str | None
    is_active: bool

    model_config = {"from_attributes": True}
