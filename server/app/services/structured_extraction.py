"""Deterministic structured extraction of explicitly stated medical facts.

Scope of this module: take the plain text a PDF already yielded, and pull out
the facts the document *states outright* into the `ExtractedData` shape the
model already declares. Nothing else.

    PDF --(extraction_service)--> text --(this module)--> extracted_data

Why this sits between the text and any future summary is the whole point of
the phase. A summarizer handed 500,000 characters of raw clinical prose has to
decide what it is looking at; a summarizer handed structured, source-attributed
facts does not. Everything that can be established deterministically is
established here first, so nothing that can be checked is left to be guessed.

Three rules are load-bearing, and each of them is a safety property rather than
a parsing detail:

  * **Nothing is inferred.** Every value here was written on the page. A lab
    number is never turned into a condition, a medication is never turned into
    a recommendation, and a sentence about a body part is never promoted to a
    finding because it contains medical vocabulary.

  * **`flag` is transcribed, never computed.** A laboratory value is marked
    abnormal *only* when the document itself prints a marker next to it --
    `H`, `L`, `*`, `(High)`. Comparing a number against a reference range is
    deliberately NOT done here, even though the range is present in the text,
    because that comparison is an interpretation and an interpretation is
    exactly what this layer exists to avoid. It would also be fragile: `<5`,
    `>180` and `70-99` are not the same shape of claim as `12-16`, and a
    mistaken "high" would enter a future summary as a clinical fact.

  * **Every fact carries `source_text`.** A future summary must be able to
    deep-link any claim back to the line it came from. A fact that cannot be
    attributed to a line is dropped rather than kept "approximately right",
    because an untraceable claim in a medical record is worse than a missing
    one.

Determinism is a hard requirement, not a convenience: the same text must
always produce the same structure, so tests can assert on it and a demo can be
reproduced. Every pass below walks the text in document order, sorts nothing
that depends on set iteration, and derives every decision from the text itself.

Bounded by construction. `extracted_text` is already capped at
`MAX_EXTRACTED_CHARS` by the text extractor, and this module caps it again
along with the number of lines it will read, the number of facts per category,
and the length of any single fact. A pathological document therefore cannot
produce an unbounded structure.

Nothing here logs document content. On failure it logs the exception *type*,
which is the only thing about a parse error that is safe to write down.
"""

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
# cannot turn this pass into the memory problem the upload limits already
# guard against. They are constants rather than inline numbers so the
# trade-off is stated in one place: a truncated pass is an incomplete one,
# never an unbounded one.

# Mirrors extraction_service.MAX_EXTRACTED_CHARS. The text extractor already
# enforces it; re-checking here means this module is safe to call on text from
# any origin, not only from that one caller.
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
# than truncated -- a clipped quote is not a quote. This is the one bound that
# costs recall instead of only costing speed.
MAX_SOURCE_TEXT_CHARS = 300

# How far into the document to look for a labelled header. Metadata lives at
# the top; scanning all 20,000 lines for "Hospital:" would be wasted work and
# would find a footer address long after the real header.
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
    """Pull explicitly stated facts out of extracted document text.

    Pure, deterministic, and exception-safe. Takes text, returns the
    `ExtractedData` shape -- never raises, never touches the database or the
    network, and never returns a key it has nothing to say about.

    A field the document does not state is **absent from the result**, not
    present-and-null. That is the representation the architecture specifies,
    and it is what lets "not found in the uploaded records" propagate to a
    future summary instead of a screen having to distinguish "empty" from
    "absent".
    """
    if not isinstance(text, str) or not text.strip():
        return {}

    # Bounded before anything else touches the string.
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]

    # Guarded like every other pass, even though it is the one that touches
    # the raw string first: the contract that `extract_structured` never raises
    # has to hold for the whole function, not just for its tail.
    lines = _guard(_readable_lines, text, default=[])
    if not lines:
        return {}

    result: ExtractedData = {}

    # Medications first: a prescription line ("Metformin 500 mg twice daily")
    # also looks like a lab row to a value-shaped pattern, and it must not be
    # counted as a measurement. Parsing them in this order lets the lab pass
    # skip the lines that are really prescriptions.
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
    """Run one extraction pass, degrading to `default` if it raises.

    One category failing must not discard the categories that already
    succeeded, and must never propagate -- an exception here would turn a
    successfully extracted document into a failed upload, which is precisely
    the coupling the pipeline is written to avoid.
    """
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
    """Split into non-empty, whitespace-trimmed lines, up to `MAX_LINES`.

    Trimming the ends of a line does not change what it says, and it keeps
    every `source_text` a clean quote of the line it came from. Interior
    spacing is left exactly as extracted -- reflowing a record would be
    editing it.
    """
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
    """First occurrence wins, in document order, capped at `limit`.

    Real records repeat themselves -- the same test printed in a header table
    and again in the body -- and a summary that lists a value three times
    because the PDF said it three times is noise. Order is preserved because
    the input is ordered; no set is ever iterated to build the result.
    """
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
# and no positional guess: "the first line" is where a letterhead lives on a
# letterhead and where a patient's name lives on a discharge summary, and
# guessing between those two is exactly the kind of inference this layer must
# not do. A field with no label is left absent.

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
    "hospital", "hospital name", "clinic", "clinic name", "laboratory",
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
# a doctor, because neither is a labelled field. Both are reachable only
# through `_labelled_value`.


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
    """The first date the document labels as its own.

    Precedence is deliberate. A `document_date` the patient typed at upload is
    the document's date of record and lives on the document row; this field is
    a *separate* reading of what the file says, and it never overwrites it.
    Which one a screen shows is a display decision; both are recorded.

    Two ambiguity rules, both of which choose "no answer" over "wrong answer":

      * Only `YYYY-MM-DD` / `YYYY/MM/DD` is always accepted, because the
        four-digit year in front removes the day/month ordering question.
      * `DD/MM/YYYY` is accepted **only** when the leading number is above 12,
        which proves it is a day and not a month. `03/04/2025` is refused
        outright rather than resolved to one of two readings.

    Every candidate is then checked against the real calendar, so `2026-02-30`
    is rejected rather than normalised into a different day.
    """
    for line in lines[:MAX_METADATA_LINES]:
        if not _quotable(line):
            continue
        if _BIRTH_CONTEXT.search(line):
            continue

        # A line that is nothing but a date is a report-date heading.
        # A line that is *nothing but* a date is a report-date heading, and
        # needs no label. A line that merely *contains* one does need a label
        # in front of it: "Next appointment 2025-11-02" prints a date, but the
        # date is the appointment's, not the document's, and accepting it
        # because a date happened to appear in the text would be exactly the
        # guessing this module must not do.
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
    """True when a line consists of a date and nothing else.

    Anchored at both ends, so `2025-11-02 (repeat)` and `Next appointment
    2025-11-02` both fail -- they print something else as well.
    """
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
    """Turn a date the document printed into `YYYY-MM-DD`, or refuse it.

    The ambiguity rule is enforced here as well as at the call site, because
    this is the function that actually commits a day and a month to a value --
    and a date that reaches a summary as a confident ISO string cannot be
    walked back afterwards.
    """
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
# separator is required, so "Glucose 126 mg/dL" splits at the first point that
# leaves a number in the right place and the rest of the line accounted for.
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
_LAB_NAME_STOPWORDS = {
    "age", "sex", "gender", "dob", "d o b", "date", "born", "birth",
    "page", "page no", "pages", "phone", "tel", "telephone", "id",
    "identification", "no", "s/n", "ref", "ref no", "mr no", "mrn",
    "hospital no", "unit no", "bed", "ward", "doctor", "dr", "name",
    "patient", "patient name", "address", "email", "fax", "time",
    "total pages", "report", "result", "results", "test", "tests",
}

# A name containing a copula or a perception verb is a sentence, not a label.
_LAB_NAME_VERBISH = re.compile(
    r"\b(?:is|are|was|were|be|been|has|have|had|shows?|showed|show|"
    r"reveals?|revealed|found|reports?|reported|noted|seen|measured)\b",
    re.IGNORECASE,
)

# Demographics that appear on more laboratory reports than they should, and
# which must never be recorded as an observation about the patient. The
# "tail must be fully accounted for" rule already rejects most of these; this
# catches the ones where the numbers happen to line up.
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
            # measurement of the patient. Letting the value pattern claim it
            # would report a dose as though it were an observed lab result.
            continue
        if not _quotable(line):
            continue
        entry = _parse_lab_line(line)
        if entry:
            found.append(entry)

    return _dedupe(found, ("name", "value", "unit"), MAX_LAB_VALUES)


def _parse_lab_line(line: str) -> Optional[dict]:
    """One laboratory row, or `None` if this line is not one.

    The line is read at most twice: once with a trailing explicit marker
    removed, and once without. Trying the marker reading first matters for
    two reasons. "Glucose 126 mg/dL H" only has a value once the `H` is set
    aside, and "CRP: Negative" carries its *result* in the same position --
    so each reading is attempted independently and the whole line is always
    kept as a fallback. The range is popped from whichever reading is used,
    which is why "8.2 g/dL (12-16) L" still finds both.
    """
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
    # looks like a marker but turns out to be the result is only understood
    # this way.
    candidates.append((line, None))
    return candidates


def _token_is_unit(line: str, token: str) -> bool:
    """True when the trailing token is better read as the line's unit.

    "Urine volume 2 L" is a volume of two litres; "Systolic 140 high" is a
    reading the document has already called high. One or two characters are
    plausible units, so a short token that completes the row as its unit wins;
    a longer word is a marker the document printed after the value.
    """
    match = _LAB_LINE.match(line)
    if not match:
        return False
    unit = (match.group("unit") or "").strip()
    if unit.upper() != token.upper():
        return False
    return len(token) <= 2


def _pop_trailing_range(text: str) -> tuple[str, Optional[str]]:
    """Remove a printed reference range from the end of a lab row.

    Returns the remaining text and the range with whitespace and dash glyphs
    normalised, so the same printed range always yields the same stored
    string. The numbers themselves are never reformatted.
    """
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
    """Read one already-trimmed fragment as a laboratory row.

    The rule that keeps this honest: the tail must be *fully accounted for*.
    A number followed by something that is not a unit means the fragment is
    not a lab row -- so it is refused rather than parsed with the fragment
    dropped. That is what stops "Date of birth: 1988-03-14" from becoming a
    measurement of 1988 with the rest quietly discarded.
    """
    match = _LAB_LINE.match(text)
    if match:
        name = (match.group("name") or "").strip()
        value = (match.group("value") or "").strip()
        unit = (match.group("unit") or "").strip()

        if unit and not _UNIT_SHAPE.match(unit):
            return None
        if not value or len(value) > MAX_VALUE_CHARS:
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
    if name.lower() in _LAB_NAME_STOPWORDS:
        return False
    # The *first* word is what identifies the test. A row whose name opens with
    # "Page", "Age" or "Date" is describing the form, not the patient, and the
    # words after it ("2 of", "of birth") must not rescue it: "Page 2 of 5"
    # otherwise parses as a measurement of 5 called "Page 2 of".
    if name.split()[0].lower() in _LAB_NAME_STOPWORDS:
        return False
    if _LAB_NAME_FORBIDDEN.search(name):
        return False
    if _LAB_NAME_VERBISH.search(name):
        return False
    if not re.search(r"[A-Za-z]", name):
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
    """One `lab_values` entry, in the shape the model declares.

    `reference_range` and `flag` are transcribed, never derived. `flag` is
    absent -- not `None` -- when the document printed no marker, because there
    is no finding to report rather than a finding of "nothing".
    """
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
    """`12.0 - 15.0` -> `12.0-15.0`.

    Whitespace and the dash glyph are unified so the same printed range always
    yields the same stored string. The numbers themselves are untouched --
    rounding or reformatting a reference range would alter what the document
    said the normal values are.
    """
    collapsed = re.sub(r"\s*[-–—]\s*", "-", raw.strip())
    collapsed = re.sub(r"\s+", "", collapsed)
    return collapsed[:MAX_VALUE_CHARS]


# ======================================================================
# medications
# ======================================================================
# Only what the document states. No drug knowledge is consulted: this module
# cannot recognise a medication it does not see named, and it makes no
# judgement about whether a named one is appropriate, current, or interacting.

_MEDICATION_PREFIX = re.compile(
    r"""^\s*
    (?:[-*\u2022]+\s*|\d{1,2}[.)]\s*|\([a-z]\)\s*)*           # bullet / numbering
    (?:(?:take|taken|takes|use|used|using|start|started|starting|continue|
         continued|continuing|apply|applied|inject|injected|give|given|
         prescribe|prescribed|add|added|oral|orally|topical|daily|bd|od)\s+)*
    (?:(?:tab|tabs|tablet|tablets|cap|capsule|capsules|syp|syrup|inj|injection|
         drops|oint|ointment|cream|lotion|susp|suspension|patch|suppository)\.?\s+)*
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
    """Medications the document names, plus the line numbers they claimed.

    Returns the line indexes as well because a prescription line must not also
    be counted as a laboratory measurement -- see `_extract_lab_values`.
    """
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
    # an open-ended run of words instead would make "Metformin twice daily" a
    # medication *called* "Metformin twice daily" -- the frequency absorbed
    # into the name, and the record's own phrasing lost.
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
    # signals that this is a prescription. Without any of them, any capitalised
    # word would become a medication -- "Take paracetamol" as advice prose, the
    # first word of a heading, a facility name in a sentence.
    if not (prefix and prefix.group(0).strip()) and not frequency_match:
        # A dose on its own is not enough. "Glucose 126 mg/dL" has one, and
        # without this check every laboratory row in the document would also be
        # recorded as a prescription of itself. A line qualifies only when the
        # document also says *how or in what form* the thing is given, which
        # is exactly what a prescription line has and a lab row does not.
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
        # abbreviation into words would be adding information the document
        # did not give.
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
#
#   1. A sentence containing an explicit abnormal marker.
#   2. A sentence sitting under a heading that labels it as a finding.
#
# There is deliberately no third. "Chest X-ray shows consolidation" in
# arbitrary prose is not captured, because deciding that consolidation is
# abnormal is a clinical judgement this layer is not allowed to make. Printed
# under "Findings:", where the document has already made that judgement, it
# is captured as a quote.

# Markers that mean the same thing wherever they appear in a sentence.
_UNAMBIGUOUS_MARKERS = (
    "abnormal", "elevated", "raised", "increased", "decreased", "reduced",
    "positive", "critical", "panic value",
    "out of range", "outside the normal range", "below range", "above range",
)

# "negative" is excluded on purpose. In a lab or a radiology report it is
# overwhelmingly a statement of normality -- "no focal consolidation, all
# negative" -- and treating it as abnormal would invert the document's meaning.
# As a *result value* it is still recorded, in `lab_values`.

# "high" and "low" need more than a bare word match, because "low back pain"
# and "high density lesion" are not abnormal-result statements. They count when
# they read as a description of a measurement.
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
    """An exact match for a known section heading on a line of its own.

    The labels are closed sets, so the alternation is built from them and
    sorted longest-first at import. That matters more than it looks: a generic
    `^[A-Za-z0-9 ]{1,40}$` heading pattern also matches "Type 2 Diabetes
    Mellitus", and treating *that* as a heading silently discards the one line
    of the section anyone wanted to read. Only a label this module already
    knows can open a section.
    """
    alternation = "|".join(
        re.escape(label)
        for label in sorted(labels, key=lambda label: (-len(label), label))
    )
    return re.compile(rf"^(?:{alternation})\s*[:.\-]?\s*$", re.IGNORECASE)


# Built from the closed label set. The condition-heading pattern is built
# below, once `_CONDITION_SECTION_LABELS` is declared.
_FINDINGS_HEADING = _heading_pattern(FINDINGS_SECTION_LABELS)

# "Impression: No acute abnormality." -- the label and its content share a
# line. Kept separate from `_FINDINGS_HEADING`, which is only a heading.
#
# The separator is a colon and the label may not contain a hyphen, because a
# hyphen is a word character here: "Chest X-ray shows consolidation" must not
# split into the label "Chest X-" and the body "ray shows consolidation".
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
            # Without this, a document that opens "Findings:" near the top would
            # keep every following line -- prescriptions, history, footer --
            # classified as findings.
            in_findings_section = False

        # A label with its content on the same line -- "Impression: ..." --
        # states the finding just as explicitly as the two-line form. Only a
        # recognised findings label splits the line; anything else keeps its
        # full text, so "ECG: Abnormal." is quoted whole rather than as a bare
        # "Abnormal." with the subject missing.
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
                # abnormal finding would be a false claim in the other
                # direction, which is just as wrong.
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
# normal is not recorded as an abnormal finding, including when it sits under
# a `Findings:` heading -- "Impression: No acute abnormality detected." is a
# real report, and recording it as an abnormality would invert it.
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
# path from a lab value, a medication, or a finding to a condition name: the
# patterns all require an explicit statement phrase, so "Glucose: 126 mg/dL"
# cannot produce "diabetes" no matter what else is on the page.

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
# heading begins -- otherwise "Findings: …" would swallow the entire rest of a
# document, including the prescriptions and history printed after it.
# Headings that *close* a section. A closed set, so an unrecognised layout still
# reads as continuous rather than being silently truncated -- the safer error,
# because a captured line is quoted verbatim and labelled with where it came
# from, while a dropped one is simply gone.
#
# These are the document-structure headings that follow a findings or history
# block in practice. "Medications:" is the one that matters: without it, a
# prescription line printed after a findings block would be filed as a finding.
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
# conditions" is a statement about the absence of conditions, and recording
# "chronic conditions" from it would invert the document's meaning.
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
        # statement patterns below would happily capture the words after
        # "known", so the negation is checked first and the whole line skipped.
        if _CONDITION_NEGATION.search(line):
            continue

        if _CONDITION_HEADING.match(line):
            # The heading is a label, not a condition. "Medical history:" opens
            # a section, and reading the label itself as its first entry would
            # record the word "history" as though the patient had it.
            #
            # A line that carries both is not a heading and falls through
            # normally: "Diagnosis: asthma" has content after the colon, so the
            # heading pattern never matches it and it is read as a statement.
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