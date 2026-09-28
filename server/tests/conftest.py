"""Test fixtures for the password-reset and document-pipeline suites.

The environment has to be set up *before* `app.config` is imported, because
`Settings` reads it at import time and is then cached by `lru_cache`. That is
why these assignments sit at module level above every app import, rather than
in a fixture.

A real MongoDB is used rather than a fake. The behaviour under test is
largely about how the service queries and updates documents, and a mock
would only prove the mock behaves as written. The suite points at a separate
`careverse_test` database and never touches development data.

No test writes into `server/storage/`. File tests are redirected to a
temporary directory by the `storage` fixture, because a suite that drops
medical-looking files into the repository's own storage folder is exactly the
kind of accident this project cannot afford.
"""

import os
import re

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("MONGODB_DB_NAME", "careverse_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-not-used-anywhere-else")
# Prints the OTP into the test output. That is the entire point of the mock
# provider, and it is confined to this process.
os.environ.setdefault("EMAIL_PROVIDER", "mock")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import email_service  # noqa: E402
from app.services import storage as storage_module  # noqa: E402

TEST_DB_NAME = "careverse_test"

# Matches the code line in the message the mock provider composes.
OTP_PATTERN = re.compile(r"verification code is:\s*(\d+)")


@pytest.fixture(scope="session")
def client():
    """A TestClient with the app's lifespan running.

    Entering the context manager is what opens the MongoDB connection and
    creates the indexes, so a test that relies on the TTL index needs this
    rather than a bare `TestClient(app)`.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def db():
    """A clean test database, emptied before and after each test."""
    mongo = MongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True
    )
    database = mongo[TEST_DB_NAME]

    def wipe() -> None:
        for name in database.list_collection_names():
            database[name].delete_many({})

    wipe()
    email_service.reset_email_provider()
    email_service.get_mock_outbox()  # drain anything left over

    yield database

    wipe()
    mongo.close()


@pytest.fixture()
def make_account(client, db):
    """Create a real account through the API.

    Registered through the app rather than inserted directly, so the stored
    password hash is a genuine bcrypt hash produced by the same code path a
    real user goes through.
    """

    def _make(
        email: str = "person@example.com",
        password: str = "Orig1nalPass!",
        role: str = "patient",
    ):
        response = client.post(
            "/auth/register",
            json={"name": "Test Person", "email": email, "password": password, "role": role},
        )
        assert response.status_code == 201, response.text
        return response.json()["id"], email

    return _make


@pytest.fixture(autouse=True)
def storage(tmp_path):
    """Point file storage at a temporary directory for every test.

    Autouse rather than requested per test: a document test that forgets to
    ask for this fixture would otherwise write real PDFs into the
    repository's own `server/storage/documents/`. They are gitignored, so
    nothing could be committed by accident -- but a suite that silently
    leaves files behind in the project's storage directory is still the wrong
    place for them, and forgetting is exactly how that happens.

    `DocumentService` resolves the driver lazily, so installing it here is
    enough -- no code under test needs to know it happened. Resetting
    afterwards matters just as much: a leaked driver would route the *next*
    test's uploads into this test's directory.
    """
    driver = storage_module.LocalStorageDriver(tmp_path / "documents")
    storage_module.set_storage_driver(driver)
    yield driver
    storage_module.reset_storage_driver()


@pytest.fixture()
def login(client):
    """Exchange credentials for the bearer headers every route expects."""

    def _login(email: str, password: str = "Orig1nalPass!") -> dict:
        response = client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login


@pytest.fixture()
def patient(make_account, login):
    """A registered patient with a valid session."""
    user_id, email = make_account(email="owner@example.com", role="patient")
    return {"id": user_id, "email": email, "headers": login(email)}


@pytest.fixture()
def other_patient(make_account, login):
    """A second, unrelated patient -- the cross-tenant adversary."""
    user_id, email = make_account(email="stranger@example.com", role="patient")
    return {"id": user_id, "email": email, "headers": login(email)}


@pytest.fixture()
def doctor(make_account, login):
    user_id, email = make_account(email="doc@example.com", role="doctor")
    return {"id": user_id, "email": email, "headers": login(email)}


# --- helpers --------------------------------------------------------------


def latest_otp() -> str:
    """The code the mock provider 'emailed' most recently.

    Read out of the captured message rather than from the database, because
    the database only ever holds the bcrypt hash -- there is no plaintext
    code anywhere for a test to accidentally read.
    """
    captured = email_service.get_mock_outbox()
    assert captured, "no password reset email was captured by the mock provider"
    match = OTP_PATTERN.search(captured[-1].body)
    assert match, f"could not find a code in the captured message: {captured[-1].body!r}"
    return match.group(1)


def otp_record(db, email: str):
    return db.password_reset_otps.find_one({"email": email.lower()}, sort=[("created_at", -1)])
