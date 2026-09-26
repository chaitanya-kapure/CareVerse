"""Authentication endpoints.

Each route declares the path, the dependencies, and the response model.
All behaviour lives in AuthController.
"""

from fastapi import APIRouter, Request, status

from app.controllers import AuthController
from app.middlewares.auth_middleware import CurrentUser
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
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


# --- Password reset -------------------------------------------------------
#
# These three are intentionally unauthenticated. The account holder cannot
# sign in, so demanding a token would make recovery impossible. Each step is
# constrained instead by a per-code attempt limit, a resend cooldown, a TTL,
# and single use, which together bound what an unauthenticated caller can
# do to a code they do not hold.


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a password reset OTP",
)
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    """Always answers the same way, for every address.

    The client-facing path is `/api/auth/forgot-password`; the Vite dev
    proxy strips `/api` before it reaches this router.
    """
    # Recorded for abuse triage only. X-Forwarded-For is deliberately not
    # trusted here: without a proxy configured to set it, it is
    # client-controlled and would make the field worthless.
    client_ip = request.client.host if request.client else None
    return await AuthController.forgot_password(payload, request_ip=client_ip)


@router.post(
    "/verify-reset-otp",
    response_model=VerifyOtpResponse,
    summary="Exchange a correct OTP for a single-use reset token",
)
async def verify_reset_otp(payload: VerifyOtpRequest):
    return await AuthController.verify_reset_otp(payload)


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Set a new password using a reset token",
)
async def reset_password(payload: ResetPasswordRequest):
    return await AuthController.reset_password(payload)
