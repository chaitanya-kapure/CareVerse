"""PDF text extraction."""

import io
import logging
from datetime import datetime, timezone
from typing import Optional

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.models.medical_document import ExtractionStatus
from app.services import ocr_service

logger = logging.getLogger(__name__)

# Below this many characters of extracted text the document is treated as
NEEDS_OCR_MIN_CHARS = 10

# Maximum characters stored per document. A pathological 5000-page PDF should
MAX_EXTRACTED_CHARS = 500_000

# Extraction is synchronous within the request, so it has to be bounded. The
MAX_PAGES = 1_000


class ExtractionOutcome(dict):
    """The fixed shape every result carries, so a caller cannot depend on a"""


def _outcome(
    status: ExtractionStatus,
    text: Optional[str],
    pages: Optional[int],
    error: Optional[str] = None,
) -> ExtractionOutcome:
    return ExtractionOutcome(
        extraction_status=status,
        extracted_text=text,
        page_count=pages,
        character_count=len(text) if text else 0,
        extraction_error=error,
        extracted_at=datetime.now(timezone.utc),
    )


def _normalize(raw: str) -> str:
    """Make extracted text predictable without altering what it says."""
    text = raw.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def extract_text(content: bytes) -> ExtractionOutcome:
    """Extract embedded text from PDF bytes."""
    if not content:
        return _outcome("failed", None, None, "The file is empty.")

    try:
        reader = PdfReader(io.BytesIO(content))
    except PyPdfError as exc:
        # pypdf's own error hierarchy: EOF marker missing, invalid xref, etc.
        logger.warning("PDF could not be read: %s", type(exc).__name__)
        return _outcome("failed", None, None, "The file could not be read as a PDF.")
    except Exception as exc:  # pypdf also raises low-level errors for junk input
        logger.warning("PDF parse failed: %s", type(exc).__name__)
        return _outcome("failed", None, None, "The file could not be read as a PDF.")

    # Decryption has to be settled before anything touches `reader.pages`,
    # because reading a page tree on an encrypted file raises.
    if reader.is_encrypted:
        # Without a password we cannot read it, and guessing passwords is not
        # this phase's job. Say so rather than returning an empty document.
        try:
            unlocked = reader.decrypt("")
        except Exception:
            unlocked = None
        if not unlocked:
            logger.info("encrypted PDF rejected for extraction")
            return _outcome(
                "failed",
                None,
                None,
                "This PDF is password protected, so its text could not be read.",
            )

    # --- per-page extraction ------------------------------------------------
    pages_read = 0
    pieces: list[str] = []
    try:
        pages_iter = list(reader.pages)
    except Exception as exc:
        logger.warning("page list failed: %s", type(exc).__name__)
        return _outcome("failed", None, None, "The file could not be read as a PDF.")

    page_count = len(pages_iter)

    if page_count > MAX_PAGES:
        logger.info("extraction refused: %d pages exceeds cap", page_count)
        return _outcome(
            "failed",
            None,
            page_count,
            f"This document has {page_count} pages, which is more than the "
            f"{MAX_PAGES}-page limit for automatic text extraction. The original "
            "file is still available to view and download.",
        )

    for page in pages_iter:
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("page extraction failed: %s", type(exc).__name__)
            continue
        pages_read += 1
        cleaned = _normalize(page_text)
        if cleaned:
            pieces.append(cleaned)

    if pages_read == 0:
        return _outcome("failed", None, page_count, "No page in this PDF could be read.")

    combined = "\n\n".join(pieces)

    if len(combined) >= MAX_EXTRACTED_CHARS:
        logger.info(
            "extracted text truncated at %d chars (pages=%s)",
            MAX_EXTRACTED_CHARS,
            page_count,
        )
        combined = combined[:MAX_EXTRACTED_CHARS]

    if len(combined.strip()) < NEEDS_OCR_MIN_CHARS:
        # Document has little/no embedded digital text (scanned or image-only PDF).
        # Run Optical Character Recognition (OCR) to extract text.
        logger.info("Embedded text below threshold. Running OCR pass...")
        try:
            ocr_text, _ = ocr_service.ocr_pdf(content, max_pages=min(page_count, 50))
            if ocr_text and len(ocr_text.strip()) >= NEEDS_OCR_MIN_CHARS:
                cleaned_ocr = _normalize(ocr_text)
                if len(cleaned_ocr) >= MAX_EXTRACTED_CHARS:
                    cleaned_ocr = cleaned_ocr[:MAX_EXTRACTED_CHARS]
                logger.info("OCR successfully extracted %d characters from scanned PDF", len(cleaned_ocr))
                return _outcome("completed", cleaned_ocr, page_count)
        except Exception as ocr_err:
            logger.warning("OCR pass failed: %s", ocr_err)

        # Readable document, no embedded text and OCR found nothing: the blank scan case.
        return _outcome("needs_ocr", None, page_count)

    return _outcome("completed", combined, page_count)
