"""Test fixtures for the password-reset suite.

The environment has to be set up *before* `app.config` is imported, because
`Settings` reads it at import time and is then cached by `lru_cache`. That is
why these assignments sit at module level above every app import, rather than
in a fixture.

A real MongoDB is used rather than a fake. The behaviour under test is
largely about how the service queries and updates documents, and a mock
would only prove the mock behaves as written. The suite points at a separate
`careverse_test` database and never touches development data.
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
