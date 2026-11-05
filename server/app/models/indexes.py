"""Index creation, run once on application startup."""

import logging

from pymongo.database import Database
from pymongo.errors import OperationFailure

from app.models import access
from app.models import collections as c

logger = logging.getLogger(__name__)


def ensure_indexes(db: Database) -> None:
    _safe(db, lambda: db[c.USERS].create_index([("email", 1)], unique=True, name="uniq_email"))
    _safe(db, lambda: db[c.USERS].create_index([("role", 1)], name="role_idx"))

    # One profile per patient, enforced by the database.
    _safe(
        db,
        lambda: db[c.PATIENT_PROFILES].create_index(
            [("patient_id", 1)], unique=True, name="uniq_patient_profile"
        ),
    )

    _safe(
        db,
        lambda: db[c.MEDICAL_DOCUMENTS].create_index(
            [("patient_id", 1), ("uploaded_at", -1)], name="patient_docs_recent"
        ),
    )
    # Serving a document by id is the most common read; filtering by patient
    # on top keeps that query scoped to an owner.
    _safe(
        db,
        lambda: db[c.MEDICAL_DOCUMENTS].create_index(
            [("patient_id", 1), ("_id", 1)], name="patient_docs_by_id"
        ),
    )

    # The authorization lookup: "is this doctor allowed to read this patient?"
    _safe(
        db,
        lambda: db[c.PATIENT_ACCESS].create_index(
            list(access.UNIQUE_ACTIVE_GRANT_KEYS),
            name="doctor_patient_pair",
        ),
    )
    _safe(
        db,
        lambda: db[c.PATIENT_ACCESS].create_index(
            list(access.UNIQUE_ACTIVE_GRANT_KEYS),
            name=access.UNIQUE_ACTIVE_GRANT_INDEX,
            unique=True,
            partialFilterExpression=access.UNIQUE_ACTIVE_GRANT_FILTER,
        ),
    )
    # Listing a patient's own grants, and showing the doctor their history.
    _safe(
        db,
        lambda: db[c.PATIENT_ACCESS].create_index(
            [("patient_id", 1), ("granted_at", -1)], name="patient_grants_recent"
        ),
    )

    _safe(
        db,
        lambda: db[c.PATIENT_SUMMARIES].create_index(
            [("patient_id", 1)], unique=True, name="uniq_patient_summary"
        ),
    )

    # Password-reset OTPs are the one thing in this schema with a hard
    _safe(
        db,
        lambda: db[c.PASSWORD_RESET_OTPS].create_index(
            [("expires_at", 1)], expireAfterSeconds=0, name="otp_ttl"
        ),
    )
    # verify-otp resolves the active record for an email with one lookup.
    _safe(
        db,
        lambda: db[c.PASSWORD_RESET_OTPS].create_index(
            [("email", 1), ("created_at", -1)], name="otp_by_email_recent"
        ),
    )
    # reset-password resolves the token by hash. Not unique: a spent record
    _safe(
        db,
        lambda: db[c.PASSWORD_RESET_OTPS].create_index(
            [("reset_token_hash", 1)], name="otp_by_reset_token"
        ),
    )

    # doctor_profiles: unique per user, searchable by specialty
    _safe(db, lambda: db[c.DOCTOR_PROFILES].create_index([("user_id", 1)], unique=True, name="uniq_doctor_profile"))
    _safe(db, lambda: db[c.DOCTOR_PROFILES].create_index([("specialty", 1)], name="doctor_specialty"))
    _safe(db, lambda: db[c.DOCTOR_PROFILES].create_index([("verification_status", 1)], name="doctor_verification"))

    # careverse_ids: unique in both directions
    _safe(db, lambda: db[c.CAREVERSE_IDS].create_index([("patient_id", 1)], unique=True, name="uniq_patient_careverse_id"))
    _safe(db, lambda: db[c.CAREVERSE_IDS].create_index([("careverse_id", 1)], unique=True, name="uniq_careverse_id_value"))

    # posts: feed by time
    _safe(db, lambda: db[c.POSTS].create_index([("created_at", -1)], name="posts_recent"))
    _safe(db, lambda: db[c.POSTS].create_index([("author_id", 1), ("created_at", -1)], name="posts_by_author"))
    _safe(db, lambda: db[c.POSTS].create_index([("hashtags", 1)], name="posts_hashtags"))

    # comments: all comments for a post
    _safe(db, lambda: db[c.COMMENTS].create_index([("post_id", 1), ("created_at", 1)], name="comments_by_post"))

    # follows: fast lookup for both directions
    _safe(db, lambda: db[c.FOLLOWS].create_index([("follower_id", 1), ("followee_id", 1)], unique=True, name="uniq_follow"))
    _safe(db, lambda: db[c.FOLLOWS].create_index([("followee_id", 1)], name="follows_by_followee"))

    # conversations: per participant
    _safe(db, lambda: db[c.CONVERSATIONS].create_index([("participant_ids", 1), ("last_message_at", -1)], name="conv_by_participant"))
    _safe(db, lambda: db[c.CONVERSATIONS].create_index([("participant_ids", 1)], name="conv_participants"))

    # messages: per conversation, ordered
    _safe(db, lambda: db[c.MESSAGES].create_index([("conversation_id", 1), ("created_at", 1)], name="messages_by_conv"))

    # notifications: per user, unread fast
    _safe(db, lambda: db[c.NOTIFICATIONS].create_index([("user_id", 1), ("created_at", -1)], name="notif_by_user"))
    _safe(db, lambda: db[c.NOTIFICATIONS].create_index([("user_id", 1), ("is_read", 1)], name="notif_unread"))

    # access_requests: per patient, per doctor
    _safe(db, lambda: db[c.ACCESS_REQUESTS].create_index([("patient_id", 1), ("status", 1), ("created_at", -1)], name="access_req_by_patient"))
    _safe(db, lambda: db[c.ACCESS_REQUESTS].create_index([("doctor_id", 1), ("created_at", -1)], name="access_req_by_doctor"))
    _safe(db, lambda: db[c.ACCESS_REQUESTS].create_index([("doctor_id", 1), ("patient_id", 1), ("status", 1)], name="access_req_pair"))


def _safe(db: Database, operation) -> None:
    """Index creation must never stop the API from booting."""
    try:
        operation()
    except OperationFailure as exc:
        logger.warning("Index creation skipped: %s", exc)
