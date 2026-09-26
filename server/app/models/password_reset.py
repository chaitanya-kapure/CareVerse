"""`password_reset_otps` collection.

One document per issued OTP. This is a sixth collection, which is a
deliberate and narrow deviation from the five-collection model in spec
section 12: the five are clinical data (users, profiles, documents, access,
summaries) and this is transient authentication state with a different
lifetime. Folding it into `users` would mean every document carried the
current reset code, and the TTL cleanup below would be impossible.

Nothing here is a medical record. The document holds a credential and the
timestamps needed to expire it.
"""

from datetime import datetime
from typing import Optional, TypedDict


class PasswordResetOtpDocument(TypedDict, total=False):
    _id: object
    user_id: str                # users._id as a string, never a patient id
    email: str                  # stored lowercased, matching users.email
    otp_hash: str               # bcrypt. The plaintext OTP is never stored.
    expires_at: datetime        # drives the TTL index
    attempts: int               # failed verification attempts so far
    max_attempts: int           # frozen at issue time, so raising the limit
                                # later cannot un-invalidate a live record
    created_at: datetime
    # Set once the OTP is verified. A record with no reset_token_hash is an
    # OTP that has not been redeemed.
    verified_at: Optional[datetime]
    reset_token_hash: Optional[str]        # sha256 of an opaque token
    reset_token_expires_at: Optional[datetime]
    # Set when the password is actually changed. A reset token is spent at
    # this point and can never be replayed.
    consumed_at: Optional[datetime]
    request_ip: Optional[str]   # for abuse triage; never returned to a client


# A record in this state is spent and holds no live credential.
ACTIVE_FIELDS = {
    "consumed_at": None,
    "reset_token_hash": None,
    "reset_token_expires_at": None,
}


def otp_is_active(record: PasswordResetOtpDocument) -> bool:
    """True while the record can still be exchanged for a reset token.

    Checks every gate in one place so the request, verify and reset paths
    cannot disagree about what "active" means.
    """
    if record.get("consumed_at") is not None:
        return False
    if record.get("attempts", 0) >= record.get("max_attempts", 0):
        return False
    return record.get("otp_hash") is not None
