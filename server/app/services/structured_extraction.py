"""Deterministic structured extraction of explicitly stated medical facts."""

import logging
import re
from datetime import date as _date
from typing import Any, Callable, Iterable, Optional

from app.models.medical_document import ExtractedData

logger = logging.getLogger(__name__)


# ======================================================================
# bounds
# ======================================================================
# Every one of these exists so that a hostile or merely enormous document

# Mirrors extraction_service.MAX_EXTRACTED_CHARS. The text extractor already
MAX_INPUT_CHARS = 500_000

# A 500,000-character document is ~20,000 lines. Past this the remainder is
# not read at all.
MAX_LINES = 20_000

# Per-category output caps.
MAX_LAB_VALUES = 200
MAX_MEDICATIONS = 200
MAX_ABNORMAL_FINDINGS = 200
MAX_STATED_CONDITIONS = 200

# Field length caps. A "lab value" whose name is 200 characters is a sentence
# that slipped through, not a test name.
MAX_NAME_CHARS = 60
MAX_NAME_WORDS = 6
MAX_UNIT_CHARS = 12
MAX_VALUE_CHARS = 40
MAX_CONDITION_CHARS = 120
MAX_METADATA_CHARS = 120
MAX_TITLE_CHARS = 200

# `source_text` must stay verbatim, so an over-long line is *skipped* rather
MAX_SOURCE_TEXT_CHARS = 300

# How far into the document to look for a labelled header. Metadata lives at
MAX_METADATA_LINES = 60

# Abbreviations that introduce an administration frequency. Only recognised
# when the abbreviation stands alone as a whole word.
FREQUENCY_ABBREVIATIONS = (
    "Q4H", "Q6H", "Q8H", "Q12H", "QAM", "QPM", "QOD", "QDS",
    "OD", "BD", "TDS", "QID", "BID", "TID", "SOS", "PRN", "STAT", "HS",
)


# ======================================================================
# public entry point
# ======================================================================


def extract_structured(text: str) -> ExtractedData:
    """Pull explicitly stated facts out of extracted document text."""
    if not isinstance(text, str) or not text.strip():
        return {}

    # Bounded before anything else touches the string.
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]

    # Guarded like every other pass, even though it is the one that touches
    lines = _guard(_readable_lines, text, default=[])
    if not lines:
        return {}

    result: ExtractedData = {}

    # Medications first: a prescription line ("Metformin 500 mg twice daily")
    medications, medication_lines = _guard(
        _extract_medications, lines, default=([], set())
    )
    _put(result, "medications", medications)

    lab_values = _guard(_extract_lab_values, lines, medication_lines, default=[])
    _put(result, "lab_values", lab_values)

    abnormal_findings = _guard(_extract_abnormal_findings, lines, default=[])
    _put(result, "abnormal_findings", abnormal_findings)

    stated_conditions = _guard(_extract_stated_conditions, lines, default=[])
    _put(result, "stated_conditions", stated_conditions)

    for key, finder in (
        ("report_title", _extract_report_title),
        ("document_date", _extract_document_date),
        ("referring_facility", _extract_facility),
        ("referring_doctor", _extract_referring_doctor),
    ):
        value = _guard(finder, lines, default=None)
        if value:
            result[key] = value  # type: ignore[literal-required]

    return result


# ======================================================================
# shared helpers
# ======================================================================


def _guard(fn: Callable, *args, default: Any = None) -> Any:
    """Run one extraction pass, degrading to `default` if it raises."""
    try:
        return fn(*args)
    except Exception as exc:
        # Type only. The message of a parsing failure routinely embeds the very
        # line that failed to parse, which is document content.
        logger.warning(
            "structured extraction pass '%s' failed: %s", fn.__name__, type(exc).__name__
        )
        return default


def _readable_lines(text: str) -> list[str]:
    """Split into non-empty, whitespace-trimmed lines, up to `MAX_LINES`."""
    lines: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if line:
            lines.append(line)
            if len(lines) >= MAX_LINES:
                break
    return lines


def _put(result: ExtractedData, key: str, values: Optional[list]) -> None:
    """Write a list field only when it actually found something."""
    if values:
        result[key] = values  # type: ignore[literal-required]


def _quotable(line: str) -> bool:
    """True when a line is short enough to quote verbatim in `source_text`."""
    return 0 < len(line) <= MAX_SOURCE_TEXT_CHARS


def _dedupe(items: list[dict], keys: tuple[str, ...], limit: int) -> list[dict]:
    """First occurrence wins, in document order, capped at `limit`."""
    seen: set[tuple] = set()
    unique: list[dict] = []
    for item in items:
        marker = tuple(str(item.get(key) or "").lower() for key in keys)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


# ======================================================================
# metadata: report title, date, facility, referring doctor
# ======================================================================
# All four require an explicit printed label. There is no heading heuristic

_LABELL_VALUE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z0-9 /\-]{0,40}?)\s*[:\-]\s*(?P<value>\S.*)$"
)

# Values that are placeholders rather than answers.
_EMPTY_LABEL_VALUES = {
    "", "-", "--", "n/a", "na", "none", "nil", "not applicable",
    "not available", "unknown", "not specified", "tbd", "xxxx",
}

REPORT_TITLE_LABELS = {
    "report", "report title", "title", "test", "test name", "tests",
    "investigation", "investigation name", "examination", "study",
    "procedure", "specimen", "document", "description",
}

FACILITY_LABELS = {
    "hospital", "hospital name", "clinic", "cliniq", "clinic name", "laboratory",
    "lab", "centre", "center", "facility", "facility name", "institution",
    "department", "issued by", "performed at", "organisation", "organization",
}

# `reported by` is deliberately absent from FACILITY_LABELS. The phrase is
# ambiguous between a person and a place, and resolving it would be a guess.
REFERRING_DOCTOR_LABELS = {
    "doctor", "doctor name", "dr", "physician", "referring doctor",
    "referring physician", "referred by", "reported by", "performed by",
    "consultant", "ref doctor", "registered medical practitioner", "rmp",
    "practitioner", "signed by", "authorised by", "authorized by",
}


def _labelled_value(
    lines: list[str], labels: set[str], max_chars: int
) -> Optional[str]:
    """The first `labels:`-style value near the top of the document."""
    for line in lines[:MAX_METADATA_LINES]:
        if not _quotable(line):
            continue
        match = _LABELL_VALUE.match(line)
        if not match:
            continue
        if match.group("label").strip().lower() not in labels:
            continue
        value = match.group("value").strip().rstrip(".").strip()
        if value.lower() in _EMPTY_LABEL_VALUES:
            continue
        # A placeholder like "…" or a run of dots is not an answer.
        if not re.search(r"[A-Za-z0-9]", value):
            continue
        return value[:max_chars]
    return None


def _extract_report_title(lines: list[str]) -> Optional[str]:
    return _labelled_value(lines, REPORT_TITLE_LABELS, MAX_TITLE_CHARS)


def _extract_facility(lines: list[str]) -> Optional[str]:
    return _labelled_value(lines, FACILITY_LABELS, MAX_METADATA_CHARS)


def _extract_referring_doctor(lines: list[str]) -> Optional[str]:
    return _labelled_value(lines, REFERRING_DOCTOR_LABELS, MAX_METADATA_CHARS)


# An address is never promoted to a facility, and a name is never promoted to


# ======================================================================
# document date
# ======================================================================

_ISO_DATE = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")
_SLASH_DATE = re.compile(r"\b(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})\b")

_DATE_LABEL = re.compile(
    r"\b(?:report\s*date|date\s+of\s+report|reported\s+on|date|dated|collected(?:\s+on)?|"
    r"sample\s+collected(?:\s+on)?|collection\s+date|issued(?:\s+on)?|test\s+date|"
    r"investigation\s+date|performed\s+on|order\s*date|bill\s*date|printed(?:\s+on)?)\b",
    re.IGNORECASE,
)

# A date of birth is not a document date, and it is printed on more documents
# than not. Any line mentioning birth is skipped outright.
_BIRTH_CONTEXT = re.compile(
    r"\b(?:date\s+of\s+birth|d\.?\s?o\.?\s?b\.?|birth\s*date|born|birth)\b",
    re.IGNORECASE,
)


def _extract_document_date(lines: list[str]) -> Optional[str]:
    """The first date the document labels as its own."""
    for line in lines[:MAX_METADATA_LINES]:
        if not _quotable(line):
            continue
        if _BIRTH_CONTEXT.search(line):
            continue

        # A line that is nothing but a date is a report-date heading.
        candidates: list[str] = []
        if _line_is_only_a_date(line):
            candidates.append(line)

        for candidate in _find_dates(line):
            preceding = line[: candidate.start()]
            if _DATE_LABEL.search(preceding):
                candidates.append(candidate.group(0))

        for raw in candidates:
            iso = _parse_iso_date(raw)
            if iso:
                return iso
    return None


def _line_is_only_a_date(line: str) -> bool:
    """True when a line consists of a date and nothing else."""
    for pattern in (_ISO_DATE, _SLASH_DATE):
        if pattern.fullmatch(line):
            return True
    return False


def _find_dates(line: str) -> list[re.Match]:
    found = list(_ISO_DATE.finditer(line))
    for match in _SLASH_DATE.finditer(line):
        # Ambiguous unless the leading component cannot be a month.
        if int(match.group("day")) > 12:
            found.append(match)
    return sorted(found, key=lambda m: m.start())


def _parse_iso_date(raw: str) -> Optional[str]:
    """Turn a date the document printed into `YYYY-MM-DD`, or refuse it."""
    iso = _ISO_DATE.search(raw)
    if iso:
        year, month, day = int(iso.group("year")), int(iso.group("month")), int(iso.group("day"))
    else:
        slash = _SLASH_DATE.search(raw)
        if not slash:
            return None
        first = int(slash.group("day"))
        if first <= 12:
            # Could be a day or a month. Refusing is the only honest answer.
            return None
        year = int(slash.group("year"))
        month = int(slash.group("month"))
        day = first

    try:
        return _date(year, month, day).isoformat()
    except ValueError:
        # Not a real calendar date. Refused rather than rolled over.
        return None


# ======================================================================
# laboratory values
# ======================================================================

# name, separator, value, optional unit. The name is non-greedy and the
_LAB_LINE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 ()'/%+.\-]{0,59}?)[:\s]+"
    r"(?P<value>[<>≤≥]?\s*-?\d+(?:\.\d+)?)\s*"
    r"(?P<unit>\S{1,12})?\s*$"
)

_UNIT_SHAPE = re.compile(
    r"^(?:%|[A-Za-zµμ][A-Za-z0-9%./µμ*\-^_]{0,11}"
    r"|/[A-Za-z][A-Za-z0-9/]{0,5}"
    r"|\d+\*?\d*/[A-Za-z][A-Za-z0-9]{0,5})$"
)

_TRAILING_RANGE = re.compile(
    r"\s*[\(\[]\s*(?P<range>[<>≤≥]?\s*-?\d[\d.,]*"
    r"(?:\s*(?:-|–|—|to)\s*[<>≤≥]?\s*-?\d[\d.,]*)?)\s*[\)\]]\s*$",
    re.IGNORECASE,
)

_TRAILING_RANGE_LABELLED = re.compile(
    r"\s*(?:ref(?:erence)?(?:\s+range)?|normal(?:\s+range)?|therapeutic(?:\s+range)?)"
    r"\s*[:=]?\s*(?P<low>-?\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?P<high>-?\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)

_TRAILING_MARKER = re.compile(
    r"(?:\s+|\s*[\(\[]\s*)(?P<marker>[A-Za-z]{1,11}|\*{1,3})[\)\]]?\s*$"
)

# Qualitative results a lab report prints in words. A closed list: an open one
# would start matching prose.
_QUALITATIVE_RESULTS = {
    "negative", "positive", "not detected", "detected", "non-reactive",
    "reactive", "normal", "abnormal", "equivocal", "indeterminate",
    "not seen", "seen", "clear", "inconclusive",
}

# Marker -> normalised `flag`. Every entry is a word the document itself can
# print. There is no entry that this module could compute.
_MARKER_FLAGS = {
    "h": "high",
    "hh": "high",
    "l": "low",
    "ll": "low",
    "*": "abnormal",
    "**": "abnormal",
    "high": "high",
    "low": "low",
    "elevated": "high",
    "raised": "high",
    "increased": "high",
    "decreased": "low",
    "reduced": "low",
    "abnormal": "abnormal",
    "critical": "critical",
    "panic": "critical",
    "positive": "positive",
    "negative": "negative",
    "normal": "normal",
}

# Names that are demographics or paperwork, not tests.
_NON_LAB_PATTERNS = re.compile(
    r"(?:https?://|www\.|\.(?:com|org|net|in|co|io|gov|info|edu)\b"
    r"|\b(?:call|phone|tel|mobile|cell|fax|contact|helpline|whatsapp|appointment|appointments|timing|schedule)\b"
    r"|\b(?:dr\.?|doctor|hospital|clinic|cliniq|centre|center|nursing\s*home|consultant|physician|surgeon|pathologist|radiologist|specialist)\b"
    r"|\b(?:invoice|bill|receipt|barcode|token|mrn|uhid|reg(?:istration)?(?:\s*no)?|opd|ipd|gstin|pan|prescription|advice)\b"
    r"|\b(?:address|street|road|floor|building|block|city|district|pin\s*code|pincode|lane|nagar)\b)",
    re.IGNORECASE,
)

_UNITLESS_ACCEPTED_TESTS = {
    "ph", "urine ph", "inr", "international normalized ratio",
    "a/g ratio", "ag ratio", "albumin/globulin ratio",
    "bun/creatinine ratio", "bun/cr ratio", "specific gravity",
    "sp gravity", "anion gap", "bmi", "spo2",
}

_LAB_NAME_STOPWORDS = {
    "age", "sex", "gender", "dob", "d o b", "date", "born", "birth",
    "page", "page no", "pages", "phone", "tel", "telephone", "id",
    "identification", "no", "s/n", "ref", "ref no", "mr no", "mrn",
    "hospital no", "unit no", "bed", "ward", "doctor", "dr", "name",
    "patient", "patient name", "address", "email", "fax", "time",
    "total pages", "report", "result", "results", "test", "tests",
    "call", "appointment", "appointments", "clinic", "cliniq", "hospital",
    "consultant", "physician", "surgeon", "barcode", "token", "bill",
    "invoice", "receipt", "pin", "pincode", "road", "street", "nagar",
    "floor", "reg", "registration", "gstin", "website", "web", "online",
    "helpline", "whatsapp", "timing", "schedule",
}

# A name containing a copula or a perception verb is a sentence, not a label.
_LAB_NAME_VERBISH = re.compile(
    r"\b(?:is|are|was|were|be|been|has|have|had|shows?|showed|show|"
    r"reveals?|revealed|found|reports?|reported|noted|seen|measured)\b",
    re.IGNORECASE,
)

# Demographics that appear on more laboratory reports than they should, and
_LAB_NAME_FORBIDDEN = re.compile(
    r"\b(?:date\s+of\s+birth|birth\s*date|d\.?\s?o\.?\s?b\.?|born|age\s+of)\b",
    re.IGNORECASE,
)


def _extract_lab_values(
    lines: list[str], medication_lines: set[int]
) -> list[dict]:
    found: list[dict] = []
    for index, line in enumerate(lines):
        if index in medication_lines:
            # "Metformin 500 mg twice daily" is a prescription, not a
            continue
        if not _quotable(line):
            continue
        entry = _parse_lab_line(line)
        if entry:
            found.append(entry)

    return _dedupe(found, ("name", "value", "unit"), MAX_LAB_VALUES)


def _parse_lab_line(line: str) -> Optional[dict]:
    """One laboratory row, or `None` if this line is not one."""
    for text, flag in _lab_candidates(line):
        trimmed, reference_range = _pop_trailing_range(text)
        entry = _interpret_lab_text(trimmed, line, reference_range, flag)
        if entry:
            return entry
    return None


def _lab_candidates(line: str) -> list[tuple[str, Optional[str]]]:
    """`(text, flag)` readings to try for one line, most specific first."""
    candidates: list[tuple[str, Optional[str]]] = []

    marker_match = _TRAILING_MARKER.search(line)
    if marker_match:
        token = marker_match.group("marker")
        flag = _MARKER_FLAGS.get(token.lower())
        stripped = line[: marker_match.start()].strip()
        if flag and stripped and not _token_is_unit(line, token):
            candidates.append((stripped, flag))

    # The whole line, unflagged. Always last, and always present: a token that
    candidates.append((line, None))
    return candidates


def _token_is_unit(line: str, token: str) -> bool:
    """True when the trailing token is better read as the line's unit."""
    match = _LAB_LINE.match(line)
    if not match:
        return False
    unit = (match.group("unit") or "").strip()
    if unit.upper() != token.upper():
        return False
    return len(token) <= 2


def _pop_trailing_range(text: str) -> tuple[str, Optional[str]]:
    """Remove a printed reference range from the end of a lab row."""
    bracketed = _TRAILING_RANGE.search(text)
    if bracketed:
        return (
            text[: bracketed.start()].strip(),
            _normalise_range(bracketed.group("range")),
        )

    labelled = _TRAILING_RANGE_LABELLED.search(text)
    if labelled:
        return (
            text[: labelled.start()].strip(),
            _normalise_range(f"{labelled.group('low')}-{labelled.group('high')}"),
        )

    return text, None


def _interpret_lab_text(
    text: str, source_text: str, reference_range: Optional[str], flag: Optional[str]
) -> Optional[dict]:
    """Read one already-trimmed fragment as a laboratory row."""
    match = _LAB_LINE.match(text)
    if match:
        name = (match.group("name") or "").strip()
        value = (match.group("value") or "").strip()
        unit = (match.group("unit") or "").strip()

        if unit and not _UNIT_SHAPE.match(unit):
            return None
        if not _usable_lab_value(value, unit or None, name, reference_range, flag):
            return None
        if not _usable_lab_name(name):
            return None

        return _lab_entry(
            name=name,
            value=value,
            unit=unit or None,
            reference_range=reference_range,
            flag=flag,
            source_text=source_text,
        )

    qualitative = _parse_qualitative_line(text)
    if qualitative:
        name, value = qualitative
        if not _usable_lab_name(name):
            return None
        # When the trailing word was the result itself ("CRP: Negative") it
        # is recorded as the value, not also as a flag saying the same thing.
        return _lab_entry(
            name=name,
            value=value,
            unit=None,
            reference_range=reference_range,
            flag=flag if flag != value.lower() else None,
            source_text=source_text,
        )

    return None


def _parse_qualitative_line(work: str) -> Optional[tuple[str, str]]:
    """`CRP: Negative` -- a stated result that is a word, not a number."""
    match = re.match(
        r"^(?P<name>[A-Za-z][A-Za-z0-9 ()'/%+.\-]{0,59}?)[:\s]+"
        r"(?P<value>[A-Za-z][A-Za-z \-]{0,20})$",
        work,
    )
    if not match:
        return None
    name = match.group("name").strip()
    value = match.group("value").strip()
    if value.lower() not in _QUALITATIVE_RESULTS:
        return None
    return name, value


def _usable_lab_name(name: str) -> bool:
    if not name or len(name) > MAX_NAME_CHARS:
        return False
    if len(name.split()) > MAX_NAME_WORDS:
        return False
    clean = name.strip()
    clean_lower = clean.lower()
    if clean_lower in _LAB_NAME_STOPWORDS:
        return False
    first_word = clean_lower.split()[0]
    if first_word in _LAB_NAME_STOPWORDS:
        return False
    if _LAB_NAME_FORBIDDEN.search(clean):
        return False
    if _LAB_NAME_VERBISH.search(clean):
        return False
    if _NON_LAB_PATTERNS.search(clean):
        return False
    if "@" in clean or re.search(r"[a-z0-9]+\.(?:com|org|net|in|co|io)\b", clean, re.I):
        return False
    if not re.search(r"[A-Za-z]", clean):
        return False
    return True


def _usable_lab_value(
    value: str,
    unit: Optional[str],
    name: str,
    reference_range: Optional[str] = None,
    flag: Optional[str] = None,
) -> bool:
    if not value or len(value) > MAX_VALUE_CHARS:
        return False

    digits = re.sub(r"[^\d]", "", value)
    if len(digits) >= 7:
        is_cell_count = any(k in name.lower() for k in ("platelet", "wbc", "rbc", "cells", "count")) and bool(
            unit and re.search(r"(?:/uL|/mcL|/cumm|cells|10\^|x10)", unit, re.IGNORECASE)
        )
        if not is_cell_count:
            return False

    try:
        num = float(re.sub(r"[^\d.]", "", value))
        if num >= 1000000 and not any(k in name.lower() for k in ("platelet", "wbc", "rbc", "viral")):
            return False
    except ValueError:
        pass

    if not unit:
        if reference_range or flag:
            return True
        name_lower = name.lower()
        if name_lower in _UNITLESS_ACCEPTED_TESTS:
            return True
        if any(term in name_lower for term in ("ratio", "index", "score", "inr", "ph")):
            return True
        return False

    return True


def _lab_entry(
    *,
    name: str,
    value: str,
    unit: Optional[str],
    reference_range: Optional[str],
    flag: Optional[str],
    source_text: str,
) -> dict:
    """One `lab_values` entry, in the shape the model declares."""
    entry: dict[str, Any] = {"name": name, "value": value}
    if unit:
        entry["unit"] = unit[:MAX_UNIT_CHARS]
    if reference_range:
        entry["reference_range"] = reference_range
    if flag:
        entry["flag"] = flag
    entry["source_text"] = source_text
    return entry


def _normalise_range(raw: str) -> str:
    """`12.0 - 15.0` -> `12.0-15.0`."""
    collapsed = re.sub(r"\s*[-–—]\s*", "-", raw.strip())
    collapsed = re.sub(r"\s+", "", collapsed)
    return collapsed[:MAX_VALUE_CHARS]


# ======================================================================
# medications
# ======================================================================
# Only what the document states. No drug knowledge is consulted: this module

_MEDICATION_PREFIX = re.compile(
    r"""^\s*
    (?:[-*\u2022]+\s*|\d{1,2}[.)]\s*|\([a-z]\)\s*)*           # bullet / numbering
    (?:(?:take|taken|takes|use|used|using|start|started|starting|continue|
         continued|continuing|apply|applied|inject|injected|give|given|
         prescribe|prescribed|add|added|oral|orally|topical|daily|bd|od)\s+)*
    (?:(?:tab|tabs|tablet|tablets|cap|capsule|capsules|syp|syrup|inj|injection|
         drops|oint|ointment|cream|lotion|susp|suspension|patch|suppository)\.?\s*)*
    """,
    re.VERBOSE | re.IGNORECASE,
)

_MEDICATION_NAME = re.compile(
    r"^(?P<name>[A-Z][A-Za-z'\u2019\-]{2,39}(?:\s+[A-Za-z'\u2019\-]{2,15}){0,2})"
)

_MEDICATION_DOSE = re.compile(
    r"\b(?P<dose>\d+(?:\.\d+)?)\s*(?P<unit>mg|mcg|\u00b5g|ug|gm|g|mL|ml|IU|units|U|%)\b",
    re.IGNORECASE,
)

_MEDICATION_FREQUENCY_TERMS = (
    "once daily", "twice daily", "twice a day", "three times daily",
    "three times a day", "four times daily", "four times a day",
    "once a day", "once a week", "twice a week", "three times a week",
    "as needed", "as required", "when required", "before food", "after food",
    "with food", "empty stomach", "before meals", "after meals", "after meals",
    "every morning", "every evening", "every night", "every day",
    "at bedtime", "at night", "in the morning", "once", "twice", "daily",
    "nightly", "weekly", "monthly", "three times", "four times",
)
_MEDICATION_FREQUENCY_TERMS += FREQUENCY_ABBREVIATIONS

# Longest first so "twice daily" wins over "twice"; the list is sorted at
# import so the alternation order never depends on dict or set ordering.
_FREQUENCY_ALTERNATION = "|".join(
    re.escape(term)
    for term in sorted(set(_MEDICATION_FREQUENCY_TERMS), key=lambda t: (-len(t), t))
)
_MEDICATION_FREQUENCY = re.compile(
    rf"\b(?:{_FREQUENCY_ALTERNATION})\b", re.IGNORECASE
)

# Words that open a line but are not drugs.
_MEDICATION_NAME_STOPWORDS = {
    "patient", "name", "date", "time", "dose", "dosage", "frequency",
    "duration", "route", "advice", "follow", "follow-up", "review",
    "next", "diagnosis", "history", "hospital", "clinic", "department",
    "investigation", "report", "result", "results", "before", "after",
    "with", "and", "the", "this", "that", "daily", "morning", "night",
    "evening", "day", "days", "week", "weeks", "month", "months", "no",
    "bp", "hr", "spo2", "weight", "height", "age", "sex", "dr", "note",
    "notes", "medication", "medications", "drug", "drugs", "rx",
}


def _extract_medications(lines: list[str]) -> tuple[list[dict], set[int]]:
    """Medications the document names, plus the line numbers they claimed."""
    entries: list[dict] = []
    claimed: set[int] = set()

    for index, line in enumerate(lines):
        if not _quotable(line):
            continue
        entry = _parse_medication_line(line)
        if entry:
            entries.append(entry)
            claimed.add(index)

    return _dedupe(entries, ("name", "dosage", "frequency"), MAX_MEDICATIONS), claimed


def _parse_medication_line(line: str) -> Optional[dict]:
    prefix = _MEDICATION_PREFIX.match(line)
    remainder = line[prefix.end():] if prefix else line

    dose_match = _MEDICATION_DOSE.search(remainder)
    frequency_match = _MEDICATION_FREQUENCY.search(remainder)

    # The name is whatever precedes the dose and the frequency. Reading it as
    name_end = min(
        [m.start() for m in (dose_match, frequency_match) if m] or [len(remainder)]
    )
    name_match = _MEDICATION_NAME.match(remainder[:name_end].strip())
    if not name_match:
        return None
    name = name_match.group("name").strip()
    if name.lower() in _MEDICATION_NAME_STOPWORDS:
        return None

    # A line qualifies only if the document gave it at least one of the three
    if not (prefix and prefix.group(0).strip()) and not frequency_match:
        # A dose on its own is not enough. "Glucose 126 mg/dL" has one, and
        return None

    dosage: Optional[str] = None
    if dose_match:
        # The dose exactly as printed. Never converted, rounded, or completed.
        dosage = re.sub(
            r"\s+", " ", f"{dose_match.group('dose')} {dose_match.group('unit')}"
        ).strip()

    frequency: Optional[str] = None
    if frequency_match:
        # The frequency exactly as printed. "BD" stays "BD": expanding an
        frequency = re.sub(r"\s+", " ", frequency_match.group(0)).strip()

    entry: dict[str, Any] = {"name": name[:MAX_NAME_CHARS]}
    if dosage:
        entry["dosage"] = dosage[:MAX_VALUE_CHARS]
    if frequency:
        entry["frequency"] = frequency[:MAX_METADATA_CHARS]
    entry["source_text"] = line
    return entry


# ======================================================================
# abnormal findings
# ======================================================================
# Two mechanisms, both requiring the document to say so:

# Markers that mean the same thing wherever they appear in a sentence.
_UNAMBIGUOUS_MARKERS = (
    "abnormal", "elevated", "raised", "increased", "decreased", "reduced",
    "positive", "critical", "panic value",
    "out of range", "outside the normal range", "below range", "above range",
)

# "negative" is excluded on purpose. In a lab or a radiology report it is

# "high" and "low" need more than a bare word match, because "low back pain"
_DIRECTIONAL_MARKER = re.compile(
    r"(?:\b(?:is|are|was|were|appears?|appeared|seems?|seemed|remains?|remained|"
    r"found|showing|shows)\s+(?:markedly\s+|significantly\s+|mildly\s+|"
    r"moderately\s+|slightly\s+|persistently\s+)*(?P<word>high|low)\b)"
    r"|(?:\b\d[\d.,]*\s*(?:mmHg|mg|g|mL|dL|bpm|%|/dL|/L|/uL)?\s+(?P<word2>high|low)\b)"
    r"|(?:\b(?P<word3>high|low)\s+(?:blood\s+)?(?:pressure|level|levels|count|counts|"
    r"value|values|reading|readings|range|potassium|haemoglobin|hemoglobin)\b)",
    re.IGNORECASE,
)

_ABNORMAL_MARKER = re.compile(
    r"\b(?:" + "|".join(sorted((re.escape(m) for m in _UNAMBIGUOUS_MARKERS),
                               key=lambda m: (-len(m), m))) + r")\b",
    re.IGNORECASE,
)

# Headings under which text is, by the document's own labelling, a finding.
FINDINGS_SECTION_LABELS = {
    "abnormal findings", "abnormal results", "abnormal test results",
    "significant findings", "findings", "findings/impression",
    "findings / impression", "impression", "impressions", "interpretation",
    "observations", "comments", "comment", "conclusion", "conclusions",
    "remarks", "report findings",
}

# Bare "report" is not in that set: it heads almost every document and would
# swallow the whole thing.

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _heading_pattern(labels: set[str]) -> re.Pattern:
    """An exact match for a known section heading on a line of its own."""
    alternation = "|".join(
        re.escape(label)
        for label in sorted(labels, key=lambda label: (-len(label), label))
    )
    return re.compile(rf"^(?:{alternation})\s*[:.\-]?\s*$", re.IGNORECASE)


# Built from the closed label set. The condition-heading pattern is built
# below, once `_CONDITION_SECTION_LABELS` is declared.
_FINDINGS_HEADING = _heading_pattern(FINDINGS_SECTION_LABELS)

# "Impression: No acute abnormality." -- the label and its content share a
_INLINE_SECTION = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z0-9 /&]{0,40}?)\s*:\s*(?P<body>\S.*)$"
)


def _extract_abnormal_findings(lines: list[str]) -> list[dict]:
    findings: list[dict] = []
    in_findings_section = False

    for line in lines:
        if not _quotable(line):
            continue

        # A heading on its own line opens a section for what follows.
        if _FINDINGS_HEADING.match(line):
            in_findings_section = True
            continue

        if _ANY_HEADING.match(line):
            # Some other section's heading: this findings section has ended.
            in_findings_section = False

        # A label with its content on the same line -- "Impression: ..." --
        inline = _INLINE_SECTION.match(line)
        inline_findings = False
        body = line
        if inline:
            if inline.group("label").strip().lower() in FINDINGS_SECTION_LABELS:
                inline_findings = bool(inline.group("body").strip())
                body = inline.group("body").strip()

        in_section = in_findings_section or inline_findings

        for sentence in _sentences(body):
            if _NORMALITY_STATEMENT.search(sentence):
                # The document said this part is normal. Recording it as an
                continue
            marker = _abnormal_marker(sentence)
            if marker:
                findings.append(
                    {"text": sentence, "marker": marker, "source_text": line}
                )
            elif in_section:
                # The document already told us this is a finding. The text is
                # quoted, never reinterpreted.
                findings.append(
                    {
                        "text": sentence,
                        "marker": "stated_in_findings_section",
                        "source_text": line,
                    }
                )

    return _dedupe(findings, ("text",), MAX_ABNORMAL_FINDINGS)


def _sentences(line: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(line)]
    return [part for part in parts if len(part) >= 3]


def _abnormal_marker(sentence: str) -> Optional[str]:
    match = _ABNORMAL_MARKER.search(sentence)
    if match:
        return match.group(0).lower()
    directional = _DIRECTIONAL_MARKER.search(sentence)
    if directional:
        word = directional.group("word") or directional.group("word2") or directional.group("word3")
        if word:
            return word.lower()
    return None


# Explicit statements of normality. A sentence the document itself marks as
_NORMALITY_STATEMENT = re.compile(
    r"\b(?:unremarkable|within\s+normal\s+limits?|normal\s+(?:study|chest|examination|"
    r"findings?|appearance)|no\s+(?:acute|significant|abnormal\w*|evidence\s+of|"
    r"focal|active)|negative\s+for|within\s+range|no\s+definite)\b",
    re.IGNORECASE,
)


# ======================================================================
# stated conditions
# ======================================================================
# A condition is recorded only where the document states one. There is no

_CONDITION_PATTERNS = (
    re.compile(
        r"\b(?:past\s+medical\s+history|medical\s+history|clinical\s+history|pmh|hx)\s*"
        r"(?:of|includes?)?\s*[:\-]?\s*(?P<value>[^.!?\n]{2,120})",
        re.IGNORECASE,
    ),
    re.compile(r"\bhistory\s+of\s+(?P<value>[^.!?\n]{2,120})", re.IGNORECASE),
    re.compile(r"\bh/o\s+(?P<value>[^.!?\n]{2,120})", re.IGNORECASE),
    re.compile(r"\bknown\s+(?:case\s+of\s+)?(?P<value>[^.!?\n]{2,120})", re.IGNORECASE),
    re.compile(
        r"\b(?:diagnosis|diagnosed\s+with|dx|d/dx|condition|comorbidity|"
        r"comorbidities|medical\s+problem|problem\s+list)\s*[:\-]?\s*"
        r"(?P<value>[^.!?\n]{2,120})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:suffers?\s+from|suffering\s+from|under\s+treatment\s+for|"
        r"being\s+treated\s+for|on\s+treatment\s+for)\s+(?P<value>[^.!?\n]{2,120})",
        re.IGNORECASE,
    ),
    re.compile(r"\bcase\s+of\s+(?P<value>[^.!?\n]{2,120})", re.IGNORECASE),
)

# Section headings whose contents are conditions. Excludes bare "history" and
# bare "problems", which head too much unrelated prose to trust.
_CONDITION_SECTION_LABELS = {
    "medical history", "past medical history", "past history",
    "clinical history", "medical problems", "diagnoses", "diagnosis",
    "comorbidities", "comorbid conditions", "known conditions",
    "problems", "background", "clinical background",
}

_CONDITION_HEADING = _heading_pattern(_CONDITION_SECTION_LABELS)

# Any recognised heading. A findings section has to end when some *other*
_SECTION_BOUNDARY_LABELS = {
    "medications", "medication", "drugs", "drug", "prescriptions",
    "prescription", "treatment", "plan", "advice", "recommendations",
    "recommendation", "instructions", "notes", "note", "summary",
    "next steps", "follow up", "follow-up", "references", "signature",
    "authorised by", "authorized by", "signed by", "specimen", "sample",
    "patient details", "investigation", "tests", "results", "result",
    "vitals", "observations chart", "allergies", "immunisations",
    "immunizations", "procedures", "procedure",
}

_ANY_HEADING = _heading_pattern(
    _CONDITION_SECTION_LABELS | FINDINGS_SECTION_LABELS | _SECTION_BOUNDARY_LABELS
)

# A line that denies having the thing it goes on to mention. "No known chronic
_CONDITION_NEGATION = re.compile(
    r"\b(?:no|not|never|denies|deny|without|nil|none)\s+(?:\w+\s+){0,3}?"
    r"(?:known|significant|history|diagnosed|conditions?|problems?|illness|"
    r"illnesses|diseases?|comorbidit\w*|medications?|allergies)\b",
    re.IGNORECASE,
)

# Answers that mean "the document said there is nothing", which must not be
# recorded as though the document had said something.
_NON_CONDITION_ANSWERS = {
    "none", "nil", "nothing", "no", "not known", "unknown", "unremarkable",
    "normal", "negative", "not documented", "not recorded", "not applicable",
    "n/a", "na", "no significant history", "no significant past history",
    "no known illness", "no active issues", "denies", "not applicable.",
}


def _extract_stated_conditions(lines: list[str]) -> list[dict]:
    conditions: list[dict] = []
    in_condition_section = False

    for line in lines:
        if not _quotable(line):
            continue

        # "No known chronic conditions" states the absence of a condition. The
        if _CONDITION_NEGATION.search(line):
            continue

        if _CONDITION_HEADING.match(line):
            # The heading is a label, not a condition. "Medical history:" opens
            in_condition_section = True
            continue

        if _ANY_HEADING.match(line):
            in_condition_section = False

        matched = False
        for pattern in _CONDITION_PATTERNS:
            for match in pattern.finditer(line):
                value = _clean_condition(match.group("value"))
                if value:
                    conditions.append({"text": value, "source_text": line})
                    matched = True
                    break
            if matched:
                break

        if in_condition_section and not matched:
            cleaned = _clean_condition(line)
            if cleaned:
                conditions.append({"text": cleaned, "source_text": line})

    return _dedupe(conditions, ("text",), MAX_STATED_CONDITIONS)


def _clean_condition(raw: str) -> Optional[str]:
    """Trim a captured condition, or refuse it."""
    value = raw.strip().strip(".,;:").strip()
    value = re.sub(r"^(?:of|includes?|and)\s+", "", value, flags=re.IGNORECASE).strip()
    if len(value) < 3 or len(value) > MAX_CONDITION_CHARS:
        return None
    if value.lower() in _NON_CONDITION_ANSWERS:
        return None
    # A condition is named in words. A bare number is not one.
    if not re.search(r"[A-Za-z]{3}", value):
        return None
    # Reject a captured clause that is really a sentence about something else.
    if _LAB_NAME_VERBISH.search(value):
        return None
    return value