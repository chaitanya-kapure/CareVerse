"""`medical_documents` collection.

The original uploaded file is never modified. `extracted_text` and
`extracted_data` are derived data layered on top, and the file itself always
remains reachable so a doctor can verify the summary.
"""

from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

# `needs_ocr` is the honest outcome for a scanned/image-only PDF: we say we
# cannot read it rather than inventing text. See extractionService.
ExtractionStatus = Literal[
    "pending",      # queued, not yet processed
    "processing",   # extraction in progress
    "completed",    # text extracted successfully
    "needs_ocr",    # little/no embedded text -> OCR required
    "failed",       # extraction errored
]

DocumentCategory = Literal[
    "lab_report",
    "prescription",
    "discharge_summary",
    "imaging",
    "other",
]


class ExtractedData(TypedDict, total=False):
    """Structured fields pulled from the document text.

    Every value here is quoted or copied from the document. When a field
    cannot be found it is omitted rather than guessed.
    """
    report_title: Optional[str]
    document_date: Optional[str]       # ISO date if detected in the text
    referring_facility: Optional[str]
    referring_doctor: Optional[str]
    # [{ name, value, unit, reference_range, flag, source_text }]
    lab_values: list[dict[str, Any]]
    # [{ name, dosage, frequency, source_text }]
    medications: list[dict[str, Any]]
    # Verbatim sentences containing abnormal / positive / elevated markers.
    abnormal_findings: list[dict[str, Any]]
    # Verbatim sentences that state a diagnosis already made elsewhere.
    stated_conditions: list[dict[str, Any]]


class MedicalDocumentDocument(TypedDict, total=False):
    _id: object
    patient_id: str                    # -> users._id of the owner
    # --- file metadata ---
    original_filename: str
    stored_filename: str               # opaque, generated; never user input
    storage_driver: str                # "local" today, "s3" later
    storage_key: str                   # location handle inside the driver
    mime_type: str
    size_bytes: int
    # --- classification ---
    title: str
    category: DocumentCategory
    document_date: Optional[str]       # date on the document, if found
    # --- extraction ---
    extraction_status: ExtractionStatus
    extraction_error: Optional[str]
    extracted_at: Optional[datetime]
    page_count: Optional[int]
    character_count: int
    extracted_text: Optional[str]
    extracted_data: ExtractedData
    uploaded_at: datetime
    updated_at: datetime


def serialize_document(doc: MedicalDocumentDocument, include_text: bool = False) -> dict:
    """List/metadata shape. `extracted_text` is opt-in because it is large."""
    payload = {
        "id": str(doc["_id"]),
        "patient_id": doc.get("patient_id"),
        "original_filename": doc.get("original_filename"),
        "mime_type": doc.get("mime_type"),
        "size_bytes": doc.get("size_bytes"),
        "title": doc.get("title"),
        "category": doc.get("category"),
        "document_date": doc.get("document_date"),
        "extraction_status": doc.get("extraction_status"),
        "extraction_error": doc.get("extraction_error"),
        "page_count": doc.get("page_count"),
        "character_count": doc.get("character_count", 0),
        "uploaded_at": doc.get("uploaded_at"),
        "has_text": bool(doc.get("extracted_text")),
    }
    if include_text:
        payload["extracted_text"] = doc.get("extracted_text")
        payload["extracted_data"] = doc.get("extracted_data", {})
    return payload
