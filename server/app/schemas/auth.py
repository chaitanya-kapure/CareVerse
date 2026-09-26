"""Request/response schemas for authentication.

Pydantic is the validation layer here (the Zod equivalent in the original
spec). Nothing reaches a service without passing through one of these.
"""

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import settings

UserRoleLiteral = Literal["patient", "doctor"]

# One definition of what a valid password is. Registration and password
# reset share it so the two paths cannot drift apart -- a reset that accepted
# a password registration would reject would be a confusing lockout bug.
# 72 is bcrypt's hard byte limit; the schema stops oversized input before
# hashing rather than silently truncating it later.
PasswordValue = Annotated[str, Field(min_length=6, max_length=72)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Asha Menon",
                "email": "asha@example.com",
                "password": "strongpassword",
                "role": "patient",
            }
        }
    )

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    # 72 bytes is bcrypt's hard limit; the schema stops oversized input
    # before hashing rather than silently truncating it later.
    password: PasswordValue
    role: UserRoleLiteral


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: UserRoleLiteral


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    detail: str
    code: Optional[str] = None


# --- Password reset -------------------------------------------------------
#
# Three endpoints, three distinct credentials. `retry_after_seconds` is a
# configuration constant rather than a measurement of this particular
# request, because a value that changed depending on whether the account
# exists would defeat the point of the generic response.


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    # Identical for a registered address, an unregistered one, and a
    # disabled account. See PasswordResetService.request_otp.
    detail: str
    code: str
    retry_after_seconds: int
    # The configured OTP lifetime, so the client can show a countdown that
    # matches the server. Constant for every caller, so it reveals nothing.
    expires_in: int


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=1, max_length=16)

    @field_validator("otp")
    @classmethod
    def _must_be_numeric_of_expected_length(cls, value: str) -> str:
        # Length is checked against configuration rather than hardcoded, so
        # changing OTP_LENGTH does not silently reject every real code.
        stripped = value.strip()
        if not stripped.isdigit():
            raise ValueError("OTP must contain digits only")
        if len(stripped) != settings.otp_length:
            raise ValueError(f"OTP must be exactly {settings.otp_length} digits")
        return stripped


class VerifyOtpResponse(BaseModel):
    # Returned only on a correct OTP. Opaque to the client and useless to a
    # third party: it authorises exactly one password change, once.
    reset_token: str
    expires_in: int
    detail: str


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=20, max_length=256)
    new_password: PasswordValue

