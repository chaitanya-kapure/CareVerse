"""The PDF document pipeline: upload -> validate -> store -> extract -> save."""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import UploadFile
from pymongo.database import Database

from app.config import settings
from app.models.collections import get_medical_documents, get_patient_profiles, get_users
from app.services.careverse_id_service import CareVerseIdService
from app.models.medical_document import MedicalDocumentDocument, serialize_document
from app.schemas.documents import UploadMeta
from app.services import clinical_analyzer, extraction_service, structured_extraction
from app.services.extraction_service import ExtractionOutcome
from app.services.storage import StorageDriver, StorageError, get_storage_driver
from app.utils import errors

logger = logging.getLogger(__name__)

# Byte-level proof of a PDF. The declared MIME type is attacker-controlled and
# the extension even more so; this is the check that actually decides.
PDF_MAGIC = b"%PDF-"

# Read in chunks rather than slurping the whole body: a client can keep
CHUNK_SIZE = 256 * 1024

# Readable fallback derived from the upload name when the patient supplies no
# title. The extension is dropped and the separators become spaces.
_WHITESPACE = re.compile(r"[\s_-]+")
_NON_TITLE = re.compile(r"[^\w\s()\-./&+']")


class DocumentService:
    def __init__(self, db: Database, driver: Optional[StorageDriver] = None) -> None:
        self._db = db
        self._docs = get_medical_documents(db)
        self._users = get_users(db)
        self._profiles = get_patient_profiles(db)
        self._id_service = CareVerseIdService(db)
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
        if content_type not in settings.allowed_mime_list and not (
            file.filename and file.filename.lower().endswith((".pdf", ".jpg", ".jpeg", ".png", ".webp"))
        ):
            raise errors.unsupported_media_type(
                "Only PDF and image files (JPG, PNG, WebP) can be uploaded.",
                code="UNSUPPORTED_FILE_TYPE",
            )

        content = await self._read_capped(file)

        # Validate byte signature
        is_pdf = content.startswith(PDF_MAGIC)
        is_jpeg = content.startswith(b"\xff\xd8\xff")
        is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
        is_webp = content.startswith(b"RIFF") and len(content) > 12 and content[8:12] == b"WEBP"

        if not (is_pdf or is_jpeg or is_png or is_webp):
            raise errors.bad_request(
                "That file is not a supported document. Please upload a PDF or image document (JPG, PNG).",
                code="INVALID_FILE_TYPE",
            )

        # If an image was uploaded, convert it to a standard PDF document so storage and downstream viewers remain uniform
        if not is_pdf and (is_jpeg or is_png or is_webp):
            try:
                import io
                from PIL import Image
                img = Image.open(io.BytesIO(content)).convert("RGB")
                pdf_buf = io.BytesIO()
                img.save(pdf_buf, format="PDF")
                content = pdf_buf.getvalue()
            except Exception as conv_err:
                logger.warning("Failed to convert image to PDF: %s", conv_err)
                raise errors.bad_request(
                    "The uploaded image could not be processed into a medical document.",
                    code="IMAGE_CONVERSION_FAILED",
                ) from conv_err

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
            logger.error("failed to persist document metadata")
            try:
                self.driver.delete(key)
            except StorageError:
                logger.error("rollback of stored file also failed; key=%s", key)
            raise

        # --- 3. extract ------------------------------------------------
        outcome = await asyncio.to_thread(_extract_text_and_structure, content, meta.category)

        # A failure here still returns the document. It is recorded as
        # `failed` and the upload succeeds -- see the module docstring.
        self._docs.update_one(
            {"_id": inserted.inserted_id, "patient_id": patient_id},
            {"$set": {**outcome, "updated_at": _utcnow()}},
        )

        stored = self._docs.find_one({"_id": inserted.inserted_id})
        if stored is None:  # pragma: no cover - vanished between calls
            raise errors.not_found("Document not found", code="DOCUMENT_NOT_FOUND")
        cid, name = self._resolve_patient_info(patient_id)
        return serialize_document(
            stored,
            include_text=True,
            patient_careverse_id=cid,
            patient_name=name,
        )

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

    def _resolve_patient_info(self, patient_id: str) -> tuple[Optional[str], Optional[str]]:
        cid = self._id_service.get_for_patient(patient_id)
        name = None
        profile = self._profiles.find_one({"patient_id": patient_id})
        if profile and profile.get("full_name"):
            name = profile["full_name"]
        elif ObjectId.is_valid(patient_id):
            u = self._users.find_one({"_id": ObjectId(patient_id)})
            if u:
                name = u.get("name")
        return cid, name

    def list_for(self, patient_id: str) -> dict:
        cid, name = self._resolve_patient_info(patient_id)
        cursor = self._docs.find({"patient_id": patient_id}).sort("uploaded_at", -1)
        items = [
            serialize_document(
                doc,
                include_text=False,
                patient_careverse_id=cid,
                patient_name=name,
            )
            for doc in cursor
        ]
        return {"items": items, "total": len(items)}

    def get(self, patient_id: str, document_id: str) -> dict:
        doc = self._find(patient_id, document_id)
        # If the document has text but lacks analysis_verdict (e.g. existing record), compute and persist it
        if doc.get("extracted_text") and not (doc.get("extracted_data") or {}).get("analysis_verdict"):
            try:
                extracted_data = dict(doc.get("extracted_data") or {})
                analysis = clinical_analyzer.analyze_document_content(
                    doc.get("extracted_text") or "",
                    category=doc.get("category", "other"),
                    structured_data=extracted_data,
                )
                extracted_data["analysis_verdict"] = analysis
                if not extracted_data.get("referring_doctor") and analysis.get("doctor"):
                    extracted_data["referring_doctor"] = analysis["doctor"]
                if not extracted_data.get("referring_facility") and analysis.get("facility"):
                    extracted_data["referring_facility"] = analysis["facility"]
                if not extracted_data.get("specialty") and analysis.get("specialty"):
                    extracted_data["specialty"] = analysis["specialty"]

                doc["extracted_data"] = extracted_data
                self._docs.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"extracted_data": extracted_data, "updated_at": _utcnow()}},
                )
            except Exception as e:
                logger.warning("Auto-analysis failed for doc %s: %s", document_id, e)

        cid, name = self._resolve_patient_info(patient_id)
        return serialize_document(
            doc,
            include_text=True,
            patient_careverse_id=cid,
            patient_name=name,
        )

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
        """Load one document, scoped to its owner."""
        if not ObjectId.is_valid(document_id):
            raise errors.not_found("Document not found", code="DOCUMENT_NOT_FOUND")

        doc = self._docs.find_one(
            {"_id": ObjectId(document_id), "patient_id": patient_id}
        )
        if doc is None:
            raise errors.not_found("Document not found", code="DOCUMENT_NOT_FOUND")
        return doc


# ---------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _extract_text_and_structure(content: bytes, category: str = "other") -> ExtractionOutcome:
    """Text first, and only then structured facts."""
    outcome = extraction_service.extract_text(content)
    if outcome.get("extraction_status") != "completed":
        return outcome

    text = outcome.get("extracted_text") or ""
    extracted_data = structured_extraction.extract_structured(text)

    # Run clinical analysis to generate patient-friendly observations and verdict
    try:
        analysis = clinical_analyzer.analyze_document_content(
            text,
            category=category,
            structured_data=extracted_data,
        )
        extracted_data["analysis_verdict"] = analysis
        if not extracted_data.get("referring_doctor") and analysis.get("doctor"):
            extracted_data["referring_doctor"] = analysis["doctor"]
        if not extracted_data.get("referring_facility") and analysis.get("facility"):
            extracted_data["referring_facility"] = analysis["facility"]
        if not extracted_data.get("specialty") and analysis.get("specialty"):
            extracted_data["specialty"] = analysis["specialty"]
    except Exception as exc:
        logger.warning("Clinical analysis failed: %s", exc)

    outcome["extracted_data"] = extracted_data
    return outcome


def _safe_filename(name: str) -> str:
    """Reduce an upload name to a displayable basename."""
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
