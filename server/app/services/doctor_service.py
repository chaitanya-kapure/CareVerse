"""What an authorized doctor is allowed to read."""

import logging

from pymongo.database import Database

from app.models.collections import (
    get_medical_documents,
    get_patient_profiles,
)
from app.services.careverse_id_service import CareVerseIdService
from app.services.document_service import DocumentService
from app.services.profile_service import ProfileService
from app.utils import errors

logger = logging.getLogger(__name__)


class DoctorService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._profiles = get_patient_profiles(db)
        self._documents = get_medical_documents(db)
        self._id_service = CareVerseIdService(db)

    # ==================================================================
    # patient list
    # ==================================================================

    def list_authorized(
        self, doctor_id: str, authorized_patient_ids: list[str]
    ) -> dict:
        """Summaries of the patients in `authorized_patient_ids`, in that order."""
        if not authorized_patient_ids:
            return {"items": [], "total": 0}

        counts = self._document_counts(authorized_patient_ids)
        items = []
        for patient_id in authorized_patient_ids:
            profile = self._profiles.find_one({"patient_id": patient_id})
            careverse_id = self._id_service.get_for_patient(patient_id)
            items.append(
                {
                    "patient_id": patient_id,
                    "careverse_id": careverse_id,
                    "full_name": (profile or {}).get("full_name") or "Name not provided",
                    "date_of_birth": (profile or {}).get("date_of_birth"),
                    "gender": (profile or {}).get("gender", "unspecified"),
                    "document_count": counts.get(patient_id, 0),
                    # A patient with no profile row is still a patient with a
                    "has_profile": profile is not None,
                }
            )

        return {"items": items, "total": len(items)}

    def get_patient_profile(self, patient_id: str) -> dict:
        """A patient's profile as an authorized doctor sees it."""
        return ProfileService(self._db).get(patient_id)

    # ==================================================================
    # documents
    # ==================================================================

    def list_documents(self, patient_id: str) -> dict:
        return DocumentService(self._db).list_for(patient_id)

    def get_document(self, patient_id: str, document_id: str) -> dict:
        return DocumentService(self._db).get(patient_id, document_id)

    def read_document_file(self, patient_id: str, document_id: str) -> tuple:
        return DocumentService(self._db).read_file(patient_id, document_id)

    # ==================================================================
    # helpers
    # ==================================================================

    def _document_counts(self, patient_ids: list[str]) -> dict[str, int]:
        """Record count per patient, for the ids already known to be authorized."""
        pipeline = [
            {"$match": {"patient_id": {"$in": patient_ids}}},
            {"$group": {"_id": "$patient_id", "count": {"$sum": 1}}},
        ]
        return {
            row["_id"]: row["count"]
            for row in self._documents.aggregate(pipeline)
        }
