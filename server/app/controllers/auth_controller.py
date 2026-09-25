"""Auth controller: request -> service -> response."""

from app.database import get_db
from app.models.user import UserDocument, serialize_user
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService
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
