"""Patient profile: create-on-register, read, partial update, validation.

These go through the HTTP API rather than the service, because the security
properties under test -- which roles are refused, what a tokenless request
gets -- exist only at the route boundary.
"""

import pytest


# --- creation -------------------------------------------------------------


def test_profile_exists_as_soon_as_a_patient_registers(client, patient):
    response = client.get("/patients/me", headers=patient["headers"])

    assert response.status_code == 200, response.text
    profile = response.json()
    assert profile["patient_id"] == patient["id"]
    # Carried over from registration, so the patient never sees a blank name.
    assert profile["full_name"] == "Test Person"
    # Nothing typed yet -> neutral defaults, not invented values.
    assert profile["date_of_birth"] is None
    assert profile["gender"] == "unspecified"


def test_profile_is_created_even_if_the_registration_row_is_missing(
    client, patient, db
):
    """The profile is a fixture of having an account, not a document that
    can be missing. A deleted row must not become a 404 on the screen that
    lets the patient recreate it."""
    db.patient_profiles.delete_one({"patient_id": patient["id"]})

    response = client.get("/patients/me", headers=patient["headers"])

    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Test Person"


def test_only_one_profile_row_per_patient(client, patient, db):
    client.get("/patients/me", headers=patient["headers"])
    client.get("/patients/me", headers=patient["headers"])

    assert db.patient_profiles.count_documents({"patient_id": patient["id"]}) == 1


# --- update ---------------------------------------------------------------


def test_profile_updates_persist(client, patient):
    payload = {
        "full_name": "Asha Kulkarni",
        "date_of_birth": "1994-07-11",
        "gender": "female",
        "phone": "+91 98765 43210",
        "address": "12 Model Mill Road, Pune",
        "notes": "Penicillin allergy, reported by me.",
    }

    response = client.patch(
        "/patients/me", json=payload, headers=patient["headers"]
    )

    assert response.status_code == 200, response.text
    for key, value in payload.items():
        assert response.json()[key] == value

    # Re-read rather than trusting the response body: a write that reported
    # success but did not commit is the failure worth catching.
    reread = client.get("/patients/me", headers=patient["headers"]).json()
    for key, value in payload.items():
        assert reread[key] == value


def test_patch_only_writes_the_fields_it_was_sent(client, patient):
    """The whole point of PATCH over PUT: a phone number must not blank a
    name, because the client will never send every field it does not own."""
    client.patch(
        "/patients/me",
        json={"full_name": "Original Name", "date_of_birth": "1990-01-01"},
        headers=patient["headers"],
    )

    response = client.patch(
        "/patients/me", json={"phone": "555-0100"}, headers=patient["headers"]
    )

    assert response.status_code == 200, response.text
    assert response.json()["phone"] == "555-0100"
    assert response.json()["full_name"] == "Original Name"
    assert response.json()["date_of_birth"] == "1990-01-01"


def test_explicit_null_clears_a_field(client, patient):
    client.patch(
        "/patients/me", json={"date_of_birth": "1990-01-01"}, headers=patient["headers"]
    )

    response = client.patch(
        "/patients/me", json={"date_of_birth": None}, headers=patient["headers"]
    )

    assert response.status_code == 200, response.text
    assert response.json()["date_of_birth"] is None


def test_empty_body_is_a_no_op(client, patient):
    client.patch("/patients/me", json={"full_name": "Kept"}, headers=patient["headers"])

    response = client.patch("/patients/me", json={}, headers=patient["headers"])

    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Kept"


def test_changing_the_profile_name_updates_the_account_name(client, patient):
    """One name to the patient.

    The account name is what the topbar shows; the profile name is what they
    typed on the edit screen. Storing both is unavoidable, so they are
    written together rather than allowed to disagree."""
    response = client.patch(
        "/patients/me",
        json={"full_name": "Asha Kulkarni"},
        headers=patient["headers"],
    )
    assert response.status_code == 200, response.text

    account = client.get("/auth/me", headers=patient["headers"]).json()
    assert account["name"] == "Asha Kulkarni"


# --- validation -----------------------------------------------------------


@pytest.mark.parametrize(
    "payload, fragment",
    [
        # Impossible dates pass a plain string check, so they get a real one.
        ({"date_of_birth": "2026-02-30"}, "not a real calendar date"),
        ({"date_of_birth": "11/07/1994"}, "YYYY-MM-DD"),
        ({"date_of_birth": "not-a-date"}, "YYYY-MM-DD"),
        ({"gender": "robot"}, "Gender must be one of"),
        ({"full_name": ""}, "at least 1"),
    ],
)
def test_invalid_profile_values_are_refused(client, patient, payload, fragment):
    response = client.patch(
        "/patients/me", json=payload, headers=patient["headers"]
    )

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert fragment in body["detail"]


def test_a_refused_profile_change_writes_nothing(client, patient):
    original = client.get("/patients/me", headers=patient["headers"]).json()

    client.patch(
        "/patients/me",
        json={"full_name": "Should Not Land", "date_of_birth": "2026-02-30"},
        headers=patient["headers"],
    )

    # The whole payload is discarded, not applied field by field -- otherwise
    # a patient could "fail" a change and still get half of it.
    assert client.get("/patients/me", headers=patient["headers"]).json() == original


def test_over_long_name_is_refused(client, patient):
    response = client.patch(
        "/patients/me",
        json={"full_name": "x" * 121},
        headers=patient["headers"],
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"


# --- authorization --------------------------------------------------------


def test_profile_requires_a_token(client):
    assert client.get("/patients/me").status_code == 401
    assert client.patch("/patients/me", json={"phone": "x"}).status_code == 401


def test_a_garbage_token_is_refused_before_the_database_matters(client, patient):
    response = client.get(
        "/patients/me", headers={"Authorization": "Bearer not.a.token"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_TOKEN"


def test_a_doctor_cannot_reach_the_patient_profile(client, doctor):
    """Being a doctor is not authorization for anything in here.

    The route-level role gate fires first, which is what makes the message
    about the role rather than about record ownership."""
    response = client.get("/patients/me", headers=doctor["headers"])

    assert response.status_code == 403
    assert response.json()["code"] == "ROLE_NOT_ALLOWED"


def test_a_disabled_account_is_refused(client, patient, db):
    db.users.update_one(
        {"email": patient["email"]}, {"$set": {"status": "disabled"}}
    )

    response = client.get("/patients/me", headers=patient["headers"])

    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"
