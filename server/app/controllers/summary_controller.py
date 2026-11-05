"""Summary endpoints: a doctor's view of one patient's summary, and the"""

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
        """The current summary, generated if missing or out of date."""
        db = get_db()
        authorized_id = _authorized_patient_id(db, user, patient_id)
        return await _run(SummaryService(db).get_summary, authorized_id)

    @staticmethod
    async def regenerate_for_doctor(patient_id: str, user: UserDocument) -> dict:
        """Force a fresh summary, ignoring the staleness check."""
        db = get_db()
        authorized_id = _authorized_patient_id(db, user, patient_id)
        return await _run(SummaryService(db).get_summary, authorized_id, force=True)

    @staticmethod
    async def get_own(user: UserDocument) -> dict:
        """The caller's own summary."""
        db = get_db()
        patient_id = assert_own_records(db, user)
        return await _run(SummaryService(db).get_summary, patient_id)


async def _run(func, *args, **kwargs):
    """Call the summary service off the event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)


def _authorized_patient_id(db: Database, user: UserDocument, patient_id: str) -> str:
    """Validate a requested patient id, and return it only if permitted."""
    requested = resolve_patient_id(patient_id)
    assert_patient_access(db, user, requested)
    return requested
