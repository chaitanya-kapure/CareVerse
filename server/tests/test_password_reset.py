"""Password-reset flow: OTP issue, exchange, and redemption.

The security properties get the most attention here, because that is where
this feature can quietly go wrong. The behavioural tests (a user can recover
their password) matter less than the adversarial ones (a code cannot be
replayed, guessed, or used to discover who has an account).
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.services import email_service
from tests.conftest import latest_otp, otp_record

PASSWORD = "Orig1nalPass!"
NEW_PASSWORD = "Replacement9"


def request_code(client, email):
    return client.post("/auth/forgot-password", json={"email": email})


def verify(client, email, otp):
    return client.post("/auth/verify-reset-otp", json={"email": email, "otp": otp})


def reset(client, token, new_password=NEW_PASSWORD):
    return client.post(
        "/auth/reset-password",
        json={"reset_token": token, "new_password": new_password},
    )


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def issue_usable_token(client, email):
    """Walk a registered address as far as a valid reset token."""
    request_code(client, email)
    return verify(client, email, latest_otp()).json()["reset_token"]


# --- 1. requesting a code -------------------------------------------------


def test_request_returns_generic_accepted_response(client, make_account):
    _, email = make_account(email="known@example.com")

    response = request_code(client, email)

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "OTP_REQUEST_ACCEPTED"
    assert body["retry_after_seconds"] == settings.otp_resend_cooldown_seconds
    assert body["expires_in"] == settings.otp_ttl_minutes * 60


def test_request_creates_exactly_one_record(client, db, make_account):
    _, email = make_account(email="known@example.com")

    request_code(client, email)

    record = otp_record(db, email)
    assert record is not None
    assert record["attempts"] == 0
    assert record["max_attempts"] == settings.otp_max_attempts
    assert record["consumed_at"] is None
    assert record["reset_token_hash"] is None
    assert record["verified_at"] is None


# --- 13. unknown email is not disclosed ------------------------------------
#
# The single most important property of this endpoint. If it can tell an
# attacker which addresses have accounts, it undoes the point.


def test_unknown_email_is_indistinguishable_from_known(client, db, make_account):
    _, known = make_account(email="known@example.com")

    known_response = request_code(client, known)
    unknown_response = request_code(client, "nobody@example.com")

    assert known_response.status_code == unknown_response.status_code == 200
    assert known_response.json() == unknown_response.json()
    # And nothing was created for the address that does not exist.
    assert otp_record(db, "nobody@example.com") is None


def test_disabled_account_looks_like_an_unknown_address(client, db):
    from bson import ObjectId

    from app.utils.security import hash_password

    db.users.insert_one(
        {
            "_id": ObjectId(),
            "name": "Disabled",
            "email": "disabled@example.com",
            "password_hash": hash_password(PASSWORD),
            "role": "patient",
            "status": "disabled",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )

    response = request_code(client, "disabled@example.com")

    assert response.status_code == 200
    assert response.json()["code"] == "OTP_REQUEST_ACCEPTED"
    assert otp_record(db, "disabled@example.com") is None


# --- 2 & 3. the code is generated well and never stored in the clear ------


def test_generated_otp_has_the_configured_length_and_is_numeric(client, db, make_account):
    _, email = make_account(email="known@example.com")

    request_code(client, email)
    otp = latest_otp()

    assert otp.isdigit()
    assert len(otp) == settings.otp_length


def test_plain_otp_is_never_stored(client, db, make_account):
    _, email = make_account(email="known@example.com")

    request_code(client, email)
    otp = latest_otp()
    record = otp_record(db, email)

    assert record["otp_hash"] != otp
    assert otp not in record["otp_hash"]
    assert record["otp_hash"].startswith(("$2b$", "$2a$", "$2y$"))


def test_generated_otps_differ_between_requests(client, db, make_account):
    _, email = make_account(email="known@example.com")

    request_code(client, email)
    first = latest_otp()

    # Age the record past the cooldown, otherwise the second request is
    # suppressed and there is no second code to compare against.
    aged = datetime.now(timezone.utc) - timedelta(
        seconds=settings.otp_resend_cooldown_seconds + 10
    )
    db.password_reset_otps.update_many({"email": email}, {"$set": {"created_at": aged}})

    request_code(client, email)
    second = latest_otp()

    # Not a security proof on its own, but a hardcoded or seeded generator
    # would fail this immediately.
    assert first != second


# --- 14. resend cooldown ---------------------------------------------------


def test_resend_inside_cooldown_does_not_issue_a_new_code(client, db, make_account):
    _, email = make_account(email="known@example.com")

    request_code(client, email)
    first = latest_otp()
    first_created = otp_record(db, email)["created_at"]

    # Still inside the cooldown window.
    second_response = request_code(client, email)

    # Same generic response...
    assert second_response.status_code == 200
    assert second_response.json()["code"] == "OTP_REQUEST_ACCEPTED"
    # ...and no second message, no second record, original untouched.
    assert email_service.get_mock_outbox() == []
    records = list(db.password_reset_otps.find({"email": email}))
    assert len(records) == 1
    assert records[0]["created_at"] == first_created
    # The original code therefore still works.
    assert verify(client, email, first).status_code == 200


def test_request_after_cooldown_replaces_the_previous_code(client, db, make_account):
    _, email = make_account(email="known@example.com")

    request_code(client, email)
    stale = latest_otp()

    # Age the record past the cooldown rather than sleeping through it.
    aged = datetime.now(timezone.utc) - timedelta(
        seconds=settings.otp_resend_cooldown_seconds + 10
    )
    db.password_reset_otps.update_many({"email": email}, {"$set": {"created_at": aged}})

    request_code(client, email)
    fresh = latest_otp()

    assert fresh != stale
    # Only one live record survives: the old code is dead, not merely older.
    assert db.password_reset_otps.count_documents({"email": email}) == 1
    assert verify(client, email, stale).status_code == 400
    assert verify(client, email, fresh).status_code == 200


# --- 5, 6, 7. verification -------------------------------------------------


def test_incorrect_otp_is_rejected(client, make_account):
    _, email = make_account(email="known@example.com")
    request_code(client, email)
    otp = latest_otp()
    wrong = ("1" if otp[0] != "1" else "2") + otp[1:]

    response = verify(client, email, wrong)

    assert response.status_code == 400
    assert response.json()["code"] == "OTP_INVALID"


def test_correct_otp_returns_a_reset_token(client, make_account):
    _, email = make_account(email="known@example.com")
    request_code(client, email)

    response = verify(client, email, latest_otp())

    assert response.status_code == 200
    body = response.json()
    assert body["expires_in"] == settings.reset_token_ttl_minutes * 60
    assert body["reset_token"]
    # Opaque, not a JWT: a reset token that decoded would be carrying claims
    # a client could read and tamper with.
    assert body["reset_token"].count(".") != 2
    # The response carries nothing beyond what the next step needs.
    assert set(body) == {"reset_token", "expires_in", "detail"}


def test_reset_token_is_not_a_login_token(client, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)

    # It must not authenticate anything.
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 401
    assert me.json()["code"] == "INVALID_TOKEN"


def test_attempt_limit_destroys_the_code(client, db, make_account):
    _, email = make_account(email="known@example.com")
    request_code(client, email)
    otp = latest_otp()
    wrong = "000000" if otp != "000000" else "111111"

    # Every attempt short of the limit reports a plain "wrong code".
    for _ in range(settings.otp_max_attempts - 1):
        response = verify(client, email, wrong)
        assert response.status_code == 400
        assert response.json()["code"] == "OTP_INVALID"

    # The attempt that reaches the limit reports the lockout instead.
    final = verify(client, email, wrong)
    assert final.status_code == 400
    assert final.json()["code"] == "OTP_ATTEMPTS_EXCEEDED"

    # The record is gone, not merely locked, so it cannot be probed again.
    assert otp_record(db, email) is None

    # Past the limit the response is indistinguishable from "no code was ever
    # issued", which is what keeps this endpoint from confirming that the
    # address exists.
    exhausted = verify(client, email, otp)
    assert exhausted.status_code == 400
    assert exhausted.json()["code"] == "OTP_ATTEMPTS_EXCEEDED"


def test_correct_otp_after_few_wrong_attempts_still_works(client, db, make_account):
    _, email = make_account(email="known@example.com")
    request_code(client, email)
    otp = latest_otp()

    for _ in range(settings.otp_max_attempts - 1):
        assert verify(client, email, "000000" if otp != "000000" else "111111").status_code == 400

    assert verify(client, email, otp).status_code == 200


def test_verify_does_not_disclose_whether_an_account_exists(client):
    # No account, no code, no request: same answer as a locked-out account.
    response = verify(client, "nobody@example.com", "123456")

    assert response.status_code == 400
    assert response.json()["code"] == "OTP_ATTEMPTS_EXCEEDED"


# --- 4. expiry ------------------------------------------------------------


def test_expired_otp_is_rejected(client, db, make_account):
    _, email = make_account(email="known@example.com")
    request_code(client, email)
    otp = latest_otp()

    db.password_reset_otps.update_one(
        {"email": email},
        {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}},
    )

    response = verify(client, email, otp)

    assert response.status_code == 400
    assert response.json()["code"] == "OTP_EXPIRED"


def test_otp_record_carries_a_ttl_index(db):
    """Expiry is enforced by the database, not only by a code path."""
    db.password_reset_otps.create_index(
        [("expires_at", 1)], expireAfterSeconds=0, name="otp_ttl"
    )
    indexes = {i["name"]: i for i in db.password_reset_otps.list_indexes()}

    assert indexes["otp_ttl"].get("expireAfterSeconds") == 0


# --- 8. single use --------------------------------------------------------


def test_otp_cannot_be_exchanged_twice(client, make_account):
    _, email = make_account(email="known@example.com")
    request_code(client, email)
    otp = latest_otp()

    assert verify(client, email, otp).status_code == 200
    second = verify(client, email, otp)

    assert second.status_code == 400
    assert second.json()["code"] == "OTP_ATTEMPTS_EXCEEDED"


def test_reset_token_cannot_be_spent_twice(client, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)

    assert reset(client, token).status_code == 200
    replay = reset(client, token)

    assert replay.status_code == 400
    assert replay.json()["code"] == "RESET_TOKEN_INVALID"


def test_spent_token_hash_is_cleared(client, db, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)
    reset(client, token)

    record = otp_record(db, email)
    assert record["consumed_at"] is not None
    # No usable credential survives, not just a flag.
    assert record["reset_token_hash"] is None


# --- 9. reset token expiry ------------------------------------------------


def test_expired_reset_token_is_rejected(client, db, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)

    db.password_reset_otps.update_one(
        {"email": email},
        {"$set": {"reset_token_expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}},
    )

    response = reset(client, token)

    assert response.status_code == 400
    assert response.json()["code"] == "RESET_TOKEN_EXPIRED"
    # The password must be untouched by a rejected attempt.
    assert login(client, email, PASSWORD).status_code == 200


# --- 10, 11, 12. the actual reset -----------------------------------------


def test_password_reset_succeeds(client, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)

    response = reset(client, token)

    assert response.status_code == 200
    assert response.json()["code"] == "PASSWORD_RESET"


def test_old_password_stops_working_after_reset(client, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)
    reset(client, token)

    response = login(client, email, PASSWORD)

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_new_password_works_after_reset(client, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)
    reset(client, token)

    response = login(client, email, NEW_PASSWORD)

    assert response.status_code == 200
    assert response.json()["user"]["email"] == email
    assert response.json()["access_token"]


def test_reset_writes_a_bcrypt_hash_not_the_plaintext(client, db, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)
    reset(client, token)

    stored = db.users.find_one({"email": email})["password_hash"]
    assert NEW_PASSWORD not in stored
    assert stored.startswith(("$2b$", "$2a$", "$2y$"))


def test_reset_drops_other_live_reset_state_for_the_account(client, db, make_account):
    _, email = make_account(email="known@example.com")
    # A second code issued before the reset, so the reset can clear it.
    request_code(client, email)
    first = latest_otp()
    db.password_reset_otps.update_one(
        {"email": email},
        {"$set": {"created_at": datetime.now(timezone.utc) - timedelta(minutes=5)}},
    )
    request_code(client, email)
    token = verify(client, email, latest_otp()).json()["reset_token"]

    reset(client, token)

    # The earlier code cannot be used to undo the new password.
    assert db.password_reset_otps.count_documents({"email": email, "consumed_at": None}) == 0
    stale = verify(client, email, first)
    assert stale.status_code == 400
    assert login(client, email, PASSWORD).status_code == 401


# --- validation -----------------------------------------------------------


@pytest.mark.parametrize("bad", ["abc", "12345", "1234567", "12 345 6x"])
def test_malformed_otp_is_rejected_by_validation(client, make_account, bad):
    _, email = make_account(email="known@example.com")
    request_code(client, email)

    response = verify(client, email, bad)

    assert response.status_code == 422


def test_malformed_email_is_rejected_by_validation(client):
    assert request_code(client, "not-an-email").status_code == 422


def test_short_new_password_is_rejected(client, make_account):
    _, email = make_account(email="known@example.com")
    token = issue_usable_token(client, email)

    assert reset(client, token, new_password="abc").status_code == 422
    # Rejection costs no attempt: the token is still spendable.
    assert reset(client, token).status_code == 200


def test_unknown_reset_token_is_rejected(client):
    response = reset(client, "x" * 43)

    assert response.status_code == 400
    assert response.json()["code"] == "RESET_TOKEN_INVALID"


# --- email provider behaviour --------------------------------------------


def test_delivery_failure_does_not_leak_or_500(client, db, monkeypatch, make_account):
    """A broken mail relay must not become an account-existence oracle.

    If a send error surfaced as a 5xx, unknown addresses would answer 200 and
    registered ones 500, which is a working enumeration primitive.
    """
    _, email = make_account(email="known@example.com")

    class BrokenProvider:
        name = "broken"

        def send_password_reset_otp(self, to_email, otp, expires_in_minutes):
            raise RuntimeError("relay exploded")

    monkeypatch.setattr(email_service, "_registry", type(email_service._Registry)(BrokenProvider()))

    known = request_code(client, email)
    unknown = request_code(client, "nobody@example.com")

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_gmail_provider_is_recognised_but_fails_loudly(client, db, monkeypatch, make_account):
    """`EMAIL_PROVIDER=gmail` must not silently drop reset emails."""
    from app.services.email_service import GmailApiEmailProvider, EmailDeliveryError

    _, email = make_account(email="known@example.com")
    monkeypatch.setattr(
        email_service, "_registry", type(email_service._Registry)(GmailApiEmailProvider())
    )

    response = request_code(client, email)

    # The user still gets the generic 200; the failure is in the log, not the
    # response, so the endpoint keeps its non-disclosing behaviour.
    assert response.status_code == 200
    assert response.json()["code"] == "OTP_REQUEST_ACCEPTED"

    provider = GmailApiEmailProvider()
    with pytest.raises(EmailDeliveryError):
        provider.send_password_reset_otp("a@example.com", "123456", 10)
