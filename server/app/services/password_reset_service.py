"""Password-reset business logic."""

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

from pymongo.database import Database

from app.config import settings
from app.models.collections import get_password_reset_otps, get_users
from app.models.password_reset import PasswordResetOtpDocument
from app.services.email_service import send_password_reset_otp
from app.services.auth_service import normalize_email
from app.utils import errors
from app.utils.security import (
    generate_otp,
    generate_reset_token,
    hash_otp,
    hash_password,
    hash_reset_token,
    verify_otp,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _timing_equalizer() -> str:
    """A throwaway bcrypt hash to spend when there is nothing to compare."""
    return hash_otp("timing-equalizer")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PasswordResetService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._otps = get_password_reset_otps(db)
        self._users = get_users(db)

    # --- Step 1: request an OTP ------------------------------------------

    def request_otp(self, email: str, request_ip: Optional[str] = None) -> dict:
        """Issue an OTP when the address is registered and off cooldown."""
        email = normalize_email(email)
        now = _now()

        user = self._users.find_one({"email": email})
        if user is None or user.get("status") != "active":
            # No user, or a disabled account. Same response either way.
            logger.info("Password reset requested for an address with no active account")
            return {"issued": False, "reason": "no_active_account"}

        cooldown = timedelta(seconds=settings.otp_resend_cooldown_seconds)
        previous = self._latest_record(email)

        if previous is not None and now - previous["created_at"] < cooldown:
            # Silently ignored rather than rejected with a 429: a distinct
            logger.info("Password reset request inside resend cooldown; not reissued")
            return {"issued": False, "reason": "cooldown"}

        # A fresh request supersedes any earlier *unredeemed* code, so only
        self._otps.delete_many(
            {"email": email, "consumed_at": None, "reset_token_hash": None}
        )

        otp = generate_otp()
        record: PasswordResetOtpDocument = {
            "user_id": str(user["_id"]),
            "email": email,
            "otp_hash": hash_otp(otp),
            "expires_at": now + timedelta(minutes=settings.otp_ttl_minutes),
            "attempts": 0,
            "max_attempts": settings.otp_max_attempts,
            "created_at": now,
            "verified_at": None,
            "reset_token_hash": None,
            "reset_token_expires_at": None,
            "consumed_at": None,
            "request_ip": request_ip,
        }
        self._otps.insert_one(record)

        delivered = send_password_reset_otp(
            to_email=email, otp=otp, expires_in_minutes=settings.otp_ttl_minutes
        )

        return {"issued": True, "delivered": delivered, "reason": "issued"}

    # --- Step 2: exchange the OTP for a reset token -----------------------

    def verify_otp(self, email: str, otp: str) -> dict:
        """Return a single-use reset token for a correct OTP."""
        email = normalize_email(email)
        now = _now()
        record = self._active_record(email)

        if record is None:
            # Either the address has no code, or the code was already burned
            verify_otp(otp, _timing_equalizer())
            raise errors.bad_request(
                "Too many incorrect attempts, or no code is active. Request a new code.",
                code="OTP_ATTEMPTS_EXCEEDED",
            )

        if record["expires_at"] <= now:
            # The TTL index will reap the document shortly; nothing to do
            # beyond refusing it.
            verify_otp(otp, _timing_equalizer())
            raise errors.bad_request(
                "That code has expired. Request a new one.",
                code="OTP_EXPIRED",
            )

        if not verify_otp(otp, record.get("otp_hash", "")):
            attempts = record.get("attempts", 0) + 1
            self._otps.update_one({"_id": record["_id"]}, {"$set": {"attempts": attempts}})

            remaining = max(record.get("max_attempts", 0) - attempts, 0)
            if remaining <= 0:
                # Destroy the record rather than leaving it to be probed
                self._otps.delete_one({"_id": record["_id"]})
                logger.info("Password reset OTP locked out after too many attempts")

            raise errors.bad_request(
                "That code is not correct."
                if remaining > 0
                else "Too many incorrect attempts. Request a new code.",
                code="OTP_INVALID" if remaining > 0 else "OTP_ATTEMPTS_EXCEEDED",
            )

        token = generate_reset_token()
        self._otps.update_one(
            {"_id": record["_id"]},
            {
                "$set": {
                    "verified_at": now,
                    "reset_token_hash": hash_reset_token(token),
                    "reset_token_expires_at": now
                    + timedelta(minutes=settings.reset_token_ttl_minutes),
                    # Clearing the hash is what makes the OTP single-use.
                    "otp_hash": None,
                }
            },
        )

        return {
            "reset_token": token,
            "expires_in": settings.reset_token_ttl_minutes * 60,
        }

    # --- Step 3: spend the token ------------------------------------------

    def reset_password(self, reset_token: str, new_password: str) -> dict:
        """Set a new password, then invalidate every reset credential."""
        now = _now()
        token_hash = hash_reset_token(reset_token)

        record = self._otps.find_one(
            {"reset_token_hash": token_hash, "consumed_at": None}
        )

        if record is None:
            raise errors.bad_request(
                "This reset link is invalid or has already been used. Request a new code.",
                code="RESET_TOKEN_INVALID",
            )

        expires_at = record.get("reset_token_expires_at")
        if expires_at is None or expires_at <= now:
            raise errors.bad_request(
                "This reset link has expired. Request a new code.",
                code="RESET_TOKEN_EXPIRED",
            )

        user = self._users.find_one({"_id": self._as_object_id(record.get("user_id"))})
        if user is None or user.get("status") != "active":
            raise errors.bad_request(
                "This reset link is invalid or has already been used. Request a new code.",
                code="RESET_TOKEN_INVALID",
            )

        # Same hashing path as registration and login. Deliberately not a
        self._users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "password_hash": hash_password(new_password),
                    "updated_at": now,
                }
            },
        )

        # Spend this token and drop every other live reset state for the
        # account, so a code issued before the reset cannot be used to undo it.
        self._otps.update_one(
            {"_id": record["_id"]},
            {
                "$set": {
                    "consumed_at": now,
                    # Cleared as well as consumed: after this the document
                    # holds no usable credential at all.
                    "reset_token_hash": None,
                }
            },
        )
        self._otps.delete_many(
            {"user_id": record.get("user_id"), "consumed_at": None}
        )

        logger.info("Password reset completed for user %s", record.get("user_id"))
        return {"reset": True}

    # --- helpers ----------------------------------------------------------

    def _active_record(self, email: str) -> Optional[PasswordResetOtpDocument]:
        """The record holding a still-redeemable OTP, if there is one."""
        return self._otps.find_one(
            {"email": email, "consumed_at": None, "otp_hash": {"$ne": None}},
            sort=[("created_at", -1)],
        )

    def _latest_record(self, email: str) -> Optional[PasswordResetOtpDocument]:
        """The most recent record for an address in any state."""
        return self._otps.find_one({"email": email}, sort=[("created_at", -1)])

    @staticmethod
    def _as_object_id(user_id):
        from bson import ObjectId

        if user_id is None or not ObjectId.is_valid(str(user_id)):
            return None
        return ObjectId(str(user_id))
