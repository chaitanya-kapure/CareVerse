"""Doctor-facing endpoints: authorized patients and their records."""

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
        authorized_id = _authorized_patient_id(db, user, patient_id)
        return DoctorService(db).get_document(authorized_id, document_id)

    @staticmethod
    async def get_document_file(
        patient_id: str, document_id: str, user: UserDocument
    ) -> Response:
        """Stream a record's original PDF to an authorized doctor."""
        db = get_db()
        authorized_id = _authorized_patient_id(db, user, patient_id)
        mime, filename, content = DoctorService(db).read_document_file(
            authorized_id, document_id
        )
        return pdf_response(content, mime, filename)


def _authorized_patient_id(db, user: UserDocument, patient_id: str) -> str:
    """Validate a requested patient id, and return it only if permitted."""
    requested = resolve_patient_id(patient_id)
    assert_patient_access(db, user, requested)
    return requested
