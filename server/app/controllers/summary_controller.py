"""Summary endpoints: a doctor's view of one patient's summary, and the
patient's view of their own.

Thin, exactly like `DoctorController` and `PatientController`. Each method
performs the same three steps in the same order:

    1. the route dependency has already proved the caller's role
    2. `resolve_patient_id` + `assert_patient_access` (or `assert_own_records`)
       prove this caller may read *this* patient
    3. only then is `SummaryService` called, with the authorized patient id

`SummaryService` receives an id and nothing else. It has no doctor id, no
token, no request object and no patient object supplied by the frontend, so
there is nothing in its signature that a caller could widen -- the only way to
reach another patient's documents through it is to have already been refused
by step 2.

Both the doctor route and the patient route return the same `dict` from the
same service, so the two audiences cannot drift apart.
"""

import asyncio

from pymongo.database import Database

from app.database import get_db
from app.middlewares.auth_middleware import (
    assert_own_records,
    assert_patient_access,
    resolve_patient_id,
)
from app.models.user import UserDocument
from app.services.summary_service import SummaryService


class SummaryController:
    @staticmethod
    async def get_for_doctor(patient_id: str, user: UserDocument) -> dict:
        """The current summary, generated if missing or out of date.

        Not "always regenerate": a doctor opening the screen twice must not
        rewrite the document twice, and re-running the pipeline on every page
        render is exactly the behaviour that makes a summary's `generated_at`
        meaningless. `SummaryService` compares the readable record set against
        what the persisted summary was built from, and only regenerates when
        they differ.
        """
        db = get_db()
        authorized_id = _authorized_patient_id(db, user, patient_id)
        return await _run(SummaryService(db).get_summary, authorized_id)

    @staticmethod
    async def regenerate_for_doctor(patient_id: str, user: UserDocument) -> dict:
        """Force a fresh summary, ignoring the staleness check.

        A doctor reads a summary, notices it disagrees with a record they just
        opened, and asks for it to be rebuilt. Without this there is no way to
        recover from a persisted summary that is wrong for any reason the
        three staleness comparisons do not cover.

        There is no PUT and no DELETE: a doctor never edits a summary by hand.
        Every line in it is copied from a record, so the fix is always "read
        the records again", never "retype the summary".
        """
        db = get_db()
        authorized_id = _authorized_patient_id(db, user, patient_id)
        return await _run(SummaryService(db).get_summary, authorized_id, force=True)

    @staticmethod
    async def get_own(user: UserDocument) -> dict:
        """The caller's own summary.

        There is no patient id in the path and none in the query string, so
        there is no id for a patient to change. `assert_own_records` is still
        called -- it is what refuses a doctor who reaches a patient-only
        handler -- and the id it returns is the only one that is queried.
        """
        db = get_db()
        patient_id = assert_own_records(db, user)
        return await _run(SummaryService(db).get_summary, patient_id)


async def _run(func, *args, **kwargs):
    """Call the summary service off the event loop.

    The provider seam is synchronous, and Phase 4C replaces it with an HTTP
    call. Assembling a summary reads up to `MAX_DOCUMENTS` records and
    formats every extracted value in them, which is CPU-bound work; running
    it in the default thread pool keeps it from stalling every other request
    the server is handling, exactly as `DocumentService.upload` does for PDF
    extraction.
    """
    return await asyncio.to_thread(func, *args, **kwargs)


def _authorized_patient_id(db: Database, user: UserDocument, patient_id: str) -> str:
    """Validate a requested patient id, and return it only if permitted.

    Identical to the check every other doctor route makes, and for the same
    reason: `resolve_patient_id` rejects a malformed id before it can reach a
    query, and `assert_patient_access` then raises `403 NO_PATIENT_ACCESS`
    unless this doctor holds a live grant.

    That 403 is the same answer for "no such patient" and "a patient who has
    not authorized you", because the grant lookup never consults the patient
    collection. The summary route adds no existence oracle on top of it.
    """
    requested = resolve_patient_id(patient_id)
    assert_patient_access(db, user, requested)
    return requested
