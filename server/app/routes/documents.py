"""Medical document endpoints: list, upload, read, download, delete.

Ownership is never derived from these paths -- there is no patient id in any
of them. The id in `{documentId}` is the only variable, and a document id
belonging to somebody else is answered with 404 by the service (see
`DocumentService._find`), so substituting ids changes nothing.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.controllers.document_controller import DocumentController
from app.middlewares.auth_middleware import require_roles
from app.models.user import UserDocument
from app.schemas.documents import (
    DocumentListResponse,
    MedicalDocumentDetailResponse,
)

router = APIRouter(prefix="/patients/me/documents", tags=["documents"])

PatientUser = Annotated[UserDocument, Depends(require_roles("patient"))]

# A doctor may never reach these handlers: being a doctor is not
# authorization for anything here, only an explicit grant is (Phase 3).


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="Own records, newest first",
)
async def list_documents(user: PatientUser):
    return await DocumentController.list_documents(user)


@router.post(
    "",
    response_model=MedicalDocumentDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF record",
)
async def upload_document(
    user: PatientUser,
    file: Annotated[UploadFile, File(description="A PDF file, up to MAX_UPLOAD_MB")],
    title: Annotated[str, Form()] = "",
    category: Annotated[str, Form()] = "other",
    document_date: Annotated[Optional[str], Form()] = None,
):
    """Validate, store, extract, and answer with the finished record.

    Extraction runs before the response, off the event loop, so the status
    returned is the real outcome rather than a `pending` placeholder the
    client would have to poll for. A failure *during* extraction still
    answers 201 -- with `extraction_status = "failed"` -- because the file and
    its metadata are already stored and must not be lost over it.
    """
    return await DocumentController.upload_document(
        user, file, title=title, category=category, document_date=document_date
    )


@router.get(
    "/{document_id}",
    response_model=MedicalDocumentDetailResponse,
    summary="Metadata and extracted text for one record",
)
async def get_document(document_id: str, user: PatientUser):
    return await DocumentController.get_document(document_id, user)


@router.get(
    "/{document_id}/file",
    summary="Stream the original PDF",
)
async def get_document_file(document_id: str, user: PatientUser):
    """Never served as a static file: a predictable URL over
    `server/storage` would bypass authorization entirely."""
    return await DocumentController.get_document_file(document_id, user)


@router.delete(
    "/{document_id}",
    summary="Delete a record and its stored file",
)
async def delete_document(document_id: str, user: PatientUser):
    return await DocumentController.delete_document(document_id, user)
