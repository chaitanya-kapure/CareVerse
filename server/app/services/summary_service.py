"""Patient summary generation, behind a provider seam.

This is Phase 4B. It builds, validates and persists `patient_summaries`
documents; it does **not** call a model. The only provider that exists is
`MockSummaryProvider`, which assembles the `extracted_data` that Phase 4A
already produced. `settings.ai_provider` can name `openai` or `anthropic`,
and selecting either fails loudly rather than silently producing nothing --
a real provider is Phase 4C, and a fallback that pretends to be one is worse
than an error.

Design notes that matter
------------------------
**The provider receives an already-authorized `patient_id` and nothing else.**
It never sees a doctor id, a token, a request, or a patient object handed in
by the frontend. `SummaryService` loads the data itself, from ids it derived,
after the route dependency has proved the caller may read this patient.

**The payload is deliberately thin.** Three profile fields (`full_name`,
`date_of_birth`, `gender`) and per-document metadata plus `extracted_data`.
`phone`, `address` and the patient's free-text `notes` are not sent, because
nothing in a summary needs them and a real provider in Phase 4C would be
handing them to a third party. `storage_key`, `original_filename` and
`extraction_error` are not sent either: they are internal plumbing, and the
original file is reachable through the source links instead.

**Traceability is enforced here, not by the provider.** Every item carries a
`source_document_id`. Before anything is persisted, each id is checked against
the set of documents that actually belong to this patient; an item whose id is
missing, malformed, or points at somebody else's record is dropped. A summary
that cannot name where a claim came from is not persisted at all.

**The disclaimer is not the provider's to set.** `AI_SUMMARY_DISCLAIMER` is
written over whatever came back, so no provider -- present or future -- can
reword or drop it.

**The output shape is fixed.** The eight sections in `SUMMARY_SECTIONS` are
rendered in that order whether or not the provider returned them, and an empty
one still says "Not found in the uploaded records." A blank section would read
as "nothing abnormal here", which is a claim this system is not allowed to
make on a patient's behalf.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, Sequence

from fastapi import HTTPException, status
from pymongo.database import Database

from app.config import AI_SUMMARY_DISCLAIMER, settings
from app.models.collections import (
    get_medical_documents,
    get_patient_profiles,
    get_patient_summaries,
)
from app.models.medical_document import ExtractedData, format_category
from app.models.patient_summary import (
    PatientSummaryDocument,
    SummaryProvider as SummaryProviderName,
    SummarySection,
    serialize_summary,
)

logger = logging.getLogger(__name__)


# ======================================================================
# Fixed output contract
# ======================================================================

# The section list is fixed by docs/ARCHITECTURE.md section 9. It is emitted
# in exactly this order, every time, and every one of them is always present
# -- including the empty ones, which carry `EMPTY_SECTION_NOTE`.
SUMMARY_SECTIONS: tuple[tuple[str, str], ...] = (
    ("patient_overview", "Patient Overview"),
    ("medical_history", "Available Medical History"),
    ("key_findings", "Key Findings From Records"),
    ("lab_values", "Important Lab Values"),
    ("recent_records", "Recent Records"),
    ("medications", "Medications Mentioned In Records"),
    ("abnormal_values", "Abnormal Values / Findings Mentioned In Records"),
    ("chronological_overview", "Chronological Record Overview"),
)

# Silence would read as "nothing wrong". Every section says this instead.
EMPTY_SECTION_NOTE = "Not found in the uploaded records."

# Bounds. The provider is given a small, fixed amount of data and is not
# allowed to return an unbounded document; nothing here can grow with the
# number of pages a patient happens to have uploaded.
MAX_DOCUMENTS = 200
MAX_ITEMS_PER_SECTION = 200
MAX_ITEM_CHARS = 600
MAX_OVERVIEW_CHARS = 600
MAX_SOURCE_TEXT_CHARS = 300
# `recent_records` shows this many, newest first.
MAX_RECENT_DOCUMENTS = 10


class SummaryProviderUnavailable(HTTPException):
    """A provider was requested that this build does not contain.

    Raised for `AI_PROVIDER=openai` / `anthropic` in Phase 4B. It carries no
    configuration value in its message, because an exception text is not a
    place to put a credential.

    An `HTTPException`, like the 503 `get_db` raises, and not a bare
    `RuntimeError`. That distinction is the whole point of the class: a plain
    exception matches only the catch-all handler, so the client received
    `500 INTERNAL_ERROR` -- reporting a configuration mistake as a server
    crash, with a code that says retrying is worth trying. Subclassing
    FastAPI's exception means the registered handler serialises it with the
    `code` header intact, exactly as `DOCUMENT_NOT_FOUND` and
    `DATABASE_UNAVAILABLE` are delivered, while `except
    SummaryProviderUnavailable` still catches this one case and no other.

    503 rather than 500 because the server is healthy and the records are
    perfectly readable. What is missing is a summarizer, and it stays missing
    until somebody configures one this build implements -- so retrying the
    same request cannot help, which is the distinction `503` carries and
    `500` does not.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            headers={"code": "SUMMARY_PROVIDER_UNAVAILABLE"},
        )


# ======================================================================
# Provider input
# ======================================================================


@dataclass(frozen=True)
class SummaryProfile:
    """The three profile fields a summary may legitimately use.

    `phone`, `address` and `notes` are absent by construction, not by
    convention: this object cannot carry them, so a future edit cannot leak
    them into a provider call by forgetting a filter.
    """

    full_name: str = ""
    date_of_birth: Optional[str] = None
    gender: str = "unspecified"


@dataclass(frozen=True)
class SummaryDocument:
    """One readable record, as the provider sees it.

    No `storage_key`, no `original_filename`, no `extraction_error` and no
    `extracted_text`: the text is large, and the structured fields were
    derived from it, so sending both would invite a provider to quote around
    the extraction instead of using it.
    """

    id: str
    title: str
    category: str
    document_date: Optional[str]
    page_count: Optional[int]
    character_count: int
    extracted_data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SummaryPayload:
    """Everything a provider is given. Documents are oldest first."""

    patient_id: str
    profile: SummaryProfile
    documents: tuple[SummaryDocument, ...]
    unreadable_document_count: int


# ======================================================================
# Provider output
# ======================================================================


@dataclass(frozen=True)
class SummaryItem:
    """One attributed statement.

    `source_document_id` is mandatory by construction. A provider cannot
    construct a claim that does not say where it came from.
    """

    text: str
    source_document_id: str
    source_text: Optional[str] = None


@dataclass(frozen=True)
class ProviderSection:
    key: str
    title: str
    items: tuple[SummaryItem, ...]


@dataclass(frozen=True)
class SummaryDraft:
    """A provider's answer.

    Deliberately has no `disclaimer` field. There is nothing for a provider to
    fill in, so there is nothing it can overwrite.
    """

    overview: str
    sections: tuple[ProviderSection, ...]


class SummaryProvider(Protocol):
    """The seam Phase 4C plugs into.

    `generate` is synchronous and must be deterministic for a given payload.
    `SummaryService` already runs it off the event loop.
    """

    name: SummaryProviderName
    is_mock: bool
    model: Optional[str]

    def generate(self, payload: SummaryPayload) -> SummaryDraft: ...


# ======================================================================
# The deterministic provider
# ======================================================================

# Profile `gender` values are the patient's own choice; "unspecified" means
# they declined to give one, so it is never phrased as a clinical attribute.
_GENDER_WORDS = {
    "male": "male",
    "female": "female",
    "other": "gender recorded as other",
}

_UNDATED = "no date on the document"


class MockSummaryProvider:
    """Assembles the structured records into a summary. Adds no judgement.

    Every sentence it produces is either a document's own words or a
    mechanical restatement of a stored field. There is no vocabulary of
    medical meaning in this class -- no condition words, no severity, no
    advice -- so there is nothing here that could become a diagnosis. A value
    becomes the string ``"Glucose: 126 mg/dL"`` and nothing further; whether
    that means anything is not a question this class is allowed to have an
    answer to.
    """

    name: SummaryProviderName = "mock"
    is_mock = True
    model: Optional[str] = None

    def generate(self, payload: SummaryPayload) -> SummaryDraft:
        documents = payload.documents

        # `_build_*` walks the documents and returns that section's items.
        # `recent_records` and `chronological_overview` describe the same
        # documents in opposite orders, so they are assembled here instead.
        by_key: dict[str, tuple[SummaryItem, ...]] = {
            key: self._walk(key, documents) for key, _ in SUMMARY_SECTIONS
        }

        newest_first = list(reversed(documents))[:MAX_RECENT_DOCUMENTS]
        by_key["recent_records"] = tuple(
            _item(document, _record_line(document)) for document in newest_first
        )
        by_key["chronological_overview"] = tuple(
            _item(document, _record_line(document)) for document in documents
        )

        return SummaryDraft(
            overview=self._overview(payload),
            sections=tuple(
                ProviderSection(key=key, title=title, items=by_key[key])
                for key, title in SUMMARY_SECTIONS
            ),
        )

    # --- overview ----------------------------------------------------------

    def _overview(self, payload: SummaryPayload) -> str:
        """One framing sentence. Deterministic: nothing here reads a clock."""
        readable = len(payload.documents)
        unreadable = payload.unreadable_document_count

        who = payload.profile.full_name.strip() or "the patient"
        details = []
        if payload.profile.date_of_birth:
            details.append(f"date of birth {payload.profile.date_of_birth}")
        details.append(
            _GENDER_WORDS.get(payload.profile.gender, "gender not recorded")
        )

        if readable:
            counts = f"{readable} readable record{'' if readable == 1 else 's'}"
        else:
            counts = "no readable records"

        excluded = ""
        if unreadable:
            excluded = (
                f" {unreadable} uploaded document{'' if unreadable == 1 else 's'}"
                " could not be read and is not included here."
            )

        # Deliberately impersonal. One summary document is generated once and
        # served unchanged to both audiences, so this sentence cannot address
        # either of them -- "this patient has uploaded" reads as a report about
        # a third party to the patient whose own records these are, and "you
        # have uploaded" reads as though the doctor had done it. Naming the
        # record set instead is correct for both, and the reader who owns it can
        # tell from the name on the page whose it is.
        return (
            f"Assembled from {counts} in this record set. "
            f"About {who} ({', '.join(details)}).{excluded} "
            "Every item below is copied from a record and links to the document "
            "it came from. Nothing here is a diagnosis or an interpretation."
        )[:MAX_OVERVIEW_CHARS]

    # --- section builders --------------------------------------------------

    def _walk(
        self, key: str, documents: Sequence[SummaryDocument]
    ) -> tuple[SummaryItem, ...]:
        builder = getattr(self, f"_build_{key}")
        items: list[SummaryItem] = []
        for document in documents:
            items.extend(builder(document))
        return tuple(items[:MAX_ITEMS_PER_SECTION])

    def _build_patient_overview(
        self, document: SummaryDocument
    ) -> list[SummaryItem]:
        """Who wrote the record, and what the record says it is.

        Identity-level facts from `extracted_data`. Profile details live in
        the overview sentence instead: they come from the patient rather than
        from a document, and putting them here would mean an item with no
        source to point at.
        """
        items: list[SummaryItem] = []
        data = document.extracted_data

        title = _clean(data.get("report_title"))
        if title:
            items.append(_item(document, f"Report title on the document: {title}."))

        facility = _clean(data.get("referring_facility"))
        if facility:
            items.append(_item(document, f"Referring facility: {facility}."))

        doctor = _clean(data.get("referring_doctor"))
        if doctor:
            items.append(_item(document, f"Referring doctor: {doctor}."))

        detected = _clean(data.get("document_date"))
        if detected:
            items.append(
                _item(
                    document,
                    f"Date printed on the document: {detected} "
                    f"(the record is filed as {document.document_date or _UNDATED}).",
                )
            )
        return items

    def _build_medical_history(
        self, document: SummaryDocument
    ) -> list[SummaryItem]:
        """Conditions the document itself states.

        `stated_conditions` only ever contains an explicit statement phrase
        (Phase 4A), stored under `text`. There is no path here from a lab
        value to a condition.
        """
        return [
            _item(
                document,
                f"The document states: \u201c{_clean(entry.get('text'))}\u201d",
                source_text=entry.get("source_text"),
            )
            for entry in _entries(document, "stated_conditions")
            if _clean(entry.get("text"))
        ]

    def _build_key_findings(self, document: SummaryDocument) -> list[SummaryItem]:
        """Verbatim sentences the document itself marked as abnormal."""
        return [
            _item(
                document,
                f"The document states: \u201c{_clean(entry.get('text'))}\u201d",
                source_text=entry.get("source_text"),
            )
            for entry in _entries(document, "abnormal_findings")
            if _clean(entry.get("text"))
        ]

    def _build_lab_values(self, document: SummaryDocument) -> list[SummaryItem]:
        return [
            _item(document, _lab_line(entry), source_text=entry.get("source_text"))
            for entry in _entries(document, "lab_values")
            if _clean(entry.get("name")) and _clean(entry.get("value"))
        ]

    def _build_abnormal_values(self, document: SummaryDocument) -> list[SummaryItem]:
        """Lab values the page itself marked.

        Only rows carrying a `flag`, and only because Phase 4A transcribed a
        marker that was printed on the page -- never because the number was
        compared against the printed range. The wording says whose judgement
        the marker is.
        """
        items: list[SummaryItem] = []
        for entry in _entries(document, "lab_values"):
            flag = _clean(entry.get("flag"))
            if not flag or not _clean(entry.get("name")) or not _clean(entry.get("value")):
                continue
            items.append(
                _item(
                    document,
                    f"{_lab_line(entry)} The document marks this value: {flag}.",
                    source_text=entry.get("source_text"),
                )
            )
        return items

    def _build_medications(self, document: SummaryDocument) -> list[SummaryItem]:
        """Medications the record mentions.

        Reported as written. No dose is adjusted, no interaction is checked,
        and nothing here says the medication should or should not be taken.
        """
        items: list[SummaryItem] = []
        for entry in _entries(document, "medications"):
            name = _clean(entry.get("name"))
            if not name:
                continue
            parts = [name]
            for optional in ("dosage", "frequency"):
                value = _clean(entry.get(optional))
                if value:
                    parts.append(value)
            items.append(
                _item(
                    document,
                    "Medication mentioned in the record: " + " ".join(parts) + ".",
                    source_text=entry.get("source_text"),
                )
            )
        return items

    def _build_recent_records(self, document: SummaryDocument) -> list[SummaryItem]:
        return []  # assembled in `generate`, newest first

    def _build_chronological_overview(
        self, document: SummaryDocument
    ) -> list[SummaryItem]:
        return []  # assembled in `generate`, oldest first


# ======================================================================
# Provider selection -- the single switch point
# ======================================================================

MOCK_PROVIDER = MockSummaryProvider()

_IMPLEMENTED_PROVIDERS: dict[str, SummaryProvider] = {"mock": MOCK_PROVIDER}

_override: Optional[SummaryProvider] = None


def get_summary_provider() -> SummaryProvider:
    """Resolve the configured provider.

    Phase 4B implements `mock` only. `openai` and `anthropic` are accepted by
    `settings` so the environment variable already has the right shape, but
    asking for one raises: a Phase 4C provider that silently did nothing would
    leave a summary labelled as a real model's output when it was not.
    """
    if _override is not None:
        return _override

    configured = (settings.ai_provider or "mock").strip().lower()
    provider = _IMPLEMENTED_PROVIDERS.get(configured)
    if provider is None:
        # The rejected value is deliberately not echoed. This message is now
        # rendered to the client, and `AI_PROVIDER` is a free-text variable
        # that someone can paste anything into -- including a key pasted into
        # the wrong name, which this response would then hand back. Naming the
        # providers that *do* work is both safer and more useful than
        # repeating back what was asked for. The offending value stays in the
        # server log, where it belongs.
        logger.error(
            "AI_PROVIDER is set to an unimplemented value; refusing to guess. "
            "Implemented providers: %s",
            ", ".join(sorted(_IMPLEMENTED_PROVIDERS)),
        )
        raise SummaryProviderUnavailable(
            "No summary provider is configured for this build. Implemented "
            f"providers: {', '.join(sorted(_IMPLEMENTED_PROVIDERS))}. Set "
            "AI_PROVIDER to one of those to generate a summary."
        )
    return provider


def set_summary_provider(provider: Optional[SummaryProvider]) -> None:
    """Install a provider for this process. Tests use it; nothing else does."""
    global _override
    _override = provider


def reset_summary_provider() -> None:
    set_summary_provider(None)


# ======================================================================
# Formatting helpers
# ======================================================================


def _clean(value: Any) -> str:
    """Collapse whitespace and bound nothing. Never raises."""
    if value is None:
        return ""
    try:
        return " ".join(str(value).split())
    except Exception:  # pragma: no cover - defensive
        return ""


def _entries(document: SummaryDocument, key: str) -> list[dict]:
    """Read one list out of `extracted_data`, defensively.

    Phase 4A guarantees the shape, but a provider should not be the thing
    that turns a malformed stored field into a 500 on a doctor's screen.
    """
    raw = document.extracted_data.get(key)
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def _item(
    document: SummaryDocument,
    text: str,
    source_text: Any = None,
) -> SummaryItem:
    """Build one attributed item, bounded."""
    verbatim = _clean(source_text)[:MAX_SOURCE_TEXT_CHARS]
    return SummaryItem(
        text=_clean(text)[:MAX_ITEM_CHARS],
        source_document_id=document.id,
        source_text=verbatim or None,
    )


def _record_line(document: SummaryDocument) -> str:
    """One line describing a document. Purely stored metadata."""
    return (
        f"\u201c{_clean(document.title) or 'Untitled document'}\u201d "
        f"(category: {format_category(_clean(document.category))}, "
        f"date: {document.document_date or _UNDATED})"
    )


def _lab_line(entry: Mapping[str, Any]) -> str:
    """Render a lab row as the document printed it.

    The unit and the reference range appear only when the document carried
    them. Nothing is rounded, converted, or compared.
    """
    name = _clean(entry.get("name"))
    value = _clean(entry.get("value"))
    unit = _clean(entry.get("unit"))
    reference = _clean(entry.get("reference_range"))

    line = f"{name}: {' '.join(part for part in (value, unit) if part)}"
    if reference:
        line += f" (reference range printed on the document: {reference})"
    return line


# ======================================================================
# The service
# ======================================================================

# Only these document fields are read. `extracted_text`, `storage_key`,
# `original_filename`, `extraction_error`, `mime_type` and `size_bytes` stay
# in MongoDB -- they are either large, internal, or both, and a summary needs
# none of them.
_DOCUMENT_PROJECTION = {
    "_id": 1,
    "title": 1,
    "category": 1,
    "document_date": 1,
    "page_count": 1,
    "character_count": 1,
    "extracted_data": 1,
    "extraction_status": 1,
    "uploaded_at": 1,
}

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class _RecordSet:
    """The readable documents for one patient, plus what was excluded.

    Loaded in a single scoped query so the staleness check, the provider
    payload and the persisted counts all come from one consistent read.
    """

    documents: tuple[SummaryDocument, ...]
    unreadable_count: int
    newest_uploaded_at: Optional[datetime]


class SummaryService:
    """Build, validate and persist one summary per patient.

    Only ever called *after* the route dependency has authorized the caller
    for `patient_id`. Every method takes that already-authorized id as an
    argument rather than re-deriving it, so no caller can pass an id that has
    not been checked.
    """

    def __init__(self, db: Database, provider: Optional[SummaryProvider] = None) -> None:
        self._db = db
        self._documents = get_medical_documents(db)
        self._profiles = get_patient_profiles(db)
        self._summaries = get_patient_summaries(db)
        self._provider = provider

    # ==================================================================
    # public API
    # ==================================================================

    def get_summary(self, patient_id: str, force: bool = False) -> dict:
        """Return the current summary, generating it if missing or stale.

        `force=True` is the explicit-regenerate path. `force=False` is the
        GET path: regenerate only when the readable record set has changed
        since the persisted summary was written, so opening the screen twice
        does not rewrite the document twice.
        """
        records = self._load_records(patient_id)
        persisted = self._summaries.find_one({"patient_id": patient_id})

        if persisted is not None and not force and not self._is_stale(persisted, records):
            return serialize_summary(persisted)

        payload = SummaryPayload(
            patient_id=patient_id,
            profile=self._load_profile(patient_id),
            documents=records.documents,
            unreadable_document_count=records.unreadable_count,
        )
        provider, draft = self._generate(payload)
        summary = self._to_document(
            patient_id=patient_id,
            provider=provider,
            draft=draft,
            source_ids=[document.id for document in records.documents],
            unreadable_count=records.unreadable_count,
        )
        self._summaries.update_one(
            {"patient_id": patient_id}, {"$set": summary}, upsert=True
        )
        return serialize_summary(self._summaries.find_one({"patient_id": patient_id}) or summary)

    # ==================================================================
    # inputs
    # ==================================================================

    def _load_records(self, patient_id: str) -> _RecordSet:
        """One scoped query. Completed documents only, oldest first.

        `needs_ocr` and `failed` documents contribute nothing but a count:
        their text is either absent or wrong, and Phase 4A deliberately left
        `extracted_data` empty for them. Counting them is how the UI can say
        "3 of 5 records are in this summary" instead of quietly dropping two.
        """
        readable: list[dict] = []
        unreadable = 0
        for raw in self._documents.find(
            {"patient_id": patient_id}, _DOCUMENT_PROJECTION
        ):
            if raw.get("extraction_status") != "completed":
                unreadable += 1
                continue
            readable.append(raw)

        readable.sort(key=_sort_key)

        # Oldest first, so the cap keeps the patient's history rather than
        # whichever rows MongoDB happened to return last.
        over_cap = max(0, len(readable) - MAX_DOCUMENTS)
        readable = readable[:MAX_DOCUMENTS]

        documents: list[SummaryDocument] = []
        newest: Optional[datetime] = None
        for raw in readable:
            documents.append(
                SummaryDocument(
                    id=str(raw["_id"]),
                    title=_clean(raw.get("title")),
                    category=_clean(raw.get("category")) or "other",
                    document_date=_clean(raw.get("document_date")) or None,
                    page_count=raw.get("page_count"),
                    character_count=int(raw.get("character_count") or 0),
                    extracted_data=_safe_extracted_data(raw.get("extracted_data")),
                )
            )
            uploaded = _as_utc(raw.get("uploaded_at"))
            if uploaded is not None and (newest is None or uploaded > newest):
                newest = uploaded

        return _RecordSet(
            documents=tuple(documents),
            # Anything dropped for exceeding the cap is counted as unreadable
            # too, so the UI can never imply the summary read more than it did.
            unreadable_count=unreadable + over_cap,
            newest_uploaded_at=newest,
        )

    def _load_profile(self, patient_id: str) -> SummaryProfile:
        raw = self._profiles.find_one({"patient_id": patient_id}) or {}
        return SummaryProfile(
            full_name=_clean(raw.get("full_name")),
            date_of_birth=_clean(raw.get("date_of_birth")) or None,
            gender=_clean(raw.get("gender")) or "unspecified",
        )

    # ==================================================================
    # staleness
    # ==================================================================

    @staticmethod
    def _is_stale(persisted: PatientSummaryDocument, records: _RecordSet) -> bool:
        """True when the persisted summary no longer describes these records.

        Three comparisons, no cache layer and no new stored field:

          * the set of readable document ids changed -- something was
            uploaded or deleted since this was written;
          * the unreadable count changed -- a record that could not be read
            has since been read, or one that could has gone;
          * a readable document is newer than the summary -- a Phase 2
            document is immutable after upload, so a later `uploaded_at`
            means a different set, not a re-saved one.

        Being wrong in one direction costs one cheap deterministic pass.
        Being wrong in the other costs a doctor reading a summary that has
        silently fallen behind the record list beside it.
        """
        stored_ids = {str(value) for value in persisted.get("source_document_ids", [])}
        if stored_ids != {document.id for document in records.documents}:
            return True

        if int(persisted.get("unreadable_document_count", 0) or 0) != records.unreadable_count:
            return True

        generated_at = _as_utc(persisted.get("generated_at"))
        if generated_at is None:
            return True

        newest = records.newest_uploaded_at
        return newest is not None and newest > generated_at

    # ==================================================================
    # generation
    # ==================================================================

    def _generate(
        self, payload: SummaryPayload
    ) -> tuple[SummaryProvider, SummaryDraft]:
        """Call the provider, falling back to the deterministic one.

        A provider that raises or times out must not reach the client as a raw
        exception, and the fallback must not invent clinical facts. The
        deterministic provider satisfies both: it reads only what Phase 4A
        already extracted, and it is stored with `is_mock` set so the UI can
        label it.

        The log line records that a fallback happened and nothing else -- no
        document id, no title, no extracted value.
        """
        provider = self._provider or get_summary_provider()
        try:
            return provider, provider.generate(payload)
        except Exception:
            logger.warning(
                "summary provider %s failed; using the deterministic summary instead",
                getattr(provider, "name", "unknown"),
            )
            return MOCK_PROVIDER, MOCK_PROVIDER.generate(payload)

    def _to_document(
        self,
        patient_id: str,
        provider: SummaryProvider,
        draft: SummaryDraft,
        source_ids: Sequence[str],
        unreadable_count: int,
    ) -> dict:
        """Validate provider output and assemble the stored document.

        Everything that can reject a claim happens here, before anything is
        written: unknown sections are dropped, the fixed section order is
        re-imposed, and every item is checked against the ids that really do
        belong to this patient.
        """
        known_keys = {key for key, _ in SUMMARY_SECTIONS}
        allowed = set(source_ids)
        by_key: dict[str, list[dict]] = {}
        dropped = 0

        for section in draft.sections:
            if section.key not in known_keys:
                dropped += 1
                continue
            bucket = by_key.setdefault(section.key, [])
            for item in section.items:
                if item.source_document_id not in allowed:
                    dropped += 1
                    continue
                text = _clean(item.text)[:MAX_ITEM_CHARS]
                if not text:
                    dropped += 1
                    continue
                verbatim = _clean(item.source_text)[:MAX_SOURCE_TEXT_CHARS]
                bucket.append(
                    {
                        "text": text,
                        "source_document_id": item.source_document_id,
                        "source_text": verbatim or None,
                    }
                )

        if dropped:
            # Counted, never logged with content: a rejected item is still a
            # medical claim, and claims do not belong in the server log.
            logger.warning(
                "dropped %d untraceable summary item(s) for patient %s",
                dropped,
                patient_id,
            )

        sections: list[SummarySection] = [
            {
                "key": key,
                "title": title,
                "items": by_key.get(key, [])[:MAX_ITEMS_PER_SECTION],
                "empty_note": None if by_key.get(key) else EMPTY_SECTION_NOTE,
            }
            for key, title in SUMMARY_SECTIONS
        ]

        return {
            "patient_id": patient_id,
            "provider": provider.name,
            # Stored, never inferred from the output text: a provider that is
            # genuinely not a mock sets this itself, and the UI reads it.
            "is_mock": bool(provider.is_mock),
            "model": provider.model,
            # Written here and never read from `draft`: the provider has no
            # disclaimer field to fill in, so it has nothing to overwrite.
            "disclaimer": AI_SUMMARY_DISCLAIMER,
            "overview": _clean(draft.overview)[:MAX_OVERVIEW_CHARS],
            "sections": sections,
            "source_document_ids": list(source_ids),
            "source_document_count": len(source_ids),
            "unreadable_document_count": unreadable_count,
            "generated_at": datetime.now(timezone.utc),
        }


# ======================================================================
# Small helpers
# ======================================================================


def _sort_key(raw: dict) -> tuple:
    """Oldest first, by the date on the document, then by upload time.

    Undated documents sort last rather than first, so a record with a printed
    date is never pushed off the front of a chronological list by a file whose
    date nobody could read.
    """
    date = _clean(raw.get("document_date"))
    return (
        0 if date else 1,
        date or "",
        _as_utc(raw.get("uploaded_at")) or _EPOCH,
        str(raw.get("_id")),
    )


def _as_utc(value: Any) -> Optional[datetime]:
    """Naive datetimes are UTC here; `mongomock`/drivers differ on tzinfo."""
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _safe_extracted_data(raw: Any) -> ExtractedData:
    if not isinstance(raw, dict):
        return {}
    return dict(raw)  # type: ignore[return-value]
