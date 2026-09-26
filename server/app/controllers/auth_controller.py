"""Auth controller: request -> service -> response."""

from app.config import settings
from app.database import get_db
from app.models.user import UserDocument, serialize_user
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyOtpRequest,
)
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService
from app.utils import errors
from app.utils.security import create_access_token


class AuthController:
    @staticmethod
    async def register(payload: RegisterRequest) -> dict:
        db = get_db()
        service = AuthService(db)

        user = service.register(payload)

        # Every patient gets their centralized profile immediately, so the
        # upload screen always has something to attach records to.
        service.ensure_patient_profile(user["id"])

        return user

    @staticmethod
    async def login(payload: LoginRequest) -> dict:
        db = get_db()
        service = AuthService(db)

        user = service.authenticate(payload.email, payload.password)
        if user is None:
            # One message for both "no such account" and "wrong password",
            # so login cannot be used to discover registered emails.
            raise errors.unauthorized(
                "Invalid email or password", code="INVALID_CREDENTIALS"
            )

        if user.get("status") == "disabled":
            raise errors.forbidden("This account has been disabled", code="ACCOUNT_DISABLED")

        return {
            "access_token": create_access_token(str(user["_id"]), user["role"]),
            "token_type": "bearer",
            "user": serialize_user(user),
        }

    @staticmethod
    async def me(user: UserDocument) -> dict:
        return serialize_user(user)

    @staticmethod
    async def logout() -> dict:
        return {"detail": "Logged out", "code": "LOGGED_OUT"}

    # --- Password reset ---------------------------------------------------
    #
    # Notice that these take no CurrentUser. A user who cannot log in
    # because they forgot their password is, by definition, unable to
    # authenticate, so requiring a token here would make the flow
    # unreachable. The OTP is the credential; these routes stay anonymous
    # and are constrained instead by the per-code attempt limit, the resend
    # cooldown, and the single-use reset token. (Per-IP rate limiting is
    # listed as out of scope in docs/ARCHITECTURE.md; `request_ip` is
    # recorded for abuse triage, not used to throttle.)

    @staticmethod
    async def forgot_password(payload: ForgotPasswordRequest, request_ip=None) -> dict:
        db = get_db()
        service = PasswordResetService(db)

        service.request_otp(payload.email, request_ip=request_ip)

        # Built unconditionally from constants. Nothing the service returned
        # reaches the client, so the response cannot vary with whether the
        # address is registered, disabled, or already inside its cooldown.
        return {
            "detail": "If an account exists for this email, an OTP has been sent.",
            "code": "OTP_REQUEST_ACCEPTED",
            "retry_after_seconds": settings.otp_resend_cooldown_seconds,
            "expires_in": settings.otp_ttl_minutes * 60,
        }

    @staticmethod
    async def verify_reset_otp(payload: VerifyOtpRequest) -> dict:
        db = get_db()
        service = PasswordResetService(db)

        result = service.verify_otp(payload.email, payload.otp)

        return {
            "reset_token": result["reset_token"],
            "expires_in": result["expires_in"],
            "detail": "Code accepted. Choose a new password.",
        }

    @staticmethod
    async def reset_password(payload: ResetPasswordRequest) -> dict:
        db = get_db()
        service = PasswordResetService(db)

        service.reset_password(payload.reset_token, payload.new_password)

        return {
            "detail": "Your password has been updated. You can sign in now.",
            "code": "PASSWORD_RESET",
        }
