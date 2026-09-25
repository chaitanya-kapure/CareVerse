"""Authentication endpoints.

Each route declares the path, the dependencies, and the response model.
All behaviour lives in AuthController.
"""

from fastapi import APIRouter, status

from app.controllers import AuthController
from app.middlewares.auth_middleware import CurrentUser
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a patient or doctor",
)
async def register(payload: RegisterRequest):
    return await AuthController.register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Exchange credentials for a JWT",
)
async def login(payload: LoginRequest):
    return await AuthController.login(payload)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current authenticated user",
)
async def me(user: CurrentUser):
    """Lets the client validate a stored token on app start instead of
    trusting whatever role it happens to have in localStorage."""
    return await AuthController.me(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout acknowledgement",
)
async def logout(user: CurrentUser):
    """Stateless JWTs cannot be revoked server-side without a blocklist.
    The client discards the token; this endpoint exists so the flow is
    explicit and can grow a blocklist later without a client change."""
    return await AuthController.logout()
