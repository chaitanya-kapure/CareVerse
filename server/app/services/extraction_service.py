"""PDF text extraction.

Scope of this module: turn PDF bytes into text, and say honestly when it
cannot. It does not interpret what it read.

Two rules that are easy to lose and impossible to undo once they leak into
the data:

  * Nothing is invented. An image-only or scanned PDF has no embedded text,
    and the correct answer for it is `needs_ocr` with no text at all -- not
    a plausible reconstruction, and not an empty string that a later screen
    could mistake for "this record says nothing".
  * The extraction status is never a guess. `completed` means pypdf actually
    returned characters; `failed` means it raised; `needs_ocr` means it read
    the document fine and there was simply nothing there to read.

OCR is deliberately not implemented here. `ExtractionStatus` already carries
`needs_ocr` so the UI and the schema can state the outcome, and the OCR pass
can be added later behind this function without changing the caller.
"""

import io
import logging
from datetime import datetime, timezone
from typing import Optional

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.models.medical_document import ExtractionStatus

logger = logging.getLogger(__name__)

# Below this many characters of extracted text the document is treated as
# image-only. A real page of lab results carries orders of magnitude more;
# an image-only page yields nothing, or at most a stray character or two from
# a page number. The constant is named so the trade-off is visible: raising it
# risks marking a very short-but-real record as unreadable.
NEEDS_OCR_MIN_CHARS = 10

# Maximum characters stored per document. A pathological 5000-page PDF should
# not be able to write an unbounded string into one Mongo document (16 MB cap),
# and anything past this is not going to be read in the UI anyway.
MAX_EXTRACTED_CHARS = 500_000

# Extraction is synchronous within the request, so it has to be bounded. The
# byte cap does not bound the work: many tiny pages fit in a few MB, and
# `extract_text()` runs per page. Above this the document is refused for
# extraction rather than truncated -- silently extracting half of a medical
# record is worse than saying we did not extract it at all. The stored file is
# unaffected and stays downloadable.
MAX_PAGES = 1_000


class ExtractionOutcome(dict):
    """The fixed shape every result carries, so a caller cannot depend on a
    partial result.

    Keys: `extraction_status`, `extracted_text`, `page_count`,
    `character_count`, `extraction_error`, `extracted_at`.
    """


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
    """Make extracted text predictable without altering what it says.

    Normalization is limited to whitespace: line endings are unified and NUL
    bytes (which Mongo will reject) are dropped. Rewrapping, reflowing or
    "cleaning up" wording here would quietly edit a medical record.
    """
    text = raw.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def extract_text(content: bytes) -> ExtractionOutcome:
    """Extract embedded text from PDF bytes.

    Never raises. Every failure path returns a status, because a failure here
    must degrade the document to `failed` rather than failing the upload that
    already stored the file successfully.
    """
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
    # One unreadable page must not discard pages that did read. pypdf can
    # raise on a single damaged object while the rest of the file is fine,
    # and walking the page tree can itself fail on a malformed catalog.
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
        # Readable document, no embedded text: the scan case. Storing None
        # rather than "" so no screen can present "no text found" as content.
        return _outcome("needs_ocr", None, page_count)

    return _outcome("completed", combined, page_count)
