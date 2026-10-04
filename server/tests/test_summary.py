"""The patient summary pipeline, exercised through the HTTP API.

Ordered by risk rather than by feature. The questions that matter most here
are not "does the summary render" -- they are, in order:

  * can a caller who is not authorized reach a patient's summary at all;
  * can a claim in that summary be traced to a record belonging to the same
    patient;
  * can a summary say something a document did not say.

Everything else in this file is subordinate to those three.

Like `test_doctor_access.py`, every case here is a real HTTP request with a
hand-built URL. The Phase 4B threat model is a doctor pointing the summary
route at somebody else's patient id, and a frontend that renders a button is
not what stops that.

The suite is not safe to run concurrently with itself: every test in the
repository shares the `careverse_test` database, and two pytest processes
wiping it at the same time produce failures that look like application bugs.
"""

import dataclasses

import pytest
from bson import ObjectId

from app.config import AI_SUMMARY_DISCLAIMER, settings
from app.services import summary_service
from app.services.summary_service import (
    EMPTY_SECTION_NOTE,
    MAX_ITEMS_PER_SECTION,
    MOCK_PROVIDER,
    SUMMARY_SECTIONS,
    MockSummaryProvider,
    ProviderSection,
    SummaryDraft,
    SummaryItem,
    SummaryProviderUnavailable,
    get_summary_provider,
)
from tests.pdf_fixtures import blank_pdf, corrupt_pdf, text_pdf

# A record with real structure: metadata lines, two lab rows, a medication and
# an explicitly stated condition. Nothing here is a real patient.
RICH_REPORT = """City General Hospital
Referred by: Dr A. Okafor
Report Date: 2026-05-14

Complete Blood Count
Glucose 126 mg/dL Ref: 70-110 H
Haemoglobin 14.2 g/dL Ref: 13.0-17.0

Medications:
1. Metformin 500 mg twice daily

Diagnosis: Type 2 Diabetes Mellitus
"""

# Structure-free prose: readable, but nothing extractable is claimed.
FLAT_REPORT = "Receipt for copying fees paid at the desk on Tuesday morning."

# `Glucose 126 mg/dL` and nothing else. The single most important safety case
# in this file: a raised number on a page must never become a condition.
GLUCOSE_ONLY = "Fasting sample\nGlucose 126 mg/dL"


# =====================================================================
# helpers
# =====================================================================


def grant_access(client, patient, doctor, note=None):
    """The patient authorizes the doctor. The only supported route to access."""
    body = {"doctor_id": doctor["id"]}
    if note:
        body["note"] = note
    response = client.post(
        "/patients/me/access", json=body, headers=patient["headers"]
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, patient, text=None, *, content=None, filename="report.pdf", **fields):
    """Upload one PDF and return its id. Fails the test if it is unreadable."""
    payload = content if content is not None else text_pdf(text or RICH_REPORT)
    response = client.post(
        "/patients/me/documents",
        files={"file": (filename, payload, "application/pdf")},
        data=fields,
        headers=patient["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def set_profile(client, patient, **fields):
    response = client.patch("/patients/me", json=fields, headers=patient["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def doctor_summary(client, doctor, patient_id):
    return client.get(
        f"/doctor/patients/{patient_id}/summary", headers=doctor["headers"]
    )


def own_summary(client, patient):
    return client.get("/patients/me/summary", headers=patient["headers"])


def sections_by_key(body):
    return {section["key"]: section for section in body["sections"]}


def all_items(body):
    """Every item in every section -- the claim set, flattened."""
    return [item for section in body["sections"] for item in section["items"]]


def section_text(body, key):
    return " ".join(item["text"] for item in sections_by_key(body)[key]["items"])


def claims_text(body):
    """Every generated claim, joined for substring assertions.

    Deliberately the section items and *not* the overview: the overview ends
    with "Nothing here is a diagnosis or an interpretation.", which is the
    safety notice itself. A negative substring check has to look at what the
    system claims, not at the sentence telling the reader it claims nothing.
    """
    return " ".join(item["text"] for item in all_items(body)).lower()


def stored_summary(db, patient_id):
    return db.patient_summaries.find_one({"patient_id": patient_id})


class RecordingProvider:
    """A provider that remembers exactly what it was handed.

    Used for the privacy tests: the assertion is about the payload, so the
    payload has to be observable, and the only honest way to observe it is at
    the seam a real provider would also sit behind.
    """

    name = "custom"
    is_mock = False
    model = "recorder-v1"

    def __init__(self):
        self.payloads = []

    def generate(self, payload):
        self.payloads.append(payload)
        return MOCK_PROVIDER.generate(payload)

    @property
    def last(self):
        return self.payloads[-1]


class MarkerProvider:
    """Returns one identifiable line, to prove regeneration really happened."""

    name = "custom"
    is_mock = False
    model = "marker-v1"

    def __init__(self, marker="REGENERATED-MARKER"):
        self.marker = marker
        self.calls = 0

    def generate(self, payload):
        self.calls += 1
        first = payload.documents[0] if payload.documents else None
        if first is None:
            return SummaryDraft(overview="", sections=())
        return SummaryDraft(
            overview=f"{self.marker} overview",
            sections=(
                ProviderSection(
                    key="lab_values",
                    title="Important Lab Values",
                    items=(SummaryItem(self.marker, first.id, None),),
                ),
            ),
        )


class RogueProvider:
    """Emits claims that must never survive: untraceable and foreign.

    `name` is `"custom"` because that is the honest label: the response schema
    accepts `mock | openai | anthropic | custom`, and a provider that claims
    to be something it is not would fail at the boundary rather than teach us
    anything. What matters here is the items, not the name.
    """

    name = "custom"
    is_mock = False
    model = None

    def __init__(self, foreign_document_id, patient_document_id):
        self.foreign_document_id = foreign_document_id
        self.patient_document_id = patient_document_id

    def generate(self, payload):
        return SummaryDraft(
            overview="rogue overview",
            sections=(
                ProviderSection(
                    key="lab_values",
                    title="Important Lab Values",
                    items=(
                        # No source at all.
                        SummaryItem("unsourced claim", "", None),
                        # Points at another patient's record.
                        SummaryItem("someone else's result", self.foreign_document_id, None),
                        # Points at a document id that does not exist at all.
                        SummaryItem("invented document", "000000000000000000000000", None),
                        # A healthcare section the architecture does not define.
                        SummaryItem("extra", self.patient_document_id, None),
                    ),
                ),
                ProviderSection(
                    key="prognosis",
                    title="Prognosis",
                    items=(
                        SummaryItem("This patient is deteriorating", self.patient_document_id, None),
                    ),
                ),
            ),
        )


class FailingProvider:
    """A provider that fails the two ways a real one does."""

    name = "openai"
    is_mock = False
    model = "unreachable"

    def __init__(self, exception):
        self.exception = exception
        self.calls = 0

    def generate(self, payload):
        self.calls += 1
        raise self.exception


# =====================================================================
# A. authentication
# =====================================================================


def test_the_doctor_summary_needs_a_token(client, patient):
    response = client.get(f"/doctor/patients/{patient['id']}/summary")
    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_TOKEN"


def test_the_patient_summary_needs_a_token(client):
    response = client.get("/patients/me/summary")
    assert response.status_code == 401


def test_regenerate_needs_a_token(client, patient):
    response = client.post(f"/doctor/patients/{patient['id']}/summary/regenerate")
    assert response.status_code == 401


def test_a_bogus_token_is_refused(client, patient):
    response = client.get(
        f"/doctor/patients/{patient['id']}/summary",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


# =====================================================================
# B. role
# =====================================================================


def test_a_patient_cannot_use_the_doctor_summary_route(client, patient):
    """The path is not the authorization. A patient reading it is refused."""
    response = client.get(
        f"/doctor/patients/{patient['id']}/summary", headers=patient["headers"]
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ROLE_NOT_ALLOWED"


def test_a_patient_cannot_regenerate_a_summary(client, patient):
    response = client.post(
        f"/doctor/patients/{patient['id']}/summary/regenerate", headers=patient["headers"]
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ROLE_NOT_ALLOWED"


def test_a_doctor_cannot_use_the_patient_summary_route(client, doctor):
    """The reverse direction too: /patients/me is not "the summary route"."""
    response = client.get("/patients/me/summary", headers=doctor["headers"])
    assert response.status_code == 403
    assert response.json()["code"] == "ROLE_NOT_ALLOWED"


def test_a_patient_summary_is_not_written_while_the_call_is_refused(client, patient, db):
    """A refused request must not leave a summary behind as a side effect."""
    client.get(f"/doctor/patients/{patient['id']}/summary", headers=patient["headers"])
    assert stored_summary(db, patient["id"]) is None


# =====================================================================
# C. authorization
# =====================================================================


def test_an_authorized_doctor_reads_the_summary(client, patient, doctor, db):
    grant_access(client, patient, doctor)
    upload(client, patient)

    response = doctor_summary(client, doctor, patient["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["patient_id"] == patient["id"]
    assert body["source_document_count"] == 1
    assert stored_summary(db, patient["id"]) is not None


def test_an_unauthorized_doctor_is_refused(client, patient, doctor, db):
    upload(client, patient)

    response = doctor_summary(client, doctor, patient["id"])

    assert response.status_code == 403
    assert response.json()["code"] == "NO_PATIENT_ACCESS"
    # The refusal happens before generation, so no summary is left behind.
    assert stored_summary(db, patient["id"]) is None


def test_a_revoked_grant_stops_working(client, patient, doctor, db):
    grant = grant_access(client, patient, doctor)
    upload(client, patient)
    assert doctor_summary(client, doctor, patient["id"]).status_code == 200

    client.delete(f"/patients/me/access/{grant['id']}", headers=patient["headers"])

    response = doctor_summary(client, doctor, patient["id"])
    assert response.status_code == 403
    assert response.json()["code"] == "NO_PATIENT_ACCESS"


def test_doctor_a_cannot_reach_doctor_bs_patient(client, make_account, login, doctor, patient, db):
    other_id, other_email = make_account(email="doctor-b@example.com", role="doctor")
    doctor_b = {"id": other_id, "headers": login(other_email)}
    grant_access(client, patient, doctor_b)
    upload(client, patient)

    assert doctor_summary(client, doctor, patient["id"]).status_code == 403
    # And the doctor who *is* authorized still can.
    assert doctor_summary(client, doctor_b, patient["id"]).status_code == 200


def test_nonexistent_and_ungranted_patients_are_indistinguishable(
    client, make_account, doctor, patient, db
):
    """The summary route must not become an existence oracle.

    Byte-for-byte identical bodies: same status, same `detail`, same `code`.
    A doctor who can tell the two apart can enumerate the patient collection,
    which is exactly what `assert_patient_access` exists to prevent.
    """
    stranger_id, _ = make_account(email="nobody@example.com", role="patient")

    ungranted = doctor_summary(client, doctor, patient["id"])
    nonexistent = doctor_summary(client, doctor, stranger_id)

    assert ungranted.status_code == nonexistent.status_code == 403
    assert ungranted.json() == nonexistent.json()


def test_a_malformed_patient_id_is_rejected_before_any_query(client, doctor):
    response = doctor_summary(client, doctor, "not-an-object-id")
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PATIENT_ID"


def test_a_malformed_id_is_not_an_oracle_either(client, doctor, patient):
    """Different failure (400, not 403) but still no summary and no data."""
    assert doctor_summary(client, doctor, "not-an-object-id").status_code == 400
    assert doctor_summary(client, doctor, patient["id"]).status_code == 403


def test_regenerate_is_authorized_exactly_like_the_read(client, patient, doctor):
    grant_access(client, patient, doctor)
    upload(client, patient)

    assert client.post(
        f"/doctor/patients/{patient['id']}/summary/regenerate", headers=doctor["headers"]
    ).status_code == 200


def test_regenerate_is_refused_for_an_unauthorized_doctor(client, patient, doctor, db):
    upload(client, patient)

    response = client.post(
        f"/doctor/patients/{patient['id']}/summary/regenerate", headers=doctor["headers"]
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NO_PATIENT_ACCESS"
    assert stored_summary(db, patient["id"]) is None


# =====================================================================
# D. patient isolation
# =====================================================================


def test_a_patient_reads_their_own_summary(client, patient):
    upload(client, patient)

    response = own_summary(client, patient)

    assert response.status_code == 200, response.text
    assert response.json()["patient_id"] == patient["id"]


def test_a_patient_never_sees_another_patients_summary(client, patient, other_patient, db):
    """`/patients/me` has no id in it, so there is nothing to tamper with."""
    upload(client, patient, RICH_REPORT)
    upload(client, other_patient, "Lipid panel\nCholesterol 6.1 mmol/L")

    mine = own_summary(client, patient).json()
    theirs = own_summary(client, other_patient).json()

    assert mine["id"] != theirs["id"]
    assert mine["patient_id"] == patient["id"]
    assert theirs["patient_id"] == other_patient["id"]
    assert "Cholesterol" in section_text(theirs, "lab_values")
    assert "Cholesterol" not in section_text(mine, "lab_values")


def test_the_doctor_and_the_patient_read_the_same_summary(client, patient, doctor):
    grant_access(client, patient, doctor)
    upload(client, patient)

    as_patient = own_summary(client, patient).json()
    as_doctor = doctor_summary(client, doctor, patient["id"]).json()

    # One service, one document, one id -- not two similar summaries.
    assert as_patient == as_doctor


# =====================================================================
# E. generation and staleness
# =====================================================================


def test_a_summary_is_generated_when_none_exists(client, patient, db):
    upload(client, patient)

    body = own_summary(client, patient).json()

    assert body["id"]
    assert body["patient_id"] == patient["id"]
    assert stored_summary(db, patient["id"]) is not None


def test_a_fresh_summary_is_returned_not_rebuilt(client, patient, db):
    upload(client, patient)
    first = own_summary(client, patient).json()

    second = own_summary(client, patient).json()

    # Identical down to `generated_at`: the read path did not rewrite it.
    assert second == first
    assert second["generated_at"] == first["generated_at"]


def test_exactly_one_summary_row_exists_per_patient(client, patient, db):
    upload(client, patient)
    own_summary(client, patient)
    own_summary(client, patient)

    assert db.patient_summaries.count_documents({"patient_id": patient["id"]}) == 1


def test_a_new_record_makes_the_summary_stale(client, patient):
    upload(client, patient, RICH_REPORT)
    first = own_summary(client, patient).json()

    upload(client, patient, FLAT_REPORT, filename="receipt.pdf")
    second = own_summary(client, patient).json()

    assert second["source_document_count"] == 2
    assert set(second["source_document_ids"]) != set(first["source_document_ids"])
    # The new record has no extractable structure, so its own sections stay
    # explicit rather than blank.
    assert len(second["source_document_ids"]) == 2


def test_a_deleted_record_makes_the_summary_stale(client, patient):
    keep = upload(client, patient, RICH_REPORT, filename="keep.pdf")
    drop = upload(client, patient, RICH_REPORT, filename="drop.pdf")
    first = own_summary(client, patient).json()
    assert first["source_document_count"] == 2

    assert client.delete(
        f"/patients/me/documents/{drop}", headers=patient["headers"]
    ).status_code == 200

    second = own_summary(client, patient).json()
    assert second["source_document_count"] == 1
    assert second["source_document_ids"] == [keep]


def test_a_record_that_becomes_readable_makes_the_summary_stale(client, patient):
    """The unreadable count is part of the staleness check, not just a label.

    A summary written while a scan was unreadable says "1 uploaded document
    could not be read". Once that file is gone the sentence is false, so the
    persisted count has to be recomputed rather than served from the row.
    """
    upload(client, patient, RICH_REPORT, filename="readable.pdf")
    scan = upload(client, patient, content=blank_pdf(), filename="scan.pdf")

    first = own_summary(client, patient).json()
    assert first["unreadable_document_count"] == 1
    assert first["source_document_count"] == 1

    assert client.delete(
        f"/patients/me/documents/{scan}", headers=patient["headers"]
    ).status_code == 200

    second = own_summary(client, patient).json()
    assert second["unreadable_document_count"] == 0
    assert second["source_document_count"] == 1
    assert "could not be read" not in second["overview"]


def test_a_patient_cannot_force_a_rebuild(client, patient, db):
    """Rebuilding is a doctor action. There is no patient-side route for it.

    The provider's call count is the assertion that matters: the refusal is not
    only a status code, it happened before generation ran at all.
    """
    upload(client, patient)
    own_summary(client, patient)

    marker = MarkerProvider()
    summary_service.set_summary_provider(marker)

    response = client.post(
        f"/doctor/patients/{patient['id']}/summary/regenerate",
        headers=patient["headers"],
    )

    assert response.status_code == 403
    assert marker.calls == 0
    assert stored_summary(db, patient["id"]) is not None


def test_regenerate_rebuilds_a_summary_for_an_authorized_doctor(client, patient, doctor):
    grant_access(client, patient, doctor)
    upload(client, patient)
    first = doctor_summary(client, doctor, patient["id"]).json()

    marker = MarkerProvider("FORCED-REBUILD")
    summary_service.set_summary_provider(marker)

    response = client.post(
        f"/doctor/patients/{patient['id']}/summary/regenerate", headers=doctor["headers"]
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert marker.calls == 1
    assert "FORCED-REBUILD" in section_text(body, "lab_values")
    # Still one row, and still the same document id: an upsert, not an insert.
    assert body["id"] == first["id"]


def test_the_read_path_does_not_rebuild_a_fresh_summary(client, patient, doctor):
    grant_access(client, patient, doctor)
    upload(client, patient)
    own_summary(client, patient)

    marker = MarkerProvider()
    summary_service.set_summary_provider(marker)

    response = doctor_summary(client, doctor, patient["id"])

    assert response.status_code == 200
    assert marker.calls == 0


def test_a_patient_with_no_documents_at_all_says_so_everywhere(client, patient):
    """The honest zero: a summary exists and admits it has nothing."""
    body = own_summary(client, patient).json()

    assert body["source_document_count"] == 0
    assert body["source_document_ids"] == []
    assert [section["key"] for section in body["sections"]] == [
        key for key, _ in SUMMARY_SECTIONS
    ]
    assert all(section["empty_note"] == EMPTY_SECTION_NOTE for section in body["sections"])
    assert "no readable records" in body["overview"]


# =====================================================================
# F. the mock provider
# =====================================================================


def test_the_summary_is_labelled_mock(client, patient):
    upload(client, patient)

    body = own_summary(client, patient).json()

    # Stored, not inferred from the prose.
    assert body["provider"] == "mock"
    assert body["is_mock"] is True
    assert body["model"] is None


def test_the_provider_is_selected_from_configuration():
    summary_service.reset_summary_provider()
    try:
        assert get_summary_provider().name == "mock"
        assert get_summary_provider().is_mock is True
    finally:
        summary_service.reset_summary_provider()


@pytest.mark.parametrize("configured", ["openai", "anthropic", "anything-else"])
def test_an_unimplemented_provider_fails_loudly(monkeypatch, configured):
    """Phase 4C providers must not be silently accepted.

    A provider that is requested and does not exist has to raise. Returning an
    empty summary instead would leave `provider: "openai"` on a document
    nothing produced.
    """
    summary_service.reset_summary_provider()
    monkeypatch.setattr(settings, "ai_provider", configured)
    try:
        with pytest.raises(SummaryProviderUnavailable):
            get_summary_provider()
    finally:
        summary_service.reset_summary_provider()


def test_an_unimplemented_provider_is_a_503_over_http(client, patient, doctor, monkeypatch):
    """The loud failure has to reach the client as a 503, not a 500.

    `SummaryProviderUnavailable` is a `RuntimeError`, and the only handler that
    catches a bare exception is the catch-all, which answers `500
    INTERNAL_ERROR`. That is the wrong answer twice over: it reports a
    misconfiguration as a server crash, and `INTERNAL_ERROR` tells the client
    nothing about whether retrying could ever help.

    503 is the honest code. The server is fine and the records are readable;
    the thing that is missing is a summarizer, and it will stay missing until
    somebody sets `AI_PROVIDER` to a value this build implements. Only the
    doctor route is exercised because both routes share one controller path,
    so a second copy of this test would test the same line twice.
    """
    grant_access(client, patient, doctor)
    summary_service.reset_summary_provider()
    monkeypatch.setattr(settings, "ai_provider", "openai")
    try:
        response = doctor_summary(client, doctor, patient["id"])
    finally:
        summary_service.reset_summary_provider()

    assert response.status_code == 503, response.text
    body = response.json()
    assert body["code"] == "SUMMARY_PROVIDER_UNAVAILABLE"


def test_an_unimplemented_provider_says_nothing_about_the_records(client, patient, doctor, monkeypatch):
    """The 503 must not quote a record, and must not blame the server.

    A provider failure is a configuration problem. The detail names the
    setting and nothing else: no document text, no filename, no storage path,
    no exception type, no traceback.
    """
    grant_access(client, patient, doctor)
    upload(client, patient, text=RICH_REPORT)
    summary_service.reset_summary_provider()
    monkeypatch.setattr(settings, "ai_provider", "openai")
    try:
        response = doctor_summary(client, doctor, patient["id"])
    finally:
        summary_service.reset_summary_provider()

    detail = response.json()["detail"]
    lowered = detail.lower()
    assert "glucose" not in lowered
    assert "metformin" not in lowered
    assert "report.pdf" not in lowered
    assert "traceback" not in lowered
    assert "summaryproviderunavailable" not in lowered


def test_an_unimplemented_provider_writes_no_summary(client, patient, doctor, db, monkeypatch):
    """A refused generation must not leave a partial or empty summary behind.

    Otherwise the doctor's next click finds a stored document, decides it is
    not stale, and serves the empty one as if it were current -- turning a loud
    misconfiguration into a silently wrong screen.
    """
    grant_access(client, patient, doctor)
    summary_service.reset_summary_provider()
    monkeypatch.setattr(settings, "ai_provider", "openai")
    try:
        assert doctor_summary(client, doctor, patient["id"]).status_code == 503
    finally:
        summary_service.reset_summary_provider()

    assert stored_summary(db, patient["id"]) is None


def test_the_503_detail_does_not_echo_the_configured_value(monkeypatch):
    """The refusal must not reflect the rejected value back to the client.

    `AI_PROVIDER` is free text, and the most likely way to break this build is
    to paste a key into the wrong variable. Now that the message is rendered
    rather than swallowed by the catch-all handler, echoing the configured
    value would return that key in the response body. The value belongs in the
    server log; the response names the providers that do work instead.
    """
    summary_service.reset_summary_provider()
    monkeypatch.setattr(settings, "ai_provider", "sk-live-looks-like-a-secret")
    try:
        with pytest.raises(SummaryProviderUnavailable) as caught:
            get_summary_provider()
    finally:
        summary_service.reset_summary_provider()

    detail = caught.value.detail.lower()
    assert "sk-live" not in detail
    assert "mock" in detail


def test_the_provider_output_is_deterministic():
    """Same payload, same output. No clock, no randomness, no ordering luck."""
    document = summary_service.SummaryDocument(
        id="doc-1",
        title="Bloods",
        category="lab_report",
        document_date="2026-05-14",
        page_count=1,
        character_count=42,
        extracted_data={
            "lab_values": [
                {"name": "Glucose", "value": "126", "unit": "mg/dL", "flag": "high"}
            ]
        },
    )
    payload = summary_service.SummaryPayload(
        patient_id="patient-1",
        profile=summary_service.SummaryProfile("Asha Raman", "1988-03-14", "female"),
        documents=(document,),
        unreadable_document_count=0,
    )

    first = MockSummaryProvider().generate(payload)
    second = MockSummaryProvider().generate(payload)

    assert first == second
    assert first.overview == second.overview


def test_the_same_records_regenerate_to_the_same_prose(client, patient, doctor):
    """Two forced rebuilds of one unchanged record set agree.

    Prose against prose -- `generated_at` and `id` differ by design, and the
    point is that nothing a doctor reads changes when nothing has.
    """
    grant_access(client, patient, doctor)
    upload(client, patient, RICH_REPORT)
    regenerate = f"/doctor/patients/{patient['id']}/summary/regenerate"

    first = client.post(regenerate, headers=doctor["headers"]).json()
    second = client.post(regenerate, headers=doctor["headers"]).json()

    assert second["overview"] == first["overview"]
    assert second["sections"] == first["sections"]
    assert second["source_document_ids"] == first["source_document_ids"]


# =====================================================================
# G. source traceability
# =====================================================================


def test_every_item_names_a_document(client, patient):
    upload(client, patient, RICH_REPORT)

    body = own_summary(client, patient).json()

    items = all_items(body)
    assert items, "the fixture record should have produced at least one item"
    for item in items:
        assert item["source_document_id"], item
        assert item["text"].strip()


def test_every_source_id_belongs_to_this_patient(client, patient, other_patient, db):
    """The property that makes a summary auditable rather than merely pretty."""
    mine = upload(client, patient, RICH_REPORT)
    theirs = upload(client, other_patient, RICH_REPORT)

    body = own_summary(client, patient).json()
    referenced = {item["source_document_id"] for item in all_items(body)}

    assert referenced
    assert referenced <= {mine}
    assert theirs not in referenced
    for document_id in referenced:
        owner = db.medical_documents.find_one({"_id": ObjectId(document_id)})
        assert owner["patient_id"] == patient["id"]


def test_source_ids_agree_with_the_source_document_list(client, patient):
    first = upload(client, patient, RICH_REPORT, filename="a.pdf")
    second = upload(client, patient, FLAT_REPORT, filename="b.pdf")

    body = own_summary(client, patient).json()

    assert set(body["source_document_ids"]) == {first, second}
    assert body["source_document_count"] == 2


def test_items_keep_the_documents_own_words(client, patient):
    """`source_text` is the verbatim line, not a paraphrase."""
    upload(client, patient, RICH_REPORT)

    body = own_summary(client, patient).json()
    labs = sections_by_key(body)["lab_values"]["items"]

    assert any("Glucose 126 mg/dL" in item["source_text"] for item in labs)


# =====================================================================
# H. invalid provider output
# =====================================================================


def test_untraceable_items_are_dropped(client, patient, other_patient):
    """A claim that cannot name this patient's record is not persisted.

    Three of the four rogue items are unusable: one has no source at all, one
    points at another patient's record, one names an id that does not exist.
    The fourth is properly attributed to this patient's own record and must
    survive -- otherwise the filter would be dropping content rather than
    untraceable claims, which is a different bug with the same visible symptom.
    """
    mine = upload(client, patient, RICH_REPORT)
    theirs = upload(client, other_patient, RICH_REPORT)
    summary_service.set_summary_provider(RogueProvider(theirs, mine))

    body = own_summary(client, patient).json()

    items = all_items(body)
    assert len(items) == 1
    assert items[0]["text"] == "extra"
    assert items[0]["source_document_id"] == mine


def test_a_foreign_claim_is_never_attached_to_the_right_document(
    client, patient, other_patient
):
    """The failure mode that matters: silently re-attributing a bad claim."""
    mine = upload(client, patient, RICH_REPORT)
    theirs = upload(client, other_patient, RICH_REPORT)
    summary_service.set_summary_provider(RogueProvider(theirs, mine))

    body = own_summary(client, patient).json()

    text = claims_text(body)
    for forbidden in ("someone else's result", "invented document", "unsourced claim"):
        assert forbidden not in text, forbidden
    assert "deteriorating" not in text
    # Nothing is ever re-pointed at a document that did exist.
    assert not [
        item
        for item in all_items(body)
        if item["source_document_id"] != mine
    ]


def test_sections_the_architecture_does_not_define_are_dropped(client, patient):
    """A provider cannot invent a clinical section.

    "Prognosis" is not in the fixed list and would be a section this system
    has no business rendering, whatever the provider says it contains.
    """
    mine = upload(client, patient, RICH_REPORT)
    summary_service.set_summary_provider(RogueProvider("000000000000000000000000", mine))

    body = own_summary(client, patient).json()

    assert [section["key"] for section in body["sections"]] == [
        key for key, _ in SUMMARY_SECTIONS
    ]
    assert "deteriorating" not in claims_text(body)


def test_the_section_order_is_fixed(client, patient):
    """Even a provider that reorders its sections cannot change the render order."""
    upload(client, patient, RICH_REPORT)

    body = own_summary(client, patient).json()

    assert [section["key"] for section in body["sections"]] == [
        key for key, _ in SUMMARY_SECTIONS
    ]
    assert [section["title"] for section in body["sections"]] == [
        title for _, title in SUMMARY_SECTIONS
    ]


def test_a_provider_returning_nothing_still_renders_every_section(client, patient):
    upload(client, patient, RICH_REPORT)

    class EmptyProvider:
        name = "custom"
        is_mock = False
        model = None

        def generate(self, payload):
            return SummaryDraft(overview="", sections=())

    summary_service.set_summary_provider(EmptyProvider())
    body = own_summary(client, patient).json()

    assert len(body["sections"]) == len(SUMMARY_SECTIONS)
    assert all(section["items"] == [] for section in body["sections"])


def test_items_are_bounded(client, patient):
    """A provider cannot return an unbounded item list or an endless string."""
    mine = upload(client, patient, RICH_REPORT)

    class GreedyProvider:
        name = "custom"
        is_mock = False
        model = None

        def generate(self, payload):
            return SummaryDraft(
                overview="x" * 100_000,
                sections=(
                    ProviderSection(
                        key="lab_values",
                        title="Important Lab Values",
                        items=tuple(
                            SummaryItem(f"claim {index}", mine, None)
                            for index in range(10_000)
                        ),
                    ),
                ),
            )

    summary_service.set_summary_provider(GreedyProvider())
    body = own_summary(client, patient).json()

    labs = sections_by_key(body)["lab_values"]
    assert len(labs["items"]) == MAX_ITEMS_PER_SECTION
    assert len(body["overview"]) <= 600
    assert all(len(item["text"]) <= 600 for item in labs["items"])


# =====================================================================
# I. privacy of the provider payload
# =====================================================================


def test_the_provider_is_not_sent_contact_details(client, patient):
    """`phone`, `address` and `notes` exist on the profile and must not travel.

    A real provider in Phase 4C would be a third party holding them. A summary
    needs none of them, so they are not in the dataclass that carries the
    payload -- there is no filter to forget.
    """
    set_profile(
        client,
        patient,
        full_name="Asha Raman",
        phone="+44 7700 900123",
        address="14 Example Street",
        notes="Family history of migraine. Prefers morning appointments.",
        gender="female",
        date_of_birth="1988-03-14",
    )
    document_id = upload(client, patient, RICH_REPORT)

    recorder = RecordingProvider()
    summary_service.set_summary_provider(recorder)

    assert own_summary(client, patient).status_code == 200

    payload = recorder.last
    blob = repr(payload)

    for secret in ("+44 7700 900123", "14 Example Street", "migraine", "Example Street"):
        assert secret not in blob, secret

    assert payload.profile.full_name == "Asha Raman"
    assert payload.profile.date_of_birth == "1988-03-14"
    assert payload.profile.gender == "female"
    # Nothing about storage internals either.
    for internal in ("storage_key", "stored_filename", "extraction_error", "original_filename"):
        assert internal not in blob, internal
    assert payload.documents[0].id == document_id


def test_the_payload_carries_no_raw_text_and_no_storage_fields(client, patient, db):
    """The provider sees the structured extraction, not the page it came from.

    The field list is asserted rather than a few names being absent, because
    the failure mode is an added field: a future edit that tacks `extracted_text`
    onto this dataclass would quietly ship every uploaded page to a third party
    in Phase 4C, and `hasattr` spot checks are exactly what misses that.
    """
    upload(client, patient, RICH_REPORT)

    recorder = RecordingProvider()
    summary_service.set_summary_provider(recorder)
    own_summary(client, patient)

    document = recorder.last.documents[0]
    stored = db.medical_documents.find_one({"patient_id": patient["id"]})

    assert [field.name for field in dataclasses.fields(document)] == [
        "id",
        "title",
        "category",
        "document_date",
        "page_count",
        "character_count",
        "extracted_data",
    ]
    assert [field.name for field in dataclasses.fields(recorder.last.profile)] == [
        "full_name",
        "date_of_birth",
        "gender",
    ]
    assert document.extracted_data == stored["extracted_data"]
    assert stored["extracted_text"], "the raw text exists; it just must not travel"
    assert stored["extracted_text"] not in repr(document)


def test_the_payload_never_contains_another_patients_records(
    client, patient, other_patient
):
    upload(client, other_patient, RICH_REPORT, title="Other person report")
    mine = upload(client, patient, RICH_REPORT, title="My report")

    recorder = RecordingProvider()
    summary_service.set_summary_provider(recorder)
    own_summary(client, patient)

    payload = recorder.last
    assert [document.id for document in payload.documents] == [mine]
    assert "Other person report" not in repr(payload)
    assert payload.patient_id == patient["id"]


# =====================================================================
# J. unreadable documents
# =====================================================================


def test_scanned_and_failed_records_are_excluded_but_counted(client, patient):
    """The honest accounting: 1 of 3 records is in the summary, and it says so."""
    readable = upload(client, patient, RICH_REPORT, filename="readable.pdf")
    upload(client, patient, content=blank_pdf(), filename="scan.pdf")
    upload(client, patient, content=corrupt_pdf(), filename="broken.pdf")

    body = own_summary(client, patient).json()

    assert body["source_document_count"] == 1
    assert body["source_document_ids"] == [readable]
    assert body["unreadable_document_count"] == 2
    assert "2 uploaded documents could not be read" in body["overview"]


def test_unreadable_records_never_contribute_facts(client, patient):
    """Nothing can be quoted from a record nobody could read."""
    readable = upload(client, patient, RICH_REPORT, filename="readable.pdf")
    upload(client, patient, content=blank_pdf(), filename="scan.pdf")

    body = own_summary(client, patient).json()
    referenced = {item["source_document_id"] for item in all_items(body)}

    assert referenced <= {readable}
    assert body["source_document_ids"] == [readable]
    assert body["source_document_count"] == 1


def test_a_patient_with_only_scans_gets_an_empty_but_complete_summary(client, patient):
    upload(client, patient, content=blank_pdf(), filename="scan.pdf")

    body = own_summary(client, patient).json()

    assert body["source_document_count"] == 0
    assert body["unreadable_document_count"] == 1
    assert all(section["items"] == [] for section in body["sections"])
    assert all(section["empty_note"] == EMPTY_SECTION_NOTE for section in body["sections"])


# =====================================================================
# K. empty data
# =====================================================================


# Sections that report *facts extracted from* a record. The other two
# (`recent_records`, `chronological_overview`) report which records exist, so
# they are populated whenever anything readable was uploaded -- a document with
# no lab values in it is still a document.
FACT_SECTIONS = (
    "patient_overview",
    "medical_history",
    "key_findings",
    "lab_values",
    "medications",
    "abnormal_values",
)


def test_a_record_with_no_extractable_structure_says_so_in_every_fact_section(
    client, patient
):
    """Silence would read as "nothing abnormal". Every section states it.

    The document is readable -- it has text -- it just contains nothing this
    pipeline knows how to extract. The summary must not present that as a
    normal result.
    """
    upload(client, patient, FLAT_REPORT)

    body = own_summary(client, patient).json()
    by_key = sections_by_key(body)

    assert body["source_document_count"] == 1
    assert body["unreadable_document_count"] == 0
    for key in FACT_SECTIONS:
        assert by_key[key]["items"] == [], key
        assert by_key[key]["empty_note"] == EMPTY_SECTION_NOTE, key
    # The two inventory sections still list the record, because it exists.
    assert by_key["recent_records"]["items"]
    assert "1 readable record" in body["overview"]
    assert "could not be read" not in body["overview"]


def test_the_empty_note_is_the_architectures_exact_wording(client, patient):
    upload(client, patient, FLAT_REPORT)

    body = own_summary(client, patient).json()

    assert EMPTY_SECTION_NOTE == "Not found in the uploaded records."
    notes = {
        section["empty_note"]
        for section in body["sections"]
        if section["empty_note"] is not None
    }
    assert notes == {EMPTY_SECTION_NOTE}


def test_a_populated_section_has_no_empty_note(client, patient):
    upload(client, patient, RICH_REPORT)

    body = own_summary(client, patient).json()
    by_key = sections_by_key(body)

    assert by_key["lab_values"]["items"]
    assert by_key["lab_values"]["empty_note"] is None
    # ...and a section with nothing in it still says so.
    assert by_key["recent_records"]["empty_note"] is None


# =====================================================================
# L. safety
# =====================================================================


def test_a_lab_value_never_becomes_a_diagnosis(client, patient):
    """`Glucose 126 mg/dL` is reported as a number. That is the whole claim.

    If this test ever fails, a summary is asserting a condition no document
    stated, which is the single worst thing this system could do.
    """
    upload(client, patient, GLUCOSE_ONLY)

    body = own_summary(client, patient).json()
    text = claims_text(body)

    assert "glucose" in text
    assert "126" in text
    assert "diabet" not in text
    assert "diagnos" not in text
    # Nothing reached the history section either.
    assert sections_by_key(body)["medical_history"]["items"] == []


def test_an_explicitly_stated_condition_is_reported_as_a_statement(client, patient):
    upload(client, patient, RICH_REPORT)

    body = own_summary(client, patient).json()
    history = sections_by_key(body)["medical_history"]

    assert history["items"], "the fixture states a diagnosis explicitly"
    assert "Type 2 Diabetes Mellitus" in history["items"][0]["text"]
    assert "The document states" in history["items"][0]["text"]


def test_a_medication_is_reported_without_advice(client, patient):
    upload(client, patient, RICH_REPORT)

    body = own_summary(client, patient).json()
    medications = section_text(body, "medications").lower()

    assert "metformin" in medications
    assert "500 mg" in medications
    for forbidden in ("should take", "recommended", "continue", "increase", "reduce", "stop taking"):
        assert forbidden not in medications, forbidden


def test_a_flagged_value_is_reported_as_the_documents_own_marker(client, patient):
    """The flag is transcribed, never computed, and the wording says so."""
    upload(client, patient, RICH_REPORT)

    body = own_summary(client, patient).json()
    abnormal = section_text(body, "abnormal_values")

    assert "126" in abnormal
    assert "The document marks this value" in abnormal


def test_an_unmarked_value_never_appears_as_abnormal(client, patient):
    """Haemoglobin 14.2 sits inside the printed range and carries no marker."""
    upload(client, patient, RICH_REPORT)

    body = own_summary(client, patient).json()
    abnormal = section_text(body, "abnormal_values")

    assert "14.2" not in abnormal


def test_nothing_in_the_claims_is_interpreted(client, patient):
    """No urgency, no severity, no advice, anywhere in the generated text."""
    upload(client, patient, RICH_REPORT)

    text = claims_text(own_summary(client, patient).json())

    for forbidden in (
        "the patient has",
        "you have",
        "diagnos",
        "suffering",
        "critical",
        "dangerous",
        "urgent",
        "treat",
        "therapy",
        "prescrib",
        "mg daily",
    ):
        assert forbidden not in text, forbidden


def test_the_summary_never_prints_a_stored_enum(client, patient):
    """A clinician reads prose, not database values.

    The category is a `Literal` the patient picked at upload time; printing
    `lab_report` inside a sentence reads like a debugging artifact and, worse,
    invites a reader to treat a storage value as if it were a clinical label.
    Every screen that shows this word shows "Lab report", and the summary has
    to agree with them.
    """
    upload(client, patient, RICH_REPORT, category="lab_report")

    body = own_summary(client, patient).json()

    assert "lab_report" not in claims_text(body), "the stored enum leaked"
    for forbidden in ("discharge_summary", "needs_ocr", "completed"):
        assert forbidden not in claims_text(body), forbidden
    # `claims_text` lowercases, so this is the humanized label.
    assert "category: lab report" in claims_text(body)


def test_the_overview_claims_nothing_about_the_patient(client, patient):
    """The framing sentence describes the records, not the patient.

    It may say how many records were read and how the patient asked to be
    described, and that is all. It is generated text too, so it is held to the
    same rule as the sections.
    """
    upload(client, patient, RICH_REPORT)

    overview = own_summary(client, patient).json()["overview"].lower()

    assert "nothing here is a diagnosis or an interpretation" in overview
    assert "links to the document it came from" in overview
    assert "diabet" not in overview
    assert "the patient has" not in overview


# =====================================================================
# M. the disclaimer
# =====================================================================


def test_the_disclaimer_is_the_server_constant(client, patient):
    upload(client, patient)

    body = own_summary(client, patient).json()

    assert body["disclaimer"] == AI_SUMMARY_DISCLAIMER


def test_the_provider_cannot_overwrite_the_disclaimer(client, patient):
    """There is no field for it to overwrite, and the stored copy is server-side."""
    mine = upload(client, patient, RICH_REPORT)

    class DisclaimerProvider:
        name = "custom"
        is_mock = False
        model = None

        def generate(self, payload):
            draft = MOCK_PROVIDER.generate(payload)
            # Everything a provider might plausibly try, none of which exists
            # on SummaryDraft.
            return SummaryDraft(
                overview="Our records say this patient is fine.",
                sections=draft.sections,
            )

    summary_service.set_summary_provider(DisclaimerProvider())
    body = own_summary(client, patient).json()

    assert body["disclaimer"] == AI_SUMMARY_DISCLAIMER
    # Asserted on the type, not an instance: the field does not exist to be
    # overwritten, so there is nothing for a provider to write *into*.
    assert "disclaimer" not in SummaryDraft.__dataclass_fields__
    assert body["source_document_ids"] == [mine]


def test_the_disclaimer_survives_a_failing_provider(client, patient):
    upload(client, patient)
    summary_service.set_summary_provider(FailingProvider(RuntimeError("boom")))

    body = own_summary(client, patient).json()

    assert body["disclaimer"] == AI_SUMMARY_DISCLAIMER


# =====================================================================
# provider failure
# =====================================================================


@pytest.mark.parametrize(
    "exception",
    [
        RuntimeError("upstream 500"),
        TimeoutError("read timed out"),
        ConnectionError("connection reset"),
        ValueError("malformed upstream response"),
    ],
    ids=["raises", "times-out", "drops", "garbage"],
)
def test_a_failing_provider_falls_back_without_leaking(client, patient, exception):
    """A provider failure is not the patient's problem to debug.

    The response is the deterministic summary, labelled `is_mock`, with no
    invented facts and none of the provider's exception text anywhere in it.
    """
    upload(client, patient, RICH_REPORT)
    failing = FailingProvider(exception)
    summary_service.set_summary_provider(failing)

    response = own_summary(client, patient)

    assert response.status_code == 200, response.text
    body = response.json()
    assert failing.calls == 1
    assert body["provider"] == "mock"
    assert body["is_mock"] is True
    assert body["source_document_count"] == 1
    # Real facts from the extraction, still traceable -- not a fallback that
    # made something up and not an empty screen.
    assert "Glucose" in section_text(body, "lab_values")
    for section in body["sections"]:
        for item in section["items"]:
            assert item["source_document_id"] in body["source_document_ids"]
    assert "boom" not in str(body)
    assert "timed out" not in str(body)


def test_a_failing_provider_does_not_persist_its_name(client, patient, db):
    upload(client, patient)
    summary_service.set_summary_provider(FailingProvider(RuntimeError("boom")))

    own_summary(client, patient)

    stored = stored_summary(db, patient["id"])
    assert stored["provider"] == "mock"
    assert stored["is_mock"] is True


def test_a_failing_provider_still_cannot_bypass_authorization(client, patient, doctor, db):
    upload(client, patient)
    summary_service.set_summary_provider(FailingProvider(RuntimeError("boom")))

    response = doctor_summary(client, doctor, patient["id"])

    assert response.status_code == 403
    assert stored_summary(db, patient["id"]) is None


# =====================================================================
# N. regressions in the phases this one sits on
# =====================================================================


def test_phase_4a_extraction_still_fills_extracted_data(client, patient, db):
    """The summary consumes `extracted_data`; Phase 4A must still produce it."""
    upload(client, patient, RICH_REPORT)

    stored = db.medical_documents.find_one({"patient_id": patient["id"]})
    data = stored["extracted_data"]

    assert stored["extraction_status"] == "completed"
    assert {entry["name"] for entry in data["lab_values"]} == {"Glucose", "Haemoglobin"}
    assert data["lab_values"][0]["source_text"]
    assert data["stated_conditions"]


def test_phase_2_outcomes_are_unchanged(client, patient, db):
    """`needs_ocr` and `failed` still mean empty `extracted_data`, and now a count."""
    upload(client, patient, content=blank_pdf(), filename="scan.pdf")
    upload(client, patient, content=corrupt_pdf(), filename="broken.pdf")

    statuses = {
        document["extraction_status"]
        for document in db.medical_documents.find({"patient_id": patient["id"]})
    }
    assert statuses == {"needs_ocr", "failed"}
    assert all(
        document["extracted_data"] == {}
        for document in db.medical_documents.find({"patient_id": patient["id"]})
    )

    body = own_summary(client, patient).json()
    assert body["source_document_count"] == 0
    assert body["unreadable_document_count"] == 2


def test_the_summary_does_not_touch_the_record_list(client, patient, doctor):
    """Phase 3 read-only guarantees: adding a summary route changes no data.

    A doctor may read a summary and may ask for it to be rebuilt. Neither
    writes to `medical_documents`, and there is still no doctor-side route
    that can.
    """
    grant_access(client, patient, doctor)
    document_id = upload(client, patient, RICH_REPORT)
    before = client.get(
        f"/doctor/patients/{patient['id']}/documents", headers=doctor["headers"]
    ).json()

    doctor_summary(client, doctor, patient["id"])
    client.post(
        f"/doctor/patients/{patient['id']}/summary/regenerate", headers=doctor["headers"]
    )

    after = client.get(
        f"/doctor/patients/{patient['id']}/documents", headers=doctor["headers"]
    ).json()
    assert before == after
    assert after["items"][0]["id"] == document_id

    for method in ("delete", "patch", "put"):
        call = getattr(client, method)
        assert call(
            f"/doctor/patients/{patient['id']}/documents/{document_id}",
            headers=doctor["headers"],
        ).status_code == 405


def test_deleting_the_summary_is_not_offered(client, patient, doctor):
    """A doctor never edits a summary by hand, so there is no route to."""
    grant_access(client, patient, doctor)
    upload(client, patient)

    assert client.delete(
        f"/doctor/patients/{patient['id']}/summary", headers=doctor["headers"]
    ).status_code == 405
    assert client.put(
        f"/doctor/patients/{patient['id']}/summary", headers=doctor["headers"]
    ).status_code == 405
    assert client.delete(
        f"/patients/me/summary", headers=patient["headers"]
    ).status_code == 405


def test_deleting_a_record_leaves_the_summary_regenerable(client, patient):
    upload(client, patient, RICH_REPORT, filename="a.pdf")
    upload(client, patient, RICH_REPORT, filename="b.pdf")
    own_summary(client, patient)

    items = client.get("/patients/me/documents", headers=patient["headers"]).json()["items"]
    client.delete(
        f"/patients/me/documents/{items[0]['id']}", headers=patient["headers"]
    )

    body = own_summary(client, patient).json()
    assert body["source_document_count"] == 1
    assert body["source_document_ids"] == [items[1]["id"]]


def test_one_authorization_check_covers_both_summary_routes(client, patient, doctor):
    """The grant is what authorizes the summary, not the fact that a summary exists.

    A doctor with no grant must not learn anything from the summary route --
    not its existence, not its length, not whether the patient has records.
    """
    upload(client, patient)
    summary_service.set_summary_provider(MarkerProvider("LEAK"))
    own_summary(client, patient)  # the patient can see theirs

    refused = doctor_summary(client, doctor, patient["id"])
    assert refused.status_code == 403
    assert "LEAK" not in refused.text
    assert "source_document_count" not in refused.text
