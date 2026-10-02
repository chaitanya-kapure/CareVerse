"""Deterministic structured extraction of explicitly stated medical facts.

Most of this file is about what the extractor must *refuse* to do. A parser
that quietly invents a condition, or marks a value abnormal because it
disagreed with a reference range, would be worse than one that returns nothing
-- so the negative cases below carry as much weight as the positive ones.

These are unit tests over `extract_structured` and need no database, no PDF,
and no network. The pipeline tests at the end cover the upload path and reuse
the existing fixtures.

No real medical document is committed to this repository. Every string here is
synthetic and exists only to make a parsing rule observable.
"""

import pytest

from app.models.medical_document import ExtractedData
from app.services import structured_extraction as sx
from app.services.structured_extraction import extract_structured
from tests.pdf_fixtures import blank_pdf, corrupt_pdf, text_pdf

# ======================================================================
# helpers
# ======================================================================


def only(section: str, result: ExtractedData) -> list:
    """The one list in a result, asserting nothing else was invented."""
    others = set(result) - {section}
    assert others == set(), f"unexpected extra sections: {sorted(others)}"
    return result[section]


def all_facts(result: ExtractedData) -> list[dict]:
    """Every fact in a result, across all four list sections."""
    facts = []
    for section in ("lab_values", "medications", "abnormal_findings", "stated_conditions"):
        facts.extend(result.get(section, []))
    return facts


def find_named(result: ExtractedData, name: str) -> dict:
    matches = [item for item in result.get("lab_values", []) if item["name"] == name]
    assert matches, f"no lab value named {name!r} in {result.get('lab_values')}"
    return matches[0]


# ======================================================================
# 1. empty and non-text input
# ======================================================================


@pytest.mark.parametrize("text", ["", "   ", "\n\n\n", "\t"])
def test_empty_text_yields_an_empty_structure(text):
    assert extract_structured(text) == {}


def test_whitespace_only_document_has_no_facts_and_no_error():
    result = extract_structured("   \n \n  \n")
    assert result == {}
    assert all_facts(result) == []


def test_text_with_nothing_extractable_is_an_empty_dict_not_a_guess():
    """A readable document that states nothing parseable yields `{}`.

    This is the documented representation for "nothing found" -- absent, not
    present-and-null -- and it is what lets a later summary say "not found in
    the uploaded records" instead of having to tell empty from unknown.
    """
    assert extract_structured("Dear Mr Smith, thank you for your visit.") == {}


def test_a_field_the_document_does_not_state_is_absent_not_null():
    result = extract_structured("Glucose 126 mg/dL")
    assert "reference_range" not in result["lab_values"][0]
    assert "flag" not in result["lab_values"][0]
    assert "document_date" not in result


# ======================================================================
# 2. laboratory values
# ======================================================================


def test_single_lab_value_is_extracted_with_its_source():
    result = extract_structured("Glucose: 126 mg/dL")
    values = only("lab_values", result)

    assert values == [
        {
            "name": "Glucose",
            "value": "126",
            "unit": "mg/dL",
            "source_text": "Glucose: 126 mg/dL",
        }
    ]


def test_lab_value_with_a_reference_range_keeps_every_part():
    result = extract_structured("Haemoglobin: 13.2 g/dL (12-16)")
    entry = find_named(result, "Haemoglobin")

    assert entry["name"] == "Haemoglobin"
    assert entry["value"] == "13.2"
    assert entry["unit"] == "g/dL"
    assert entry["reference_range"] == "12-16"
    assert entry["source_text"] == "Haemoglobin: 13.2 g/dL (12-16)"


def test_reference_range_spacing_and_dashes_are_normalised_but_unchanged():
    """`12.0 - 15.0` and `12.0-15.0` are the same printed range."""
    spaced = extract_structured("Haemoglobin 13.2 g/dL (12.0 - 15.0)")
    tight = extract_structured("Haemoglobin 13.2 g/dL (12.0-15.0)")

    assert find_named(spaced, "Haemoglobin")["reference_range"] == "12.0-15.0"
    assert find_named(tight, "Haemoglobin")["reference_range"] == "12.0-15.0"


def test_a_labelled_reference_range_is_read_too():
    result = extract_structured("Glucose 126 mg/dL Ref: 70-110")
    assert find_named(result, "Glucose")["reference_range"] == "70-110"


def test_several_lab_values_keep_document_order():
    text = "TSH 4.5 mIU/L\nHaemoglobin 14.2 g/dL\nPlatelets 250000 /uL"
    names = [item["name"] for item in extract_structured(text)["lab_values"]]

    assert names == ["TSH", "Haemoglobin", "Platelets"]


def test_qualitative_results_are_recorded_as_stated_values():
    """`CRP: Negative` is a result the document stated, so it is recorded.

    It is recorded as the *value*, not as a finding saying "abnormal": the
    whole point of the closed word list is that a negative result stays
    negative.
    """
    result = extract_structured("CRP: Negative")
    entry = only("lab_values", result)[0]

    assert entry["name"] == "CRP"
    assert entry["value"] == "Negative"
    assert "flag" not in entry
    assert entry["source_text"] == "CRP: Negative"


def test_demographic_lines_are_not_lab_values():
    """`Age 45 years` is a fact about the form, not an observation."""
    assert extract_structured("Age 45 years") == {}
    assert extract_structured("Date of birth: 1988-03-14") == {}
    assert extract_structured("Page 2 of 5") == {}


def test_a_line_whose_tail_is_not_a_unit_is_not_a_lab_row():
    """The tail must be fully accounted for, or the row is refused.

    This is what stops `Date of birth: 1988-03-14` being read as a
    measurement of 1988 with the rest of the date quietly dropped.
    """
    result = extract_structured("Date of birth: 1988-03-14")
    assert "lab_values" not in result


# ======================================================================
# 3. lab flags -- transcribed, never computed
# ======================================================================


@pytest.mark.parametrize(
    "text,name,flag",
    [
        ("Glucose 126 mg/dL H", "Glucose", "high"),
        ("Glucose 126 mg/dL L", "Glucose", "low"),
        ("Haemoglobin 8.2 g/dL (12-16) L", "Haemoglobin", "low"),
        ("Glucose 126 mg/dL *", "Glucose", "abnormal"),
        ("Glucose 126 mg/dL Elevated", "Glucose", "high"),
        ("Glucose 126 mg/dL (High)", "Glucose", "high"),
        ("Potassium 6.2 mmol/L Critical", "Potassium", "critical"),
    ],
)
def test_a_flag_comes_from_a_marker_the_document_printed(text, name, flag):
    result = extract_structured(text)
    assert find_named(result, name)["flag"] == flag
    assert result["lab_values"][0]["source_text"] == text


def test_no_flag_is_inferred_from_a_value_outside_its_reference_range():
    """8.2 against a stated 12-16 is flagged `low` ONLY because the document
    printed an `L`. The same numbers with no marker must carry no flag.

    Comparing a value against a range is an interpretation. This extractor
    transcribes markers and does not compute them, so a normal-looking pair
    produces no clinical claim at all.
    """
    unmarked = extract_structured("Haemoglobin 8.2 g/dL (12-16)")
    assert "flag" not in find_named(unmarked, "Haemoglobin")

    marked = extract_structured("Haemoglobin 8.2 g/dL (12-16) L")
    assert find_named(marked, "Haemoglobin")["flag"] == "low"


def test_a_value_inside_its_range_is_not_flagged_normal_either():
    """A normal-looking value is not marked `normal`.

    Silence is the honest answer: there is no finding to report, and a
    `normal` flag on every in-range value would be a claim the document never
    made.
    """
    result = extract_structured("Haemoglobin 14.2 g/dL (12-16)")
    assert "flag" not in find_named(result, "Haemoglobin")


def test_a_single_letter_that_is_a_unit_is_not_read_as_a_flag():
    """`2 L` is two litres, not a low marker."""
    result = extract_structured("Urine volume 2 L")
    entry = only("lab_values", result)[0]

    assert entry["value"] == "2"
    assert entry["unit"] == "L"
    assert "flag" not in entry


# ======================================================================
# 4. no clinical inference
# ======================================================================


def test_a_glucose_value_never_produces_a_condition():
    """The prohibited conversion, stated as a test.

    `Glucose: 126 mg/dL` must not become "diabetes". Every condition pattern
    requires an explicit statement phrase, so no lab line can reach one.
    """
    result = extract_structured("Glucose: 126 mg/dL")

    assert "stated_conditions" not in result
    haystack = str(result).lower()
    for forbidden in ("diabet", "hypertension", "prediabet", "hyperglyc"):
        assert forbidden not in haystack, f"invented {forbidden!r} from a lab value"


def test_no_condition_is_inferred_from_medications_either():
    result = extract_structured("Metformin 500 mg twice daily")

    assert "stated_conditions" not in result
    assert "diabet" not in str(result).lower()


def test_no_condition_is_inferred_from_a_finding():
    result = extract_structured("Findings:\nConsolidation in the right lower zone.")
    assert "stated_conditions" not in result


@pytest.mark.parametrize(
    "text",
    [
        "Glucose: 126 mg/dL",
        "Haemoglobin 8.2 g/dL (12-16) L",
        "Metformin 500 mg twice daily",
        "Blood pressure was elevated.",
    ],
)
def test_no_diagnosis_language_ever_appears_in_the_output(text):
    """Belt and braces over the whole extractor, not just one category."""
    result = extract_structured(text)
    haystack = str(result).lower()

    for forbidden in (
        "diagnos", "you have", "the patient has", "suffering from",
        "should take", "recommended", "prescribe", "treatment",
    ):
        assert forbidden not in haystack, f"{forbidden!r} appeared for input {text!r}"


# ======================================================================
# 5. medications
# ======================================================================


def test_medication_with_dose_and_frequency():
    result = extract_structured("Metformin 500 mg twice daily")
    entries = only("medications", result)

    assert entries == [
        {
            "name": "Metformin",
            "dosage": "500 mg",
            "frequency": "twice daily",
            "source_text": "Metformin 500 mg twice daily",
        }
    ]


def test_medication_with_as_needed_frequency():
    result = extract_structured("Paracetamol 650 mg as needed")
    entry = only("medications", result)[0]

    assert entry["name"] == "Paracetamol"
    assert entry["dosage"] == "650 mg"
    assert entry["frequency"] == "as needed"


def test_a_dosage_form_prefix_is_consumed_not_recorded_as_the_name():
    result = extract_structured("Tab. Metformin 500 mg BD")
    entry = only("medications", result)[0]

    assert entry["name"] == "Metformin"
    assert entry["dosage"] == "500 mg"
    # The document wrote "BD". It is kept verbatim rather than expanded into
    # "twice daily", which would be adding words the record does not contain.
    assert entry["frequency"] == "BD"


def test_a_missing_dosage_or_frequency_is_not_invented():
    """A name the document gave, with nothing else stated about it.

    The line does carry a frequency, so it qualifies -- but the dosage was
    never printed and must not be filled in from a default.
    """
    result = extract_structured("Metformin twice daily")
    entry = only("medications", result)[0]

    assert entry["name"] == "Metformin"
    assert entry["frequency"] == "twice daily"
    assert "dosage" not in entry


def test_numbered_prescription_lines_are_read():
    text = "Medications:\n1. Metformin 500 mg twice daily\n2. Aspirin 75 mg OD"
    names = [item["name"] for item in extract_structured(text)["medications"]]

    assert names == ["Metformin", "Aspirin"]


def test_a_lab_row_is_never_also_recorded_as_a_prescription():
    """A dose alone does not make a medication.

    `Glucose 126 mg/dL` contains "126 mg", which is the shape of a dosage.
    Without the frequency or the dosage form that distinguishes a prescription
    from a measurement, every lab row in the document would also be recorded as
    a prescription of itself.
    """
    result = extract_structured("Glucose: 126 mg/dL")

    assert "medications" not in result
    assert find_named(result, "Glucose")["value"] == "126"


def test_a_prescription_line_is_not_also_recorded_as_a_lab_value():
    result = extract_structured("Metformin 500 mg twice daily")
    assert "lab_values" not in result


# ======================================================================
# 6. stated conditions
# ======================================================================


@pytest.mark.parametrize(
    "text,expected",
    [
        ("History of hypertension.", "hypertension"),
        ("Known diabetes mellitus.", "diabetes mellitus"),
        ("Diagnosis: asthma.", "asthma"),
        ("Past medical history: Diabetes, Hypertension", "Diabetes, Hypertension"),
        ("Suffering from chronic kidney disease.", "chronic kidney disease"),
    ],
)
def test_explicitly_stated_conditions_are_extracted(text, expected):
    result = extract_structured(text)
    entries = only("stated_conditions", result)

    assert entries[0]["text"] == expected
    assert entries[0]["source_text"] == text


@pytest.mark.parametrize(
    "text",
    [
        "History: None",
        "Past medical history: nil",
        "History of: unknown",
        "Patient has no known chronic conditions.",
    ],
)
def test_a_denial_of_conditions_is_not_recorded_as_one(text):
    """`No known chronic conditions` states an absence.

    The statement patterns would otherwise capture the words after "known" and
    record "chronic conditions" as though the patient had them.
    """
    assert extract_structured(text) == {}


def test_a_condition_heading_on_its_own_line_takes_the_next_line():
    result = extract_structured("Medical history:\nType 2 Diabetes Mellitus")
    assert "diabetes" in result["stated_conditions"][0]["text"].lower()


# ======================================================================
# 7. abnormal findings
# ======================================================================


def test_explicit_abnormal_marker_is_captured():
    result = extract_structured("ECG: Abnormal.")
    entries = only("abnormal_findings", result)

    assert entries == [
        {
            "text": "ECG: Abnormal.",
            "marker": "abnormal",
            "source_text": "ECG: Abnormal.",
        }
    ]


@pytest.mark.parametrize(
    "text,marker",
    [
        ("Blood pressure was elevated.", "elevated"),
        ("Liver enzymes are raised.", "raised"),
        ("Platelet count decreased over the admission.", "decreased"),
        ("Urine protein was positive on dipstick.", "positive"),
        ("Potassium is low.", "low"),
        ("Blood pressure is high.", "high"),
    ],
)
def test_the_approved_marker_vocabulary(text, marker):
    entries = extract_structured(text)["abnormal_findings"]
    assert entries[0]["marker"] == marker
    assert entries[0]["text"] == text


def test_a_findings_section_captures_the_sentence_under_it():
    text = "Findings:\nChest X-ray shows consolidation."
    entries = only("abnormal_findings", extract_structured(text))

    assert entries == [
        {
            "text": "Chest X-ray shows consolidation.",
            "marker": "stated_in_findings_section",
            "source_text": "Chest X-ray shows consolidation.",
        }
    ]


def test_a_findings_section_stops_at_the_next_heading():
    text = "Findings:\nConsolidation in the right lower zone.\nMedications:\nMetformin 500 mg twice daily"
    result = extract_structured(text)

    assert len(result["abnormal_findings"]) == 1
    assert "medications" in result


def test_the_same_sentence_without_a_section_or_marker_is_not_a_finding():
    """The negative case the whole design turns on.

    Deciding that "consolidation" is abnormal is a clinical judgement this
    layer is not allowed to make. Printed under `Findings:`, where the
    document has already made that judgement, it is captured; in arbitrary
    prose it is not.
    """
    assert extract_structured("Chest X-ray shows consolidation.") == {}


@pytest.mark.parametrize(
    "text",
    [
        "Impression: No acute abnormality detected.",
        "Comment: No significant abnormality.",
        "Findings:\nNo focal consolidation or pneumothorax.",
    ],
)
def test_a_statement_of_normality_is_not_recorded_as_a_finding(text):
    assert "abnormal_findings" not in extract_structured(text)


def test_negative_is_not_treated_as_an_abnormal_marker():
    """`All negative` is a statement of normality in a radiology report."""
    result = extract_structured("No consolidation, effusion or pneumothorax. All negative.")
    assert "abnormal_findings" not in result


# ======================================================================
# 8. metadata
# ======================================================================


def test_labelled_metadata_is_read():
    text = (
        "Report: Complete Blood Count\n"
        "Report Date: 2025-11-02\n"
        "Hospital: City General Hospital\n"
        "Referring Doctor: Dr A Sharma"
    )
    result = extract_structured(text)

    assert result["report_title"] == "Complete Blood Count"
    assert result["document_date"] == "2025-11-02"
    assert result["referring_facility"] == "City General Hospital"
    assert result["referring_doctor"] == "Dr A Sharma"


def test_an_unlabelled_heading_is_not_promoted_to_a_title():
    """The first line is a letterhead on one document and a name on another.

    Guessing which is exactly the inference this layer must not make, so an
    unlabelled heading is left alone.
    """
    assert "report_title" not in extract_structured("City General Hospital\nComplete Blood Count")


def test_an_address_is_not_promoted_to_a_facility():
    result = extract_structured("Address: 14 Station Road, Pune 411001")
    assert "referring_facility" not in result


def test_an_arbitrary_name_is_not_promoted_to_a_doctor():
    result = extract_structured("Patient name: Rehana Khan\nAge: 38")
    assert "referring_doctor" not in result


def test_placeholder_metadata_values_are_refused():
    result = extract_structured("Hospital: N/A\nReferring Doctor: -")
    assert "referring_facility" not in result
    assert "referring_doctor" not in result


def test_only_an_explicitly_labelled_date_is_the_document_date():
    """A date with no label could be anything printed on the page."""
    assert "document_date" not in extract_structured("Next appointment 2025-11-02")


def test_an_iso_date_is_read():
    assert extract_structured("Report Date: 2025-11-02")["document_date"] == "2025-11-02"


def test_an_unambiguous_slash_date_is_read():
    """25 cannot be a month, so the ordering is proven rather than assumed."""
    assert extract_structured("Report Date: 25/11/2025")["document_date"] == "2025-11-25"


def test_an_ambiguous_slash_date_is_refused():
    """`03/04/2025` is either 3 April or 4 March.

    Refusing is the only honest answer: a summary cannot later walk back a
    date it committed to as a confident ISO string.
    """
    assert "document_date" not in extract_structured("Report Date: 03/04/2025")


def test_a_date_of_birth_is_never_the_document_date():
    assert "document_date" not in extract_structured("Date of birth: 1988-03-14")


def test_a_date_that_is_not_a_real_calendar_date_is_refused():
    """`2026-02-30` is not rolled over into March."""
    assert "document_date" not in extract_structured("Report Date: 2026-02-30")


# ======================================================================
# 9. source attribution
# ======================================================================


@pytest.mark.parametrize(
    "text",
    [
        "Glucose: 126 mg/dL",
        "Haemoglobin: 13.2 g/dL (12-16) L",
        "Metformin 500 mg twice daily",
        "History of hypertension.",
        "ECG: Abnormal.",
        "Findings:\nChest X-ray shows consolidation.",
        "Past medical history: Diabetes\nFindings:\nLiver enzymes raised\n"
        "Metformin 500 mg twice daily",
    ],
)
def test_every_fact_carries_verbatim_source_text(text):
    """The property Phase 4B depends on entirely.

    A fact that cannot be traced back to the line it came from cannot be
    verified against the original document, so this asserts the whole output
    rather than a sample.
    """
    result = extract_structured(text)
    facts = all_facts(result)

    assert facts, "expected the sample text to produce at least one fact"
    for fact in facts:
        assert fact.get("source_text"), f"fact without source_text: {fact}"
        assert fact["source_text"] in text, (
            f"source_text is not a verbatim substring of the document: "
            f"{fact['source_text']!r}"
        )


# ======================================================================
# 10. determinism
# ======================================================================


def test_the_same_text_always_produces_the_same_structure():
    text = (
        "Report: Complete Blood Count\n"
        "Report Date: 2025-11-02\n"
        "Haemoglobin 14.2 g/dL\n"
        "Metformin 500 mg twice daily\n"
        "History of hypertension.\n"
        "Findings:\nChest X-ray shows consolidation.\n"
    )

    results = [extract_structured(text) for _ in range(25)]
    first = results[0]

    for other in results[1:]:
        assert other == first, "structured extraction is not deterministic"


def test_determinism_holds_for_a_long_repeated_document():
    text = ("Haemoglobin 14.2 g/dL\nMetformin 500 mg twice daily\n" * 500)
    assert extract_structured(text) == extract_structured(text)


def test_key_insertion_order_is_stable():
    """A dict equal to a dict is not enough -- order must be reproducible too.

    A summary that renders sections in a different order on each request would
    look unstable to a reader and would make snapshots useless.
    """
    text = "Glucose 126 mg/dL\nHistory of hypertension.\nECG: Abnormal."
    keys = [list(extract_structured(text)) for _ in range(10)]

    assert all(entry == keys[0] for entry in keys)


# ======================================================================
# 11. bounds
# ======================================================================


def test_output_is_capped_per_category():
    """A pathological document cannot produce an unbounded structure."""
    text = "".join(f"Test{i} {i} mg/dL\n" for i in range(5000))
    assert len(extract_structured(text)["lab_values"]) == sx.MAX_LAB_VALUES

    text = "".join(f"History of condition{i}.\n" for i in range(5000))
    assert len(extract_structured(text)["stated_conditions"]) == sx.MAX_STATED_CONDITIONS


def test_a_repeated_row_is_recorded_once():
    """A header table repeating a body row must not double-count it."""
    text = "Haemoglobin 14.2 g/dL\n" * 50
    assert len(extract_structured(text)["lab_values"]) == 1


def test_input_longer_than_the_cap_is_truncated_not_refused():
    """A huge document is read up to the cap rather than refused.

    Refusing outright would lose the extractable beginning of a long record;
    the cap bounds the work, and the document is still summarised as far as
    it goes.
    """
    padding = "filler line with no parseable content\n" * 40000
    result = extract_structured("Glucose 126 mg/dL\n" + padding)

    assert find_named(result, "Glucose")["value"] == "126"


def test_an_over_long_line_is_skipped_rather_than_quoted():
    """`source_text` must be verbatim, so a clipped quote is not a quote.

    The line is skipped rather than truncated: a source that stops
    mid-sentence is worse than no source.
    """
    line = "Glucose " + "9" * sx.MAX_SOURCE_TEXT_CHARS
    assert extract_structured(line) == {}


def test_source_text_never_exceeds_the_cap():
    text = "Findings:\n" + ("word " * 200).strip()
    for fact in all_facts(extract_structured(text)):
        assert len(fact["source_text"]) <= sx.MAX_SOURCE_TEXT_CHARS


# ======================================================================
# 12. exception safety
# ======================================================================


def test_non_string_input_is_refused_rather_than_raising():
    assert extract_structured(None) == {}
    assert extract_structured(123) == {}
    assert extract_structured(["Glucose 126 mg/dL"]) == {}


def test_one_failing_category_does_not_discard_the_others(monkeypatch):
    """A parser bug must not cost every category its results."""

    def explode(_lines):
        raise RuntimeError("simulated parser failure")

    monkeypatch.setattr(sx, "_extract_lab_values", explode)

    result = extract_structured("History of hypertension.\nECG: Abnormal.")

    assert "lab_values" not in result
    assert result["stated_conditions"]
    assert result["abnormal_findings"]


def test_the_public_entry_point_never_raises(monkeypatch):
    """Even a total failure degrades to `{}` and leaves the text intact.

    This is the contract the upload path depends on: a document that
    extracted its text must not fail to upload because the structured pass
    could not read it.
    """

    def explode(_text):
        raise RuntimeError("simulated catastrophic failure")

    monkeypatch.setattr(sx, "_readable_lines", explode)
    assert extract_structured("Glucose 126 mg/dL") == {}


# ======================================================================
# 13. the document pipeline
# ======================================================================

LAB_REPORT = "Complete Blood Count\nHaemoglobin 14.2 g/dL\nPlatelets 250000 /uL"


def upload(client, headers, content, filename="report.pdf"):
    return client.post(
        "/patients/me/documents",
        files={"file": (filename, content, "application/pdf")},
        headers=headers,
    )


def test_an_uploaded_pdf_receives_populated_extracted_data(client, patient):
    response = upload(client, patient["headers"], text_pdf(LAB_REPORT))

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["extraction_status"] == "completed"
    assert "extracted_text" in body
    assert [item["name"] for item in body["extracted_data"]["lab_values"]] == [
        "Haemoglobin",
        "Platelets",
    ]
    assert body["extracted_data"]["lab_values"][0]["source_text"] == "Haemoglobin 14.2 g/dL"


def test_a_scanned_document_gets_no_structured_data(client, patient):
    """`needs_ocr` means there was no text to read, so nothing is built.

    Preserving the status and leaving `extracted_data` empty is what lets a
    later summary tell "no facts found" apart from "this record was never
    readable" -- and it is why the structured pass cannot run here.
    """
    response = upload(client, patient["headers"], blank_pdf())

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["extraction_status"] == "needs_ocr"
    assert body["extracted_text"] is None
    assert body["extracted_data"] == {}


def test_a_failed_extraction_gets_no_structured_data(client, patient):
    """`failed` means the file could not be read at all.

    No facts are manufactured from a filename or a category label: the
    document keeps its failure state and nothing else changes.
    """
    response = upload(client, patient["headers"], corrupt_pdf(), filename="broken.pdf")

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["extraction_status"] == "failed"
    assert body["extracted_data"] == {}
    assert body["extracted_text"] is None


def test_structured_extraction_never_overrides_the_patients_document_date(
    client, patient
):
    """A typed date is the document's date of record.

    `extracted_data.document_date` is a separate reading of what the file
    says. Both are recorded; the patient's own date is not replaced by a date
    the parser found.
    """
    content = text_pdf("Report Date: 2020-01-01\nHaemoglobin 14.2 g/dL")

    response = client.post(
        "/patients/me/documents",
        files={"file": ("cbc.pdf", content, "application/pdf")},
        data={"document_date": "2026-06-01"},
        headers=patient["headers"],
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["document_date"] == "2026-06-01"
    assert body["extracted_data"]["document_date"] == "2020-01-01"


def test_stored_document_keeps_its_structured_data(client, patient, db):
    response = upload(client, patient["headers"], text_pdf(LAB_REPORT))
    document_id = response.json()["id"]

    stored = db.medical_documents.find_one({"patient_id": patient["id"]})
    assert stored["extracted_data"]["lab_values"][0]["value"] == "14.2"

    detail = client.get(
        f"/patients/me/documents/{document_id}", headers=patient["headers"]
    )
    assert detail.json()["extracted_data"] == stored["extracted_data"]


def test_extraction_stays_inside_the_existing_page_and_size_limits(
    client, patient
):
    """The structured pass does not widen any Phase 2 bound.

    A document refused for having too many pages is refused for exactly the
    same reason in Phase 4A, and never reaches the structured pass at all.
    """
    from tests.pdf_fixtures import oversized_pdf

    response = upload(client, patient["headers"], oversized_pdf(), filename="big.pdf")
    assert response.status_code == 413, response.text

    response = upload(client, patient["headers"], text_pdf(LAB_REPORT))
    assert response.status_code == 201
    assert response.json()["page_count"] == 1


def test_a_doctor_sees_the_same_structured_data_as_the_patient(client, patient, doctor):
    """One extraction, two authorised readers.

    The structured pass runs at upload, so a doctor's read of the record is
    the same stored structure the patient sees rather than a second, possibly
    different, parse of the same file.
    """
    upload(client, patient["headers"], text_pdf(LAB_REPORT), filename="cbc.pdf")
    document_id = _first_document_id(client, patient["headers"])

    created = client.post(
        "/patients/me/access",
        json={"doctor_id": doctor["id"]},
        headers=patient["headers"],
    )
    assert created.status_code == 201, created.text

    detail = client.get(
        f"/doctor/patients/{patient['id']}/documents/{document_id}",
        headers=doctor["headers"],
    )

    assert detail.status_code == 200, detail.text
    own = client.get(
        f"/patients/me/documents/{document_id}", headers=patient["headers"]
    )
    assert detail.json()["extracted_data"] == own.json()["extracted_data"]


def _first_document_id(client, headers) -> str:
    listing = client.get("/patients/me/documents", headers=headers)
    return listing.json()["items"][0]["id"]