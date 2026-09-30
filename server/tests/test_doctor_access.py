"""Doctor access to patient records, exercised through the HTTP API.

The security properties under test only exist at the route boundary, so
every case here is a real request. The pattern to keep in mind while reading
each test: **the frontend is never the thing being trusted.** Every one of
these calls constructs a URL by hand and asserts on the response, because a
hidden button in React is not an access control.

The suite is organised by what is being refused, in increasing order of how
much damage it would do if it were allowed:

  * not signed in                     -> 401
  * signed in as the wrong role       -> 403
  * wrong doctor, or no grant at all  -> 403, indistinguishable from
                                         "no such patient"
  * right doctor, wrong patient's     -> the same 403, because the grant
    document id                        lookup never consults the patient
                                       collection
"""

import pytest

from tests.pdf_fixtures import blank_pdf, text_pdf

LAB_REPORT = "Complete Blood Count\nHaemoglobin 14.2 g/dL"


# =====================================================================
# helpers
# =====================================================================


def grant_access(client, patient, doctor, note=None):
    """The patient authorizes the doctor. The one supported way to get access."""
    body = {"doctor_id": doctor["id"]}
    if note:
        body["note"] = note
    response = client.post(
        "/patients/me/access", json=body, headers=patient["headers"]
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload_pdf(client, headers, content=None, filename="report.pdf", **fields):
    return client.post(
        "/patients/me/documents",
        files={"file": (filename, content or text_pdf(LAB_REPORT), "application/pdf")},
        data=fields,
        headers=headers,
    )


def second_doctor(make_account, login):
    """An unrelated doctor -- the cross-tenant adversary, one role up."""
    user_id, email = make_account(email="doctor-b@example.com", role="doctor")
    return {"id": user_id, "email": email, "headers": login(email)}


# =====================================================================
# authentication -- no token, no access
# =====================================================================


@pytest.mark.parametrize(
    "path",
    [
        "/doctor/patients",
        "/doctor/patients/000000000000000000000000",
        "/doctor/patients/000000000000000000000000/documents",
        "/doctor/patients/000000000000000000000000/documents/000000000000000000000000",
        "/doctor/patients/000000000000000000000000/documents/"
        "000000000000000000000000/file",
    ],
)
def test_unauthenticated_caller_reaches_no_doctor_endpoint(client, path):
    """Even a path naming a real patient. The id is not checked until the
    caller is known to be a doctor, so there is nothing to leak here."""
    assert client.get(path).status_code == 401


def test_a_bogus_token_is_rejected(client):
    response = client.get(
        "/doctor/patients", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


# =====================================================================
# role -- a patient is not a doctor
# =====================================================================


@pytest.mark.parametrize(
    "path",
    [
        "/doctor/patients",
        "/doctor/patients/000000000000000000000000",
        "/doctor/patients/000000000000000000000000/documents",
    ],
)
def test_patient_cannot_reach_any_doctor_endpoint(client, patient, path):
    """Role is checked on the request, not inferred from the UI the client
    happened to render."""
    response = client.get(path, headers=patient["headers"])
    assert response.status_code == 403
    assert response.json()["code"] == "ROLE_NOT_ALLOWED"


def test_patient_cannot_see_another_patient_through_a_doctor_route(
    client, patient, other_patient
):
    """A patient aiming the doctor route at another patient is refused by
    role, before authorization is even consulted -- so this cannot be used to
    test whether that other patient's id is real."""
    response = client.get(
        f"/doctor/patients/{other_patient['id']}", headers=patient["headers"]
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ROLE_NOT_ALLOWED"


def test_doctor_cannot_use_the_patients_me_routes(client, doctor, patient):
    """The mirror image. A doctor has an id, and `/patients/me` would happily
    resolve to it -- so `assert_own_records` refuses the role outright rather
    than treating the doctor as a patient who happens to own records."""
    for path in ("/patients/me", "/patients/me/documents"):
        response = client.get(path, headers=doctor["headers"])
        assert response.status_code == 403, path
        assert response.json()["code"] == "ROLE_NOT_ALLOWED"


# =====================================================================
# the doctor list
# =====================================================================


def test_doctor_list_is_empty_before_anything_is_granted(client, doctor):
    response = client.get("/doctor/patients", headers=doctor["headers"])

    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0}


def test_doctor_list_contains_only_granted_patients(
    client, doctor, other_patient, patient
):
    grant_access(client, patient, doctor)

    response = client.get("/doctor/patients", headers=doctor["headers"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert [item["patient_id"] for item in body["items"]] == [patient["id"]]
    # The un-granted patient is absent, not present-and-filtered: there is
    # nowhere in this response that says they exist.
    assert other_patient["id"] not in str(body)


def test_doctor_list_carries_profile_details_and_a_document_count(
    client, doctor, patient
):
    client.patch(
        "/patients/me",
        json={"full_name": "Asha Kulkarni", "date_of_birth": "1994-07-11"},
        headers=patient["headers"],
    )
    upload_pdf(client, patient["headers"], title="CBC")
    upload_pdf(client, patient["headers"], filename="other.pdf")
    grant_access(client, patient, doctor)

    body = client.get("/doctor/patients", headers=doctor["headers"]).json()

    entry = body["items"][0]
    assert entry["full_name"] == "Asha Kulkarni"
    assert entry["date_of_birth"] == "1994-07-11"
    assert entry["document_count"] == 2
    # The profile belongs to the patient, not to CAREVERSE.
    assert "notes" not in entry
    assert "password_hash" not in str(body)


def test_document_count_counts_unreadable_records_too(
    client, doctor, patient
):
    """A scan the extractor could not read is still a record the patient has.
    Counting only readable ones would understate their history."""
    upload_pdf(client, patient["headers"], content=blank_pdf(), filename="scan.pdf")
    grant_access(client, patient, doctor)

    body = client.get("/doctor/patients", headers=doctor["headers"]).json()
    assert body["items"][0]["document_count"] == 1


# =====================================================================
# isolation between doctors
# =====================================================================


def test_doctor_a_cannot_see_doctor_b_authorized_patients(
    client, doctor, make_account, login, patient
):
    other_doctor = second_doctor(make_account, login)
    grant_access(client, patient, doctor)

    a = client.get("/doctor/patients", headers=doctor["headers"]).json()
    b = client.get("/doctor/patients", headers=other_doctor["headers"]).json()

    assert a["total"] == 1
    # Doctor B shares no grant with this patient, so their list is empty even
    # though the grant row naming doctor A is right there in the collection.
    assert b == {"items": [], "total": 0}


def test_doctor_b_cannot_read_the_patient_granted_to_doctor_a(
    client, doctor, make_account, login, patient
):
    other_doctor = second_doctor(make_account, login)
    upload_pdf(client, patient["headers"])
    grant_access(client, patient, doctor)

    response = client.get(
        f"/doctor/patients/{patient['id']}", headers=other_doctor["headers"]
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NO_PATIENT_ACCESS"


# =====================================================================
# unauthorized access is indistinguishable from a nonexistent patient
# =====================================================================


def test_ungranted_patient_is_refused(client, doctor, patient):
    response = client.get(
        f"/doctor/patients/{patient['id']}", headers=doctor["headers"]
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NO_PATIENT_ACCESS"


def test_a_nonexistent_patient_id_answers_exactly_the_same(
    client, doctor, patient
):
    """The existence-oracle check.

    An id that matches no user and an id that matches a real patient the
    doctor was never granted must produce a byte-identical response. If they
    differed, this endpoint would be a way to enumerate who uses CAREVERSE.
    """
    ungranted = client.get(
        f"/doctor/patients/{patient['id']}", headers=doctor["headers"]
    )
    nonexistent = client.get(
        "/doctor/patients/000000000000000000000000", headers=doctor["headers"]
    )

    assert ungranted.status_code == nonexistent.status_code == 403
    assert ungranted.json() == nonexistent.json()


def test_a_malformed_patient_id_is_a_400_not_a_403(client, doctor):
    """Rejected before it can reach a query. This is a different failure on
    purpose: it says the string is not an id, which reveals nothing about
    whether any id exists."""
    response = client.get("/doctor/patients/not-an-object-id", headers=doctor["headers"])

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PATIENT_ID"


# =====================================================================
# the authorized path
# =====================================================================


def test_authorized_doctor_reads_the_patient_profile(client, doctor, patient):
    client.patch(
        "/patients/me",
        json={"full_name": "Asha Kulkarni", "notes": "Reported by the patient."},
        headers=patient["headers"],
    )
    grant_access(client, patient, doctor)

    response = client.get(
        f"/doctor/patients/{patient['id']}", headers=doctor["headers"]
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["patient_id"] == patient["id"]
    assert body["full_name"] == "Asha Kulkarni"
    assert body["notes"] == "Reported by the patient."


def test_authorized_doctor_lists_the_patients_documents(client, doctor, patient):
    upload_pdf(client, patient["headers"], title="CBC report", category="lab_report")
    grant_access(client, patient, doctor)

    response = client.get(
        f"/doctor/patients/{patient['id']}/documents", headers=doctor["headers"]
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "CBC report"
    # Lists carry metadata, not the text itself.
    assert "extracted_text" not in body["items"][0]


def test_authorized_doctor_reads_extracted_text(client, doctor, patient):
    upload_pdf(client, patient["headers"])
    grant_access(client, patient, doctor)
    listed = client.get(
        f"/doctor/patients/{patient['id']}/documents", headers=doctor["headers"]
    ).json()
    document_id = listed["items"][0]["id"]

    response = client.get(
        f"/doctor/patients/{patient['id']}/documents/{document_id}",
        headers=doctor["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["extraction_status"] == "completed"
    # Phase 2's extraction, reused verbatim. Nothing is re-derived here.
    assert "Haemoglobin 14.2 g/dL" in body["extracted_text"]


def test_authorized_doctor_downloads_the_original_pdf(client, doctor, patient):
    content = text_pdf(LAB_REPORT)
    upload_pdf(client, patient["headers"], content=content)
    grant_access(client, patient, doctor)
    listed = client.get(
        f"/doctor/patients/{patient['id']}/documents", headers=doctor["headers"]
    ).json()
    document_id = listed["items"][0]["id"]

    response = client.get(
        f"/doctor/patients/{patient['id']}/documents/{document_id}/file",
        headers=doctor["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.content == content
    assert response.headers["content-type"] == "application/pdf"
    # The same response hardening the patient's own file route carries.
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in response.headers["cache-control"]
    assert "inline" in response.headers["content-disposition"]
    # Nothing about where the file lives on disk.
    assert "storage" not in response.text


def test_extraction_failure_is_reported_honestly_to_a_doctor(
    client, doctor, patient
):
    """A scan is not an empty record, and the doctor is told which it is."""
    upload_pdf(client, patient["headers"], content=blank_pdf(), filename="scan.pdf")
    grant_access(client, patient, doctor)
    listed = client.get(
        f"/doctor/patients/{patient['id']}/documents", headers=doctor["headers"]
    ).json()
    document_id = listed["items"][0]["id"]

    body = client.get(
        f"/doctor/patients/{patient['id']}/documents/{document_id}",
        headers=doctor["headers"],
    ).json()

    assert body["extraction_status"] == "needs_ocr"
    assert body["extracted_text"] is None
    assert body["has_text"] is False


# =====================================================================
# document isolation -- the IDOR cases
# =====================================================================


def test_unauthorized_doctor_cannot_list_documents(client, doctor, patient):
    upload_pdf(client, patient["headers"])
    # No grant.

    response = client.get(
        f"/doctor/patients/{patient['id']}/documents", headers=doctor["headers"]
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NO_PATIENT_ACCESS"


def test_unauthorized_doctor_cannot_retrieve_a_document_by_id(client, doctor, patient):
    """The id is a real document id, obtained by the attacker from
    somewhere. Knowing it changes nothing."""
    upload_pdf(client, patient["headers"])
    document_id = client.get(
        "/patients/me/documents", headers=patient["headers"]
    ).json()["items"][0]["id"]

    response = client.get(
        f"/doctor/patients/{patient['id']}/documents/{document_id}",
        headers=doctor["headers"],
    )

    assert response.status_code == 403
    assert "Haemoglobin" not in response.text


def test_unauthorized_doctor_cannot_retrieve_extracted_text(client, doctor, patient):
    upload_pdf(client, patient["headers"])
    document_id = client.get(
        "/patients/me/documents", headers=patient["headers"]
    ).json()["items"][0]["id"]

    response = client.get(
        f"/doctor/patients/{patient['id']}/documents/{document_id}",
        headers=doctor["headers"],
    )

    assert response.status_code == 403
    # The refusal must not quote the record back in its error message.
    assert "Haemoglobin" not in response.text
    assert "storage" not in response.text


def test_unauthorized_doctor_cannot_download_the_original_pdf(client, doctor, patient):
    upload_pdf(client, patient["headers"])
    document_id = client.get(
        "/patients/me/documents", headers=patient["headers"]
    ).json()["items"][0]["id"]

    response = client.get(
        f"/doctor/patients/{patient['id']}/documents/{document_id}/file",
        headers=doctor["headers"],
    )

    assert response.status_code == 403
    assert not response.content.startswith(b"%PDF")


def test_grant_to_one_patient_does_not_open_another_patients_documents(
    client, doctor, patient, other_patient
):
    """The grant is per patient, and a valid document id from the *wrong*
    patient is a 404 rather than a 403 -- the id is looked up scoped to the
    patient the doctor was actually authorized for."""
    upload_pdf(client, other_patient["headers"], filename="stranger.pdf")
    stranger_doc = client.get(
        "/patients/me/documents", headers=other_patient["headers"]
    ).json()["items"][0]["id"]
    grant_access(client, patient, doctor)

    response = client.get(
        f"/doctor/patients/{patient['id']}/documents/{stranger_doc}",
        headers=doctor["headers"],
    )

    # Authorized for `patient`, so this is a document lookup -- and the
    # stranger's document is not in this patient's set.
    assert response.status_code == 404
    assert response.json()["code"] == "DOCUMENT_NOT_FOUND"


def test_a_doctor_cannot_widen_access_by_pasting_another_patients_id(
    client, doctor, patient, other_patient
):
    """Authorized for one patient, aiming the URL at another. The grant
    lookup fails for the substituted id, so the swap does nothing."""
    grant_access(client, patient, doctor)

    response = client.get(
        f"/doctor/patients/{other_patient['id']}", headers=doctor["headers"]
    )

    assert response.status_code == 403
    assert response.json()["code"] == "NO_PATIENT_ACCESS"


# =====================================================================
# revocation takes effect immediately
# =====================================================================


def test_revoked_access_stops_working_on_the_next_request(
    client, doctor, patient
):
    """Not cached in the token and not cached in the session -- the grant row
    is re-read per request, so revocation cannot wait for a token to expire."""
    grant = grant_access(client, patient, doctor)
    assert (
        client.get(
            f"/doctor/patients/{patient['id']}", headers=doctor["headers"]
        ).status_code
        == 200
    )

    revoked = client.delete(
        f"/patients/me/access/{grant['id']}", headers=patient["headers"]
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"

    assert (
        client.get(
            f"/doctor/patients/{patient['id']}", headers=doctor["headers"]
        ).status_code
        == 403
    )
    assert client.get("/doctor/patients", headers=doctor["headers"]).json()["total"] == 0


def test_revoked_grant_still_denies_documents(client, doctor, patient):
    upload_pdf(client, patient["headers"])
    grant = grant_access(client, patient, doctor)
    client.delete(f"/patients/me/access/{grant['id']}", headers=patient["headers"])
    document_id = client.get(
        "/patients/me/documents", headers=patient["headers"]
    ).json()["items"][0]["id"]

    assert (
        client.get(
            f"/doctor/patients/{patient['id']}/documents/{document_id}/file",
            headers=doctor["headers"],
        ).status_code
        == 403
    )


# =====================================================================
# the patient remains the owner
# =====================================================================


def test_granting_a_doctor_does_not_change_who_owns_the_records(
    client, doctor, patient
):
    """Access is read-only for the doctor, and the patient keeps full control
    of their own files."""
    upload_pdf(client, patient["headers"])
    grant_access(client, patient, doctor)

    # The doctor cannot delete it...
    document_id = client.get(
        "/patients/me/documents", headers=patient["headers"]
    ).json()["items"][0]["id"]
    for suffix in ("", "/file"):
        assert (
            client.delete(
                f"/doctor/patients/{patient['id']}/documents/{document_id}{suffix}",
                headers=doctor["headers"],
            ).status_code
            == 405
        )

    # ...and it is still there for the patient, who can still remove it.
    assert client.get(
        "/patients/me/documents", headers=patient["headers"]
    ).json()["total"] == 1
    assert (
        client.delete(
            f"/patients/me/documents/{document_id}", headers=patient["headers"]
        ).status_code
        == 200
    )


def test_a_doctor_cannot_upload_to_a_patients_records(client, doctor, patient):
    grant_access(client, patient, doctor)

    response = upload_pdf(client, doctor["headers"], filename="mine.pdf")

    # 403, not a 405: a doctor is refused by role before the route is even
    # considered, which is the safer ordering.
    assert response.status_code == 403
    assert response.json()["code"] == "ROLE_NOT_ALLOWED"
    assert client.get(
        "/patients/me/documents", headers=patient["headers"]
    ).json()["total"] == 0
