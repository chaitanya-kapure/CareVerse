"""Business logic. Routes stay thin; services own the rules."""

from app.services.auth_service import AuthService

__all__ = ["AuthService"]
