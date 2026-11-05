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

    lab_values, _claimed_lab_lines = _guard(
        _extract_lab_values, lines, medication_lines, default=([], set())
    )
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
# separator check below decides where the name ends. Real reports also
# print serial numbers ("1 Haemoglobin ...") and names that start with a
# digit ("25-OH Vitamin D"), so the name may start with a digit --
# `_usable_lab_name` refuses pure-number first words to keep ranges such as
# "200 to 499 mg/dL" from becoming a test.
_LAB_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9 ()'/%+.\-]{0,59}?)[:\s]+"
    r"(?P<value>[<>≤≥]?\s*-?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>\S{1,12})?\s*$"
)

# Tolerates one extra trailing word after the unit -- the "Method" column of
# many lab reports ("236 mg/dL Enzymatic"). The extra word is dropped, never
# recorded; the value, unit and any printed range stand on their own.
_LAB_LINE_EXTRA = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9 ()'/%+.\-]{0,59}?)[:\s]+"
    r"(?P<value>[<>≤≥]?\s*-?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>\S{1,12})\s+"
    r"(?P<extra>[A-Za-z][A-Za-z\-]{1,19})\s*$"
)

# A serial-number or bullet prefix on a table row. Bare numbers need care:
# "200 to 499 mg/dL" is a reference-range bullet, not "serial 200" -- the
# negative lookahead keeps comparator words from being treated as a name.
_ROW_PREFIX = re.compile(
    r"^\s*(?:[-•·*]+\s+|\d{1,3}[.)]\s+|\(\d{1,3}\)\s+|"
    r"\d{1,3}\s+(?![A-Za-z]*(?:to|and|or|than)\b)(?=[A-Za-z]))"
)

_UNIT_SHAPE = re.compile(
    r"^(?:%|[A-Za-zµμ][A-Za-z0-9%./µμ*\-^_]{0,5}"
    r"|[A-Za-zµμ][A-Za-z0-9µμ]*\/[A-Za-z][A-Za-z0-9]{0,6}"
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

# A reference range printed without brackets, at the end of a row:
# "236 mg/dL 0-200", "236 mg/dL <200", "210 mg/dL 150 to 199". Anchored to
# the end, and `_pop_trailing_range` refuses to take the row's own result
# value, which has the same shape.
_TRAILING_RANGE_BARE = re.compile(
    r"\s*(?P<range>[<>≤≥]\s*-?\d[\d.,]*|"
    r"-?\d[\d.,]*\s*(?:-|–|—|to)\s*-?\d[\d.,]*)\s*$",
    re.IGNORECASE,
)

# A printed result line with no test name -- the patient's own number,
# which tables and OCR frequently put on the line under the test name.
_VALUE_LINE = re.compile(
    r"^\s*(?P<value>[<>≤≥]?\s*-?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>\S{1,12})?\s*$"
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

# Reference-range descriptors read as test names by a naive split on the
# number: "Less than 200 mg/dL" would otherwise become a test called
# "Less than". None of these can start a test name.
_LAB_NAME_COMPARATOR = re.compile(
    r"^(?:less than|greater than|more than|no more than|up to|at least|"
    r"below|above|over|under|borderline|very high|near optimal|optimal|"
    r"desirable)\b",
    re.IGNORECASE,
)

# Single interpretation labels, never test names on their own.
_LAB_NAME_INTERPRETATION_LABELS = {
    "high", "low", "normal", "abnormal", "critical", "positive", "negative",
    "borderline high", "very high", "near optimal", "optimal", "desirable",
    "increased", "decreased", "elevated",
}

# Demographics that appear on more laboratory reports than they should, and
_LAB_NAME_FORBIDDEN = re.compile(
    r"\b(?:date\s+of\s+birth|birth\s*date|d\.?\s?o\.?\s?b\.?|born|age\s+of)\b",
    re.IGNORECASE,
)


def _extract_lab_values(
    lines: list[str], medication_lines: set[int]
) -> tuple[list[dict], set[int]]:
    found: list[dict] = []
    claimed: set[int] = set()
    for index, line in enumerate(lines):
        if index in medication_lines:
            # "Metformin 500 mg twice daily" is a prescription, not a
            continue
        if not _quotable(line):
            continue
        entry = _parse_lab_line(line)
        if entry:
            found.append(entry)
            claimed.add(index)

    found.extend(_extract_split_lab_values(lines, medication_lines, claimed))
    return _dedupe(found, ("name", "value", "unit"), MAX_LAB_VALUES), claimed


def _parse_lab_line(line: str) -> Optional[dict]:
    """One laboratory row, or `None` if this line is not one."""
    stripped = _ROW_PREFIX.sub("", line).strip()
    if not stripped:
        return None

    cell_entry = _parse_cell_row(line, stripped)
    if cell_entry:
        return cell_entry

    # A qualitative result ("CRP: Negative") IS the trailing word itself;
    # stripping it as a marker would leave nothing to read. Take it whole.
    if _parse_qualitative_line(stripped):
        entry = _interpret_lab_text(stripped, line, None, None)
        if entry:
            return entry

    # Measured with the whole line stripped of its trailing range and flag,
    # in either order -- "236 mg/dL High (200-239)" and
    # "236 mg/dL (200-239) H" are the same row.
    working = stripped
    reference_range: Optional[str] = None
    flag: Optional[str] = None
    for _ in range(4):
        remainder, range_found = _pop_trailing_range(working)
        if range_found:
            reference_range = reference_range or range_found
            working = remainder
            continue
        remainder, marker = _pop_trailing_marker(working)
        if marker and flag is None:
            flag = marker
        if remainder != working:
            working = remainder
            continue
        break

    entry = _interpret_lab_text(working, line, reference_range, flag)
    if entry:
        return entry

    # A trailing word that is not a unit, a range or a marker: the "Method"
    # column ("236 mg/dL Enzymatic"). Only accepted when what remains is a
    # full lab row in its own right.
    if working:
        entry = _interpret_lab_text_extra(working, line, reference_range, flag)
        if entry:
            return entry

    # Measured with the whole line stripped of its trailing range and flag,
    # in either order -- "236 mg/dL High (200-239)" and
    # "236 mg/dL (200-239) H" are the same row.
    if flag is None and reference_range is None:
        entry = _parse_trailing_result_row(stripped)
        if entry:
            return entry
    return None


def _pop_trailing_marker(text: str) -> tuple[str, Optional[str]]:
    """Remove a printed marker from the end of a row, or leave it alone."""
    marker_match = _TRAILING_MARKER.search(text)
    if not marker_match:
        return text, None
    token = marker_match.group("marker")
    flag = _MARKER_FLAGS.get(token.lower())
    if not flag:
        return text, None
    stripped = text[: marker_match.start()].strip()
    if not stripped or _token_is_unit(text, token):
        return text, None
    return stripped, flag


def _parse_cell_row(line: str, stripped: str) -> Optional[dict]:
    """A table row spread across cells, in one extracted line.

    Delimited rows -- "Total Cholesterol | 236 | mg/dL | <200 | High",
    including the multi-space shape pypdf emits for columnar reports --
    are read cell by cell while single-space prose stays on the prose
    path. The first cell is the test name, the first numeric cell is
    the result, and any remaining cell is taken as a unit, a reference
    range or a marker, in column order.
    """
    if "|" not in stripped and "\t" not in stripped and not re.search(r"\s{2,}", stripped):
        return None
    # Markdown emphasis from a vision model ("**236 mg/dL**") is not part
    # of the printed row; drop it for parsing while `source_text` keeps
    # the original line.
    cells = [
        cell.strip().replace("*", "").strip()
        for cell in re.split(r"\||\t|\s{2,}", stripped)
        if cell.strip()
    ]
    if len(cells) < 2:
        return None

    value_index = next(
        (index for index, cell in enumerate(cells) if _CELL_VALUE.match(cell)),
        None,
    )
    if value_index is None or value_index == 0:
        return None

    name_parts: list[str] = []
    reference_range: Optional[str] = None
    for cell in cells[:value_index]:
        if _looks_like_range_cell(cell):
            if reference_range is None:
                reference_range = _range_from_cell(cell)
        else:
            name_parts.append(cell)
    name = " ".join(name_parts).strip()
    if not name:
        return None

    value_cell = _CELL_VALUE.match(cells[value_index])
    assert value_cell is not None
    value = (value_cell.group("value") or "").strip()
    unit = (value_cell.group("unit") or "").strip() or None
    if unit and not _UNIT_SHAPE.match(unit):
        return None

    flag: Optional[str] = None
    for cell in cells[value_index + 1:]:
        bare = cell.strip("()").strip()
        marker = _MARKER_FLAGS.get(bare.lower())
        if marker and flag is None:
            flag = marker
            continue
        if unit is None and _UNIT_SHAPE.match(cell):
            unit = cell
            continue
        if reference_range is None and _looks_like_range_cell(cell):
            reference_range = _range_from_cell(cell)
            continue

    if not _usable_lab_name(name):
        return None
    if not _usable_lab_value(value, unit, name, reference_range, flag):
        return None
    return _lab_entry(
        name=name,
        value=value,
        unit=unit,
        reference_range=reference_range,
        flag=flag,
        source_text=line,
    )


_CELL_VALUE = re.compile(
    r"^(?P<value>[<>≤≥]?\s*-?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>[A-Za-z%µμ][A-Za-z0-9%./µμ*\-^_]{0,11})?$"
)

_CELL_RANGE = re.compile(
    r"^(?:less than|greater than|more than|up to|at least|below|above)\b", re.IGNORECASE
)


def _looks_like_range_cell(cell: str) -> bool:
    """True when a cell holds a reference range rather than a name."""
    cleaned = cell.strip()
    if _CELL_RANGE.match(cleaned):
        return True
    if re.match(r"^[<>≤≥]?\s*-?\d[\d.,]*\s*(?:-|–|—|to)\s*-?\d[\d.,]*", cleaned):
        return True
    return bool(re.match(r"^[<>≤≥]\s*-?\d[\d.,]*\s*[A-Za-z%]*$", cleaned.strip()))


def _range_from_cell(cell: str) -> str:
    """The printed range in a reference cell, without its words.

    "Less than 200 mg/dL" becomes "<200"; "200-239 mg/dL" stays
    "200-239". The words are the document's prose for the range and
    are not carried into the stored field.
    """
    range_match = re.search(r"-?\d[\d.,]*\s*(?:-|–|—|to)\s*-?\d[\d.,]*", cell)
    if range_match:
        return _normalise_range(range_match.group(0))
    number_match = re.search(r"-?\d[\d.,]*", cell)
    if number_match:
        stripped = cell.strip()
        lowered = cell.lower()
        if stripped and stripped[0] in "<>≤≥":
            prefix = stripped[0]
        elif lowered.startswith(("less than", "up to", "below", "under")):
            prefix = "<"
        elif lowered.startswith(("greater than", "more than", "above", "over")):
            prefix = ">"
        elif lowered.startswith("at least"):
            prefix = ">="
        else:
            prefix = ""
        return (prefix + number_match.group(0))[:MAX_VALUE_CHARS]
    return _normalise_range(cell)


def _extract_split_lab_values(
    lines: list[str],
    medication_lines: set[int],
    claimed: set[int],
) -> list[dict]:
    """Test name on one line, result on the line under it.

    Tables flattened by pypdf or OCR routinely put the name and the
    patient's result on separate lines -- "Total cholesterol" over
    "236 mg/dL" -- which no single-line parse can recover. The name
    line must read as a test name on its own, and the result line must
    be a bare result: a number with an optional unit, never a
    reference-range bullet or a date.
    """
    found: list[dict] = []
    claimed_values: set[int] = set()
    for index, line in enumerate(lines):
        if index in claimed or index in medication_lines:
            continue
        if not _quotable(line) or ":" in line:
            continue
        if not _looks_like_test_name(line):
            continue
        for ahead in range(1, 4):
            if index + ahead >= len(lines):
                break
            value_line = lines[index + ahead]
            if index + ahead in claimed or index + ahead in medication_lines:
                continue
            if not _quotable(value_line) or _looks_like_range_cell(value_line):
                continue
            entry = _parse_value_line(line, value_line)
            if entry:
                found.append(entry)
                claimed_values.add(index + ahead)
                break
    return found


def _looks_like_test_name(line: str) -> bool:
    """A line that names a test without stating a result."""
    if _ANY_HEADING.match(line):
        return False
    if _FINDINGS_HEADING.match(line) or _CONDITION_HEADING.match(line):
        return False
    if _LAB_NAME_FORBIDDEN.search(line) or _LAB_NAME_VERBISH.search(line):
        return False
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ()'/%+.\-]{0,59}", line):
        # Also accept names that start with a digit-letter pair ("25-OH ...").
        if not re.fullmatch(r"[A-Za-z0-9]*[A-Za-z][A-Za-z0-9 ()'/%+.\-]{0,59}", line):
            return False
    if re.search(r"\d{4}-\d{2}-\d{2}", line):
        return False
    return _usable_lab_name(line)


def _parse_value_line(name_line: str, value_line: str) -> Optional[dict]:
    """Pair a name line with the result line beneath it."""
    # Anything that is itself a full lab row is the other row's start.
    if _parse_lab_line(value_line):
        return None
    if _is_date_like(value_line):
        return None
    # A bare result has no serial number of its own; the row prefix must
    # not eat its value ("236 mg/dL" is a result, not serial 236).
    work = value_line.strip()
    match = _VALUE_LINE.match(work)
    if not match:
        return None
    value = (match.group("value") or "").strip()
    unit = (match.group("unit") or "").strip()
    if unit and not _UNIT_SHAPE.match(unit):
        return None
    # A 4-digit year next to a name is a date, not a result.
    digits = re.sub(r"[^\d]", "", value)
    if len(digits) == 4 and value.startswith(("19", "20")) and not unit:
        return None
    # A trailing range or marker on the result line is printed too.
    remainder, reference_range = _pop_trailing_range(work)
    remainder, marker = _pop_trailing_marker(remainder)
    if remainder != work:
        reparsing = _VALUE_LINE.match(remainder)
        if not reparsing:
            return None
        value = (reparsing.group("value") or "").strip()
        unit = (reparsing.group("unit") or "").strip()
    flag = marker
    name = name_line.strip()
    if not _usable_lab_value(value, unit or None, name, reference_range, flag):
        return None
    source_text = name_line + "\n" + value_line
    if len(source_text) > MAX_SOURCE_TEXT_CHARS or not source_text:
        return None
    return _lab_entry(
        name=name,
        value=value,
        unit=unit or None,
        reference_range=reference_range,
        flag=flag,
        source_text=source_text,
    )


def _is_date_like(line: str) -> bool:
    if re.search(r"\b\d{4}-\d{1,2}-\d{1,2}\b", line):
        return True
    if re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", line):
        return True
    return False


# A table row read left to right in which the reference range occupies
# the middle columns and the patient's result is the last number on the
# line: "Total cholesterol Less than 200 mg/dL (Desirable) 236". The
# trailing number (with an optional unit) is the result; the text
# between the test name and that number is the printed reference text
# and is not converted into a single reference range.
_TRAILING_RESULT = re.compile(
    r"(?:^|\s)(?P<value>[<>≤≥]?\s*-?\d[\d,]*(?:\.\d+)?)"
    r"(?:\s+(?P<unit>\S{1,12}))?\s*$"
)

_TRAILING_NAME_TAIL = re.compile(
    r"\s+(?:less than|greater than|more than|no more than|up to|at least|"
    r"below|above|over|under|and|or|to)\s*$",
    re.IGNORECASE,
)


def _parse_trailing_result_row(line: str) -> Optional[dict]:
    """A flattened table row whose result is its last number."""
    if not re.search(r"\d", line):
        return None
    # Needs a printed reference-range token in the middle of the line;
    # without one a trailing number is prose, not a table cell.
    if not _looks_like_range_cell(line) and not re.search(
        r"(?:less than|greater than|more than|up to|at least)\b", line, re.IGNORECASE
    ):
        return None

    working = line
    _remainder, flag = _pop_trailing_marker(working)
    working = _remainder
    trailing = _TRAILING_RESULT.search(working)
    if not trailing:
        return None
    value = (trailing.group("value") or "").strip()
    unit = (trailing.group("unit") or "").strip()
    if unit and not _UNIT_SHAPE.match(unit):
        # The word after the result is the interpretation, not a unit.
        unit = ""
    if not unit:
        # A bare result column inherits the unit the row itself prints
        # beside its reference values ("Less than 200 mg/dL").
        middle = working[: trailing.start()]
        for candidate_match in re.finditer(
            r"\d\s*(?P<u>[A-Za-z%µμ][A-Za-z0-9%./µμ*\-^_]{0,11})", middle
        ):
            candidate = candidate_match.group("u")
            if _UNIT_SHAPE.match(candidate):
                unit = candidate
                break

    name = working[: trailing.start()].strip(" :,|")
    # The name ends where the reference text starts: the first digit on
    # its own (not the digit inside an abbreviation like B12).
    digit_at = re.search(r"(?:^|\s)\d", name)
    if digit_at:
        name = name[: digit_at.start()].strip(" :,|")
    while True:
        trimmed = _TRAILING_NAME_TAIL.sub("", name).strip(" :,|")
        if trimmed == name:
            break
        name = trimmed
    if not _usable_lab_name(name):
        return None
    if not _usable_lab_value(value, unit or None, name, None, flag):
        return None
    return _lab_entry(
        name=name,
        value=value,
        unit=unit or None,
        reference_range=None,
        flag=flag,
        source_text=line,
    )


def _interpret_lab_text_extra(
    text: str, source_text: str, reference_range: Optional[str], flag: Optional[str]
) -> Optional[dict]:
    """A lab row followed by one extra word (the Method column)."""
    match = _LAB_LINE_EXTRA.match(text)
    if not match:
        return None
    name = (match.group("name") or "").strip()
    value = (match.group("value") or "").strip()
    unit = (match.group("unit") or "").strip()
    if unit and not _UNIT_SHAPE.match(unit):
        return None
    # Only a unit that looks like an abbreviation may carry a Method-column
    # word after it; otherwise the "extra word" is part of a name that
    # happens to sit next to a number ("Type 2 Diabetes Mellitus").
    if "/" not in unit and "%" not in unit and len(unit) > 4:
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

    bare = _TRAILING_RANGE_BARE.search(text)
    if bare:
        # Never take the row's own result value, which has the same shape
        # as a range tail ("Cholesterol 236" must not become a range).
        preceding = text[: bare.start()]
        if re.search(r"[A-Za-z]", preceding) and re.search(r"\d", preceding):
            return (
                preceding.strip(),
                _normalise_range(bare.group("range")),
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
    clean = name.strip()
    if len(clean) < 2:
        return False
    if len(clean.split()) > MAX_NAME_WORDS:
        return False
    clean_lower = clean.lower()
    if clean_lower in {"x", "p/a", "r/a", "wt", "weight", "ht", "height", "bmi", "bp", "hr", "pulse", "temp", "rr"}:
        return False
    clean = name.strip()
    clean_lower = clean.lower()
    if clean_lower in _LAB_NAME_STOPWORDS:
        return False
    if clean_lower in _LAB_NAME_INTERPRETATION_LABELS:
        return False
    if clean_lower in {"to", "and", "or", "of", "the", "a", "an", "for"}:
        return False
    if _LAB_NAME_COMPARATOR.match(clean):
        return False
    first_word = clean_lower.split()[0]
    if first_word in _LAB_NAME_STOPWORDS:
        return False
    # A bare number cannot open a test name ("200 to 499 mg/dL" is a
    # reference range, not a test called "200 to"). Names that start with a
    # number combined with a letter ("25-OH Vitamin D") are fine.
    if first_word.isdigit():
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

    if unit and unit.lower().strip() in {"month", "months", "mon", "yr", "yrs", "year", "years", "day", "days", "wk", "wks", "week", "weeks", "hr", "hrs", "hour", "hours", "min", "mins"}:
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
    collapsed = re.sub(r"\s+to\s+", "-", raw.strip(), flags=re.IGNORECASE)
    collapsed = re.sub(r"\s*[-–—]\s*", "-", collapsed)
    collapsed = re.sub(r"\s+", "", collapsed)
    return collapsed[:MAX_VALUE_CHARS]


# ======================================================================
# medications
# ======================================================================
# Only what the document states. No drug knowledge is consulted: this module

_MEDICATION_PREFIX = re.compile(
    r"""^\s*
    (?:[-*\u2022]+\s*|\d{1,2}[.)]\s*|\([0-9a-zA-Z]+\)\s*)*           # bullet / numbering
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

    has_prefix = bool(prefix and prefix.group(0).strip())
    if not has_prefix and not frequency_match:
        return None

    if has_prefix and not frequency_match:
        p_str = prefix.group(0).strip()
        is_only_bullet = bool(re.match(r"^[-*\u2022\d.()]+$", p_str))
        if is_only_bullet and not dose_match:
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

# Reference-range cell shapes. In a flattened table these are as common as
# plausible prose, and recording one as a finding or a condition invents
# the claim the document never made.
_TABLE_RANGE_START = re.compile(
    r"^\s*[-•·*]?\s*[<>≤≥]?\s*-?\d[\d.,]*\s*(?:-|–|—|to)\s*\d[\d.,]*"
)
_TABLE_COMPARATOR = re.compile(
    r"\b(?:less|greater)\s+than\b.*\d|\b(?:more than|up to|at least)\b.*\d",
    re.IGNORECASE,
)
_TABLE_RANGE_DESCRIPTOR = re.compile(
    r"^\s*[-•·*]?\s*(?:less than|greater than|more than|no more than|up to|"
    r"at least|below|above|over|under)\b",
    re.IGNORECASE,
)
_TABLE_PAREN_LABEL = re.compile(r"\(\s*[A-Za-z][A-Za-z ]{1,30}\s*\)\s*$")
_TABLE_ABOVE_BELOW = re.compile(
    r"(?:^|\W)(?:above|higher|below|lower)(?:\W|$)", re.IGNORECASE
)
_TABLE_UNIT_TAIL = re.compile(r"\d\s*(?:mg|g|ml|l|u|%|/)", re.IGNORECASE)


def _is_table_cell_line(line: str) -> bool:
    """True when a line is a results-table cell, not prose."""
    if _TABLE_RANGE_START.match(line):
        return True
    if _TABLE_RANGE_DESCRIPTOR.match(line):
        return True
    if _TABLE_COMPARATOR.search(line) and re.search(r"\d", line):
        return True
    if _TABLE_ABOVE_BELOW.search(line) and _TABLE_UNIT_TAIL.search(line):
        return True
    if _TABLE_PAREN_LABEL.search(line) and len(line.split()) <= 3:
        return True
    return False


def _lab_row_like(line: str) -> bool:
    """True when a line is a lab row with a unit-like token."""
    entry = _parse_lab_line(line)
    if not entry:
        return False
    unit = entry.get("unit") or ""
    return bool(unit) and ("/" in unit or "%" in unit or len(unit) <= 4)


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

        if _is_table_cell_line(line) or _lab_row_like(line):
            # A results table begins or continues here; its cells are for
            # `lab_values`, never for this prose section.
            in_findings_section = False
            continue

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
                # quoted, never reinterpreted. A single fragment ("Total",
                # "high)") is a table cell that leaked into the text, not a
                # finding, so section captures need at least two words.
                if len(sentence.split()) < 2:
                    continue
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
    # Tables of test results end whatever prose section came before them;
    # leaving one open would record the whole results table as prose.
    "test results", "test result", "lab results", "lab result",
    "laboratory results", "laboratory", "lab", "patient results",
    "patient's result", "reference range", "reference ranges",
    "normal range", "results table", "lipid profile",
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

        if _is_table_cell_line(line) or _lab_row_like(line):
            # A results table begins or continues here; its cells are never
            # stated conditions.
            in_condition_section = False
            continue

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

        # A section capture needs a multi-word entry: a single fragment
        # ("Total", "cholesterol") is a table name or cell, not a condition.
        if in_condition_section and not matched:
            if len(line.split()) < 2:
                continue
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