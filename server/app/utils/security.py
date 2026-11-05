"""Password hashing, OTP generation, and JWT creation/verification."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings

# bcrypt only considers the first 72 bytes of a password.
BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash in the database should read as "wrong password",
        # not as a 500.
        return False


def create_access_token(user_id: str, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {"sub": user_id, "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Return the payload, or None if the token is invalid/expired."""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# --- Password reset -------------------------------------------------------


def generate_otp(length: int | None = None) -> str:
    """A zero-padded numeric OTP from a CSPRNG."""
    length = length or settings.otp_length
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


def hash_otp(otp: str) -> str:
    """Hash a 6-digit OTP with bcrypt."""
    return hash_password(otp)


def verify_otp(otp: str, hashed_otp: str) -> bool:
    return verify_password(otp, hashed_otp)


def generate_reset_token() -> str:
    """An opaque, high-entropy token issued after a correct OTP."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """SHA-256 of a reset token, for storing and looking it up."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
