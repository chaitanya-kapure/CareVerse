"""Password hashing, OTP generation, and JWT creation/verification.

Kept free of FastAPI imports so it can be unit tested and reused by the
seed scripts without booting the app.
"""

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
    """Return the payload, or None if the token is invalid/expired.

    Returning None instead of raising keeps the exception-to-HTTP mapping in
    the auth middleware, where it belongs.
    """
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


# --- Password reset -------------------------------------------------------
#
# Two different hashing strategies below, for two different threat models.
# This is not inconsistency.


def generate_otp(length: int | None = None) -> str:
    """A zero-padded numeric OTP from a CSPRNG.

    `secrets.randbelow` is used rather than `random.randint` on purpose: the
    OTP is a single-use credential that authorises a password change, so its
    unpredictability has to come from the OS entropy source. A predictable
    generator would let an attacker who knows the time and the user id
    reproduce the code.
    """
    length = length or settings.otp_length
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


def hash_otp(otp: str) -> str:
    """Hash a 6-digit OTP with bcrypt.

    A short numeric code has a tiny search space (1e6 for 6 digits), so it
    gets the same slow hash as a password. If the database were ever exposed,
    a leaked hash would resist offline recovery for far longer than a fast
    digest would. The attempt limit in PasswordResetService is what actually
    stops online guessing; bcrypt is the second layer, not the first.
    """
    return hash_password(otp)


def verify_otp(otp: str, hashed_otp: str) -> bool:
    return verify_password(otp, hashed_otp)


def generate_reset_token() -> str:
    """An opaque, high-entropy token issued after a correct OTP.

    Deliberately NOT a login JWT. A password reset is a short, single-purpose
    capability, and reusing the access token would mean either giving the
    reset a full session's worth of authority, or bolting a `purpose` claim
    onto a token whose only consumer is the app. An opaque random string
    cannot be decoded, cannot be minted by the client, and is looked up in
    the database on every use, so single-use enforcement is a real check
    rather than an untested claim.
    """
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """SHA-256 of a reset token, for storing and looking it up.

    No salt and no slow hash here, which looks inconsistent with
    `hash_otp` but is correct: the input is 256 bits of CSPRNG output, so
    there is no dictionary or rainbow table to slow down, and the record has
    to be found by hash value. Salting per record would make every reset
    attempt a full collection scan to locate the token. The reason
    `hash_otp` needs bcrypt -- a 1e6 search space -- does not apply.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
