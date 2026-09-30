"""Doctor-facing endpoints: authorized patients and their records.

Every method here follows the same three steps, in this order:

    1. the route dependency has already proved the caller is a doctor
    2. `assert_patient_access` proves THIS doctor has a grant for THIS patient
    3. only then is `DoctorService` called, with the authorized patient id

Step 2 is what makes the rest safe, and the id it validates is the same id
step 3 queries by. A caller cannot widen their own scope here even by editing
a request, because the id is never taken from the request and used
unvalidated -- it is taken from the request *and checked* before it is used
for anything.

The patient-list route is the one exception to the "check one patient" shape,
and it is still the same rule applied as a set: `AccessService` returns the
ids this doctor holds grants for, and only those are loaded. There is no
query that starts from the patient collection, so a doctor cannot use the list
to discover that some other patient exists.
"""

from fastapi import Response

from app.database import get_db
from app.middlewares.auth_middleware import assert_patient_access, resolve_patient_id
from app.models.user import UserDocument
from app.services.access_service import AccessService
from app.services.doctor_service import DoctorService
from app.utils.responses import pdf_response


class DoctorController:
    @staticmethod
    async def list_patients(user: UserDocument) -> dict:
        db = get_db()
        # No per-patient check here: the set *is* the authorization. Starting
        # from the grants means an unauthorized patient is never loaded, so
        # the response cannot leak one by being filtered out of it.
        doctor_id = str(user["_id"])
        authorized = AccessService(db).list_authorized_patient_ids(doctor_id)
        return DoctorService(db).list_authorized(doctor_id, authorized)

    @staticmethod
    async def get_patient(patient_id: str, user: UserDocument) -> dict:
        db = get_db()
        authorized_id = _authorized_patient_id(db, user, patient_id)
        return DoctorService(db).get_patient_profile(authorized_id)

    @staticmethod
    async def list_documents(patient_id: str, user: UserDocument) -> dict:
        db = get_db()
        authorized_id = _authorized_patient_id(db, user, patient_id)
        return DoctorService(db).list_documents(authorized_id)

    @staticmethod
    async def get_document(patient_id: str, document_id: str, user: UserDocument) -> dict:
        db = get_db()
        # Patient authorization first, then the document lookup. In this
        # order a doctor without a grant never reaches the document query at
        # all, and a document belonging to a different patient is reported as
        # not found rather than as forbidden.
        authorized_id = _authorized_patient_id(db, user, patient_id)
        return DoctorService(db).get_document(authorized_id, document_id)

    @staticmethod
    async def get_document_file(
        patient_id: str, document_id: str, user: UserDocument
    ) -> Response:
        """Stream a record's original PDF to an authorized doctor.

        Byte-for-byte the same path the patient uses: the same
        `DocumentService.read_file`, the same driver, the same headers. No
        second storage implementation and no doctor-only file route, so
        there is one place where file access is authorized and one place
        where the file is read.
        """
        db = get_db()
        authorized_id = _authorized_patient_id(db, user, patient_id)
        mime, filename, content = DoctorService(db).read_document_file(
            authorized_id, document_id
        )
        return pdf_response(content, mime, filename)


def _authorized_patient_id(db, user: UserDocument, patient_id: str) -> str:
    """Validate a requested patient id, and return it only if permitted.

    `resolve_patient_id` rejects a malformed id before it can reach a query.
    `assert_patient_access` then answers the only question that matters --
    does this doctor hold a live grant for this patient -- and raises 403
    `NO_PATIENT_ACCESS` when they do not.

    That 403 is the same answer for "no such patient" and "a patient who has
    not authorized you", because the grant lookup does not consult the patient
    collection. A doctor therefore learns only that they have no access, and
    cannot use the difference to find out whether an id is real.
    """
    requested = resolve_patient_id(patient_id)
    assert_patient_access(db, user, requested)
    return requested
