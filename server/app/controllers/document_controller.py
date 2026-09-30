"""Document controller: the read/download/delete surface of the pipeline.

Every method starts with `assert_own_records`, which returns the id all
subsequent queries are scoped by. Nothing here decides ownership for itself.
"""

from fastapi import Response, UploadFile
from pydantic import ValidationError

from app.database import get_db
from app.middlewares.auth_middleware import assert_own_records
from app.models.user import UserDocument
from app.schemas.documents import UploadMeta
from app.services.document_service import DocumentService
from app.utils import errors
from app.utils.responses import pdf_response


class DocumentController:
    @staticmethod
    async def list_documents(user: UserDocument) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return DocumentService(db).list_for(patient_id)

    @staticmethod
    async def upload_document(
        user: UserDocument,
        file: UploadFile,
        title: str = "",
        category: str = "other",
        document_date: str | None = None,
    ) -> dict:
        db = get_db()
        # Ownership first, so a non-patient is rejected before a single byte
        # is read off the socket.
        patient_id = assert_own_records(db, user)

        try:
            meta = UploadMeta(
                title=title, category=category, document_date=document_date
            )
        except ValidationError as exc:
            # These fields arrive as raw multipart strings, so Pydantic never
            # saw them at the request boundary -- see `errors.from_pydantic`.
            raise errors.from_pydantic(exc) from exc

        return await DocumentService(db).upload(patient_id, file, meta)

    @staticmethod
    async def get_document(document_id: str, user: UserDocument) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        return DocumentService(db).get(patient_id, document_id)

    @staticmethod
    async def get_document_file(document_id: str, user: UserDocument) -> Response:
        """Stream the original PDF back to its owner.

        Bytes rather than a file path: the storage driver is an abstraction,
        and the moment this handler reaches for `Path` it would assume local
        disk and break the day `STORAGE_DRIVER` changes.

        Nothing under `server/storage` is ever served statically. A direct
        URL to the storage directory would bypass authorization entirely.
        """
        db = get_db()
        patient_id = assert_own_records(db, user)
        mime, filename, content = DocumentService(db).read_file(
            patient_id, document_id
        )
        return pdf_response(content, mime, filename)

    @staticmethod
    async def delete_document(document_id: str, user: UserDocument) -> dict:
        db = get_db()
        patient_id = assert_own_records(db, user)
        DocumentService(db).delete(patient_id, document_id)
        return {
            "detail": "The document has been deleted.",
            "code": "DOCUMENT_DELETED",
        }
