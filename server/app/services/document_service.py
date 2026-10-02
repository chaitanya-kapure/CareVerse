"""The PDF document pipeline: upload -> validate -> store -> extract -> save.

Order of operations is the design here, not incidental:

    validate (cheap, no writes)
    -> read with a size cap
    -> magic-byte check
    -> write the file
    -> insert the row as `processing`
    -> extract
    -> update the row with the outcome

Two consequences worth stating, because both are invisible until they fail:

  * Nothing is persisted until the file is known to be a well-formed, allowed,
    correctly sized PDF. Validation failures therefore leave no file and no
    row behind.
  * The row exists *before* extraction runs. Text extraction is the only part
    of the pipeline that touches the content of an untrusted file, and the one
    most likely to fail. If it throws, the file and its metadata survive with
    `extraction_status = "failed"` -- the patient keeps the document they
    uploaded and can still download it. An extraction failure never fails the
    upload.

Deletion runs the other way round: the file first, then the row. An orphaned
row is a visible, retryable inconvenience; an orphaned copy of a medical
document sitting on disk is neither.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import UploadFile
from pymongo.database import Database

from app.config import settings
from app.models.collections import get_medical_documents
from app.models.medical_document import MedicalDocumentDocument, serialize_document
from app.schemas.documents import UploadMeta
from app.services import extraction_service, structured_extraction
from app.services.extraction_service import ExtractionOutcome
from app.services.storage import StorageDriver, StorageError, get_storage_driver
from app.utils import errors

logger = logging.getLogger(__name__)

# Byte-level proof of a PDF. The declared MIME type is attacker-controlled and
# the extension even more so; this is the check that actually decides.
PDF_MAGIC = b"%PDF-"

# Read in chunks rather than slurping the whole body: a client can keep
# streaming, and an unbounded `await file.read()` would let a 2 GB request
# occupy memory before the size check could ever run.
CHUNK_SIZE = 256 * 1024

# Readable fallback derived from the upload name when the patient supplies no
# title. The extension is dropped and the separators become spaces.
_WHITESPACE = re.compile(r"[\s_-]+")
_NON_TITLE = re.compile(r"[^\w\s()\-./&+']")


class DocumentService:
    def __init__(self, db: Database, driver: Optional[StorageDriver] = None) -> None:
        self._db = db
        self._docs = get_medical_documents(db)
        self._driver = driver

    @property
    def driver(self) -> StorageDriver:
        # Resolved lazily so tests can swap the driver after construction.
        if self._driver is None:
            self._driver = get_storage_driver()
        return self._driver

    # ==================================================================
    # upload
    # ==================================================================

    async def upload(
        self,
        patient_id: str,
        file: UploadFile,
        meta: UploadMeta,
    ) -> dict:
        # --- 1. cheap validation, before any bytes are read or written ---
        if not file.filename or not file.filename.strip():
            raise errors.bad_request(
                "No file was included in the upload.", code="FILE_MISSING"
            )

        content_type = (file.content_type or "").split(";")[0].strip().lower()
        if content_type not in settings.allowed_mime_list:
            raise errors.unsupported_media_type(
                "Only PDF files can be uploaded.",
                code="UNSUPPORTED_FILE_TYPE",
            )

        content = await self._read_capped(file)

        # The extension and MIME type were both asserted by the client; this
        # is where the file says what it really is.
        if not content.startswith(PDF_MAGIC):
            raise errors.bad_request(
                "That file is not a valid PDF. Please upload a PDF document.",
                code="INVALID_FILE_TYPE",
            )

        original_name = _safe_filename(file.filename)
        title = meta.title.strip() or _title_from_filename(original_name)

        # --- 2. write the file ------------------------------------------
        key = self.driver.new_key()
        try:
            self.driver.save(content, key)
        except StorageError as exc:
            logger.warning("storage write failed during upload")
            raise errors.server_error(
                "The file could not be saved to storage. Please try again.",
                code="STORAGE_FAILED",
            ) from exc

        now = _utcnow()
        document: MedicalDocumentDocument = {
            "patient_id": patient_id,
            "original_filename": original_name,
            "stored_filename": key.rsplit("/", 1)[-1],
            "storage_driver": settings.storage_driver,
            "storage_key": key,
            "mime_type": "application/pdf",
            "size_bytes": len(content),
            "title": title,
            "category": meta.category,
            "document_date": meta.document_date,
            "extraction_status": "processing",
            "extraction_error": None,
            "extracted_at": None,
            "page_count": None,
            "character_count": 0,
            "extracted_text": None,
            "extracted_data": {},
            "uploaded_at": now,
            "updated_at": now,
        }

        try:
            inserted = self._docs.insert_one(document)
        except Exception:
            # The row is the thing that failed, so undo the file. Leaving it
            # behind would silently accumulate medical documents that nothing
            # can ever list or delete.
            logger.error("failed to persist document metadata")
            try:
                self.driver.delete(key)
            except StorageError:
                logger.error("rollback of stored file also failed; key=%s", key)
            raise

        # --- 3. extract ------------------------------------------------
        # Off the event loop: pypdf is CPU-bound and parses an untrusted
        # file, so one crafted PDF must not stall every other request. The
        # structured pass runs in the same thread for the same reason -- it is
        # regex work over that same text, on up to 500,000 characters of it.
        outcome = await asyncio.to_thread(_extract_text_and_structure, content)

        # A failure here still returns the document. It is recorded as
        # `failed` and the upload succeeds -- see the module docstring.
        self._docs.update_one(
            {"_id": inserted.inserted_id, "patient_id": patient_id},
            {"$set": {**outcome, "updated_at": _utcnow()}},
        )

        stored = self._docs.find_one({"_id": inserted.inserted_id})
        if stored is None:  # pragma: no cover - vanished between calls
            raise errors.not_found("Document not found", code="DOCUMENT_NOT_FOUND")
        return serialize_document(stored, include_text=True)

    async def _read_capped(self, file: "UploadFile") -> bytes:  # noqa: F821
        max_bytes = settings.max_upload_mb * 1024 * 1024
        buffer = bytearray()
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                # Abandoned mid-stream; the caller never stores anything.
                raise errors.payload_too_large(
                    f"That file is larger than the {settings.max_upload_mb} MB limit.",
                    code="FILE_TOO_LARGE",
                )
        return bytes(buffer)

    # ==================================================================
    # read
    # ==================================================================

    def list_for(self, patient_id: str) -> dict:
        cursor = self._docs.find({"patient_id": patient_id}).sort("uploaded_at", -1)
        items = [serialize_document(doc) for doc in cursor]
        return {"items": items, "total": len(items)}

    def get(self, patient_id: str, document_id: str) -> dict:
        return serialize_document(self._find(patient_id, document_id), include_text=True)

    def read_file(self, patient_id: str, document_id: str) -> tuple[str, str, bytes]:
        """Return (content_type, download_filename, bytes) for a stored PDF."""
        doc = self._find(patient_id, document_id)
        key = doc.get("storage_key")
        if not key:
            raise errors.not_found(
                "This document has no stored file.", code="DOCUMENT_FILE_MISSING"
            )
        try:
            content = self.driver.open(key)
        except StorageError as exc:
            logger.warning("stored file unreadable for document=%s", document_id)
            raise errors.not_found(
                "The original file for this document is unavailable.",
                code="DOCUMENT_FILE_MISSING",
            ) from exc

        mime = doc.get("mime_type") or "application/pdf"
        filename = doc.get("original_filename") or f"{document_id}.pdf"
        return mime, filename, content

    # ==================================================================
    # delete
    # ==================================================================

    def delete(self, patient_id: str, document_id: str) -> None:
        doc = self._find(patient_id, document_id)
        key = doc.get("storage_key")

        # File first -- see the module docstring for why the order matters.
        if key:
            try:
                self.driver.delete(key)
            except StorageError as exc:
                logger.warning("storage delete failed for document=%s", document_id)
                raise errors.server_error(
                    "The document could not be removed from storage. Please try again.",
                    code="STORAGE_DELETE_FAILED",
                ) from exc

        self._docs.delete_one({"_id": doc["_id"], "patient_id": patient_id})

    # ==================================================================
    # helpers
    # ==================================================================

    def _find(self, patient_id: str, document_id: str) -> MedicalDocumentDocument:
        """Load one document, scoped to its owner.

        The scope is in the query itself rather than in a comparison after it,
        so a document belonging to another patient is indistinguishable from
        one that does not exist. Both answer 404: replying 403 would confirm
        that someone else's record with that id is real.
        """
        if not ObjectId.is_valid(document_id):
            raise errors.not_found("Document not found", code="DOCUMENT_NOT_FOUND")

        doc = self._docs.find_one(
            {"_id": ObjectId(document_id), "patient_id": patient_id}
        )
        if doc is None:
            raise errors.not_found("Document not found", code="DOCUMENT_NOT_FOUND")
        return doc


# ---------------------------------------------------------------------
# module helpers
# ---------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _extract_text_and_structure(content: bytes) -> ExtractionOutcome:
    """Text first, and only then structured facts.

    The ordering is the safety property, not an implementation detail. A
    document that came back `needs_ocr` or `failed` has no text to read, so
    this returns before the structured pass is ever reached -- there is no
    branch anywhere that could build `extracted_data` out of a status or a
    filename. Those documents keep `extracted_data = {}` exactly as they did
    in Phase 2, and a future summary can tell "no facts found" apart from
    "this record was never readable".

    A document that extracted cleanly but contains nothing this parser
    recognises also ends up with `{}`. That is the same distinction, and it is
    why this must not raise: a parser that could not find a lab value has not
    failed to extract a lab value, and must not turn a stored document into a
    failed upload by saying so.
    """
    outcome = extraction_service.extract_text(content)
    if outcome.get("extraction_status") != "completed":
        return outcome

    outcome["extracted_data"] = structured_extraction.extract_structured(
        outcome.get("extracted_text") or ""
    )
    return outcome


def _safe_filename(name: str) -> str:
    """Reduce an upload name to a displayable basename.

    Any directory component is dropped: the client controls this string and
    it will be echoed back into the UI and into a Content-Disposition header,
    where `../../` and newlines have business being nowhere.
    """
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = base.replace("\r", " ").replace("\n", " ").replace("\x00", "")
    base = base.strip().lstrip(".")
    return base[:255] or "document.pdf"


def _title_from_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    cleaned = _NON_TITLE.sub(" ", stem)
    spaced = _WHITESPACE.sub(" ", cleaned).strip()
    if not spaced:
        return "Medical document"
    # Capitalise the leading word only. `str.title()` would mangle names and
    # abbreviations that are already correct ("CBC_HbA1c" -> "Cbc Hba1c").
    titled = spaced[0].upper() + spaced[1:]
    return titled[:200]
