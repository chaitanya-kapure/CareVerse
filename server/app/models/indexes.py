"""Index creation, run once on application startup.

These indexes are the second half of authorization: a unique index on
`patient_profiles.patient_id` is what guarantees a patient cannot end up
with two profiles, and the compound index on `patient_access` makes the
"is this doctor authorized?" check a single indexed lookup.
"""

import logging

from pymongo.database import Database
from pymongo.errors import OperationFailure

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

    _safe(
        db,
        lambda: db[c.PATIENT_ACCESS].create_index(
            [("doctor_id", 1), ("patient_id", 1)], name="doctor_patient_pair"
        ),
    )

    _safe(
        db,
        lambda: db[c.PATIENT_SUMMARIES].create_index(
            [("patient_id", 1)], unique=True, name="uniq_patient_summary"
        ),
    )

    # Password-reset OTPs are the one thing in this schema with a hard
    # deadline, so MongoDB enforces it. expireAfterSeconds=0 means "delete as
    # soon as expires_at is in the past", which means the service never has to
    # run a cleanup job and a forgotten OTP cannot linger on a server.
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
    # keeps its hash so the replay is auditable, and the query also filters
    # on consumed_at.
    _safe(
        db,
        lambda: db[c.PASSWORD_RESET_OTPS].create_index(
            [("reset_token_hash", 1)], name="otp_by_reset_token"
        ),
    )


def _safe(db: Database, operation) -> None:
    """Index creation must never stop the API from booting.

    A pre-existing index with different options raises OperationFailure; that
    is a migration concern, not a reason to take the server down.
    """
    try:
        operation()
    except OperationFailure as exc:
        logger.warning("Index creation skipped: %s", exc)
