"""Upload request and document response schemas.

The upload itself is `multipart/form-data`, so its inputs are declared with
`Form(...)` in the route rather than as one Pydantic body. What lives here
are the responses -- the shape the client reads -- plus validation for the
small set of form fields that travel alongside the file.
"""

from datetime import date
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

DOCUMENT_CATEGORIES = ("lab_report", "prescription", "discharge_summary", "imaging", "other")


def _check_iso_date(value: str, field: str) -> str:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError(f"{field} must be an ISO date in the form YYYY-MM-DD")
    try:
        year, month, day = (int(part) for part in value.split("-"))
        # Rejects 2026-02-30, which a plain string comparison would accept.
        date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"{field} is not a real calendar date") from exc
    return value


class MedicalDocumentSummaryResponse(BaseModel):
    """Metadata only.

    `extracted_text` is deliberately absent from lists: it is large enough
    that resending it for every row would dominate the response, so it is
    opt-in on the detail endpoint.
    """

    id: str
    patient_id: str
    original_filename: str
    mime_type: str
    size_bytes: int
    title: str
    category: str
    document_date: Optional[str] = None
    extraction_status: str
    extraction_error: Optional[str] = None
    page_count: Optional[int] = None
    character_count: int = 0
    uploaded_at: datetime
    has_text: bool = False


class MedicalDocumentDetailResponse(MedicalDocumentSummaryResponse):
    extracted_text: Optional[str] = None
    extracted_data: dict = Field(default_factory=dict)


class DocumentListResponse(BaseModel):
    items: list[MedicalDocumentSummaryResponse]
    total: int


class UploadMeta(BaseModel):
    """Validated form fields that arrive next to the file.

    Separate from the request body because FastAPI parses a multipart
    request field-by-field rather than as one JSON object.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(default="", max_length=200)
    category: str = "other"
    document_date: Optional[str] = Field(default=None, max_length=10)

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        if value not in DOCUMENT_CATEGORIES:
            raise ValueError(f"Category must be one of {', '.join(DOCUMENT_CATEGORIES)}")
        return value

    @field_validator("document_date")
    @classmethod
    def _validate_document_date(cls, value: Optional[str]) -> Optional[str]:
        # The date printed on the document, when the patient knows it.
        # Absent means absent -- nothing here is inferred from the file.
        if not value:
            return None
        return _check_iso_date(value, "Document date")
