"""CareVerse ID — unique 4-digit patient identifier."""
import logging
from typing import Optional

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.models.careverse_id import generate_candidate
from app.models.collections import get_careverse_ids
from app.utils import errors

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 20


class CareVerseIdService:
    def __init__(self, db: Database) -> None:
        self._ids = get_careverse_ids(db)

    def get_or_create(self, patient_id: str) -> str:
        """Return existing ID or generate a new unique one."""
        existing = self._ids.find_one({"patient_id": patient_id})
        if existing:
            return existing["careverse_id"]
        return self._assign_new(patient_id)

    def _assign_new(self, patient_id: str) -> str:
        for attempt in range(MAX_ATTEMPTS):
            candidate = generate_candidate()
            try:
                self._ids.insert_one({"patient_id": patient_id, "careverse_id": candidate})
                logger.info("CareVerse ID %s assigned to patient %s", candidate, patient_id)
                return candidate
            except DuplicateKeyError:
                continue
        logger.error("CareVerse ID namespace exhausted after %d attempts", MAX_ATTEMPTS)
        raise errors.internal("Could not assign a unique CareVerse ID. The namespace may be exhausted.")

    def lookup_patient_id(self, careverse_id: str) -> Optional[str]:
        """Return patient_id for a 4-digit ID, or None if not found."""
        row = self._ids.find_one({"careverse_id": careverse_id})
        return row["patient_id"] if row else None

    def get_for_patient(self, patient_id: str) -> Optional[str]:
        row = self._ids.find_one({"patient_id": patient_id})
        return row["careverse_id"] if row else None
