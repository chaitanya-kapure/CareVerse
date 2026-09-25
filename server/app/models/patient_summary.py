"""`patient_summaries` collection.

One summary per patient. Regenerated after every successful document
extraction, so it always reflects the current record set.

`provider` and `is_mock` are stored, not inferred at read time, so the UI can
honestly label a deterministic fallback summary as demo output.
"""

from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

SummaryProvider = Literal["mock", "openai", "anthropic", "custom"]


class SummarySection(TypedDict, total=False):
    """A titled block of the summary.

    `items` are either strings or objects carrying a `source` reference back
    to a document, which is what keeps the summary traceable.
    """
    key: str
    title: str
    items: list[Any]
    # Rendered when the section has nothing real to report, e.g.
    # "Not found in the uploaded records." Never leave it silently blank.
    empty_note: Optional[str]


class PatientSummaryDocument(TypedDict, total=False):
    _id: object
    patient_id: str                    # -> users._id, unique (1:1)
    provider: SummaryProvider
    is_mock: bool                      # True => deterministic fallback
    model: Optional[str]
    disclaimer: str                    # verbatim AI_SUMMARY_DISCLAIMER
    overview: str
    sections: list[SummarySection]
    # Document ids that fed this summary, oldest -> newest.
    source_document_ids: list[str]
    source_document_count: int
    # Documents that were present but could not be read (needs_ocr/failed).
    unreadable_document_count: int
    generated_at: datetime


def serialize_summary(summary: PatientSummaryDocument) -> dict:
    return {
        "id": str(summary["_id"]),
        "patient_id": summary.get("patient_id"),
        "provider": summary.get("provider"),
        "is_mock": summary.get("is_mock", True),
        "model": summary.get("model"),
        "disclaimer": summary.get("disclaimer", ""),
        "overview": summary.get("overview", ""),
        "sections": summary.get("sections", []),
        "source_document_ids": summary.get("source_document_ids", []),
        "source_document_count": summary.get("source_document_count", 0),
        "unreadable_document_count": summary.get("unreadable_document_count", 0),
        "generated_at": summary.get("generated_at"),
    }
