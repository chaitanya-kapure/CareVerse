"""Summary response schemas."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

SummaryProviderLiteral = Literal["mock", "openai", "anthropic", "custom"]


class SummaryItemResponse(BaseModel):
    """One attributed statement."""

    text: str
    source_document_id: str = Field(
        min_length=1,
        description="Id of the `medical_documents` row this line was copied from.",
    )
    source_text: Optional[str] = Field(
        default=None,
        description="The document's own wording, when it fits.",
    )


class SummarySectionResponse(BaseModel):
    """A titled block. Always present, even when it has nothing to report."""

    key: str
    title: str
    items: List[SummaryItemResponse] = Field(default_factory=list)
    # "Not found in the uploaded records." when empty, else null. Never absent
    # and never an empty string: silence would read as "nothing abnormal".
    empty_note: Optional[str] = None


class PatientSummaryResponse(BaseModel):
    """The stored summary, exactly as `serialize_summary` writes it."""

    id: str
    patient_id: str
    provider: SummaryProviderLiteral
    # Stored on the document, never inferred from the prose. The UI shows a
    # demo label whenever this is true.
    is_mock: bool
    model: Optional[str] = None
    # Always `AI_SUMMARY_DISCLAIMER` from the server. No provider sets it.
    disclaimer: str
    overview: str
    sections: List[SummarySectionResponse] = Field(default_factory=list)
    source_document_ids: List[str] = Field(default_factory=list)
    source_document_count: int = 0
    # Documents that were present but could not be read (needs_ocr / failed).
    unreadable_document_count: int = 0
    generated_at: datetime
