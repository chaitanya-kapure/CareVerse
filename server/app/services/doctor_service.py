"""What an authorized doctor is allowed to read.

This layer is deliberately thin. It owns no query logic of its own for
profiles or documents: it decides *which* patient ids the caller may act on,
and then delegates to the same `ProfileService` and `DocumentService` the
patient's own screens use. A doctor's view of a record and the patient's view
of that same record therefore come out of one implementation, and there is no
second place for an ownership rule to be forgotten.

The single most important property of this file is that it is only ever
called *after* `assert_patient_access` has approved the (doctor, patient)
pair. Every method takes the already-authorized `patient_id` as an argument
rather than re-deriving it, so a caller cannot pass an id it has not been
checked for.

The patient list is the one place that reads across patients, and it does so
by starting from the grant collection -- never from the patient collection.
There is no code path anywhere that lists patients and filters afterwards,
because that is the shape that turns into a directory.
"""

import logging

from pymongo.database import Database

from app.models.collections import (
    get_medical_documents,
    get_patient_profiles,
)
from app.services.document_service import DocumentService
from app.services.profile_service import ProfileService
from app.utils import errors

logger = logging.getLogger(__name__)


class DoctorService:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._profiles = get_patient_profiles(db)
        self._documents = get_medical_documents(db)

    # ==================================================================
    # patient list
    # ==================================================================

    def list_authorized(
        self, doctor_id: str, authorized_patient_ids: list[str]
    ) -> dict:
        """Summaries of the patients in `authorized_patient_ids`, in that order.

        `authorized_patient_ids` is passed in rather than looked up here so the
        set of patients a request may see is decided in exactly one place --
        the grant collection -- and this method cannot widen it.

        The document count is a single aggregation over the authorized ids
        rather than one query per patient: the alternative is a query per row
        on a screen that is explicitly a list.
        """
        if not authorized_patient_ids:
            return {"items": [], "total": 0}

        counts = self._document_counts(authorized_patient_ids)
        items = []
        for patient_id in authorized_patient_ids:
            profile = self._profiles.find_one({"patient_id": patient_id})
            items.append(
                {
                    "patient_id": patient_id,
                    "full_name": (profile or {}).get("full_name") or "Name not provided",
                    "date_of_birth": (profile or {}).get("date_of_birth"),
                    "gender": (profile or {}).get("gender", "unspecified"),
                    "document_count": counts.get(patient_id, 0),
                    # A patient with no profile row is still a patient with a
                    # grant; surfacing the id keeps the row clickable instead
                    # of rendering an entry that cannot be opened.
                    "has_profile": profile is not None,
                }
            )

        return {"items": items, "total": len(items)}

    def get_patient_profile(self, patient_id: str) -> dict:
        """A patient's profile as an authorized doctor sees it.

        Delegates to `ProfileService.get`, which is the same code the patient's
        own profile screen runs. It creates the row if it is somehow absent,
        so this does not need a second not-found path.
        """
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
        """Record count per patient, for the ids already known to be authorized.

        Counts every document regardless of extraction status. A record whose
        text could not be read is still a record the patient has, and hiding it
        would tell a doctor the patient uploaded less than they did.
        """
        pipeline = [
            {"$match": {"patient_id": {"$in": patient_ids}}},
            {"$group": {"_id": "$patient_id", "count": {"$sum": 1}}},
        ]
        return {
            row["_id"]: row["count"]
            for row in self._documents.aggregate(pipeline)
        }
