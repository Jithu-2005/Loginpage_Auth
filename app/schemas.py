from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class OtpSendRequest(BaseModel):
    phone: str = Field(..., description="Phone number in E.164 format", examples=["+919876543210"])


class OtpSendResponse(BaseModel):
    message: str = "OTP sent"
    devOtp: Optional[str] = Field(
        None,
        description="Only returned when SMS_PROVIDER=console and OTP_DEV_MODE=true",
        examples=["123456"],
    )


class LoginRequest(BaseModel):
    provider: Literal["mobile_otp", "google", "github"]
    phone: Optional[str] = Field(None, description="mobile_otp: phone in E.164 format")
    otp: Optional[str] = Field(None, description="mobile_otp: the OTP received by SMS")
    idToken: Optional[str] = Field(None, description="google: Google ID token (mobile / SPA flow)")
    code: Optional[str] = Field(None, description="google / github: OAuth authorization code")

    @field_validator("otp", "phone", "idToken", "code", mode="before")
    @classmethod
    def _to_str(cls, v):
        # Accept numbers too (e.g. otp sent as 123456 instead of "123456")
        return str(v) if isinstance(v, int) and not isinstance(v, bool) else v


class UserOut(BaseModel):
    id: str
    provider: str = Field(..., examples=["mobile_otp"])
    email: Optional[str] = None
    name: Optional[str] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    user: UserOut


class ErrorResponse(BaseModel):
    error: str
