"""Request/response schemas for authentication.

Pydantic is the validation layer here (the Zod equivalent in the original
spec). Nothing reaches a service without passing through one of these.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRoleLiteral = Literal["patient", "doctor"]


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
    password: str = Field(min_length=6, max_length=72)
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
