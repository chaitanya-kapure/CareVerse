"""SMTP email provider: configuration wiring and safe error handling.

Nothing here reaches the network. `smtplib` is replaced with a fake that
records the calls the provider makes, so STARTTLS, authentication and the
sender/recipient headers can be asserted without sending a message -- and
without any real credential appearing in the test source.
"""

import smtplib
import types

import pytest

from app.services import email_service
from app.services.email_service import (
    EmailDeliveryError,
    MockEmailProvider,
    SmtpEmailProvider,
)

RECIPIENT = "patient@example.com"
SENDER = "sender@example.com"
OTP = "654321"


def make_settings(**overrides):
    """A stand-in for `app.config.settings` with only the email fields."""
    base = dict(
        email_provider="smtp",
        email_from=SENDER,
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username=SENDER,
        # Obviously fake. The real password is only ever in the gitignored
        # .env, never in a test. Kept short and spaces-only on purpose so it
        # cannot be mistaken for a real credential by a secret scanner.
        smtp_password="not a real password",
        smtp_use_tls=True,
        email_timeout_seconds=15,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


class FakeSMTP:
    """Records the SMTP conversation instead of performing it."""

    instances: list["FakeSMTP"] = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls_context = context
        self.events: list[str] = []
        self.logins: list[tuple[str, str]] = []
        self.message = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        self.events.append("ehlo")

    def starttls(self, context=None):
        self.events.append("starttls")
        self.tls_context = context

    def login(self, username, password):
        self.events.append("login")
        self.logins.append((username, password))

    def send_message(self, message):
        self.events.append("send")
        self.message = message


class UnreachableSMTP(FakeSMTP):
    def __init__(self, *args, **kwargs):
        raise OSError("connection refused")


class RejectingSMTP(FakeSMTP):
    def login(self, username, password):
        raise smtplib.SMTPAuthenticationError(535, b"authentication failed")


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeSMTP.instances = []
    yield
    FakeSMTP.instances = []


# --- provider selection ---------------------------------------------------


def test_build_provider_selects_smtp_and_not_mock(monkeypatch):
    monkeypatch.setattr(email_service, "settings", make_settings())

    provider = email_service.build_provider()

    assert isinstance(provider, SmtpEmailProvider)
    assert provider.name == "smtp"
    assert not isinstance(provider, MockEmailProvider)


def test_build_provider_rejects_smtp_without_host(monkeypatch):
    monkeypatch.setattr(email_service, "settings", make_settings(smtp_host=""))

    with pytest.raises(EmailDeliveryError):
        email_service.build_provider()


def test_lifespan_activates_the_configured_provider(monkeypatch):
    """The registry defaults to mock; startup must bind the configured one."""
    import asyncio

    from app import main as main_module

    monkeypatch.setattr(main_module.mongo, "connect", lambda: None)
    monkeypatch.setattr(main_module.mongo, "close", lambda: None)
    monkeypatch.setattr(email_service, "settings", make_settings())
    monkeypatch.setattr(email_service._registry, "provider", MockEmailProvider())

    async def run_lifespan():
        async with main_module.lifespan(main_module.app):
            return email_service.get_email_provider().name

    assert asyncio.run(run_lifespan()) == "smtp"


# --- the SMTP conversation ------------------------------------------------


def test_send_uses_starttls_login_from_and_carries_otp(monkeypatch):
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)

    provider = SmtpEmailProvider(
        host="smtp.gmail.com",
        port=587,
        username=SENDER,
        password="not a real password",
        sender=SENDER,
        use_tls=True,
        timeout=15,
    )
    provider.send_password_reset_otp(RECIPIENT, OTP, 10)

    sent = FakeSMTP.instances[0]
    assert (sent.host, sent.port) == ("smtp.gmail.com", 587)
    # STARTTLS happens before authentication and before the message.
    assert sent.events == ["ehlo", "starttls", "ehlo", "login", "send"]
    assert sent.tls_context is not None
    assert sent.logins == [(SENDER, "not a real password")]

    message = sent.message
    assert message["From"] == SENDER
    assert message["To"] == RECIPIENT
    assert message["Subject"] == "Your CAREVERSE verification code"
    assert OTP in message.get_content()


def test_port_465_uses_implicit_tls_without_starttls(monkeypatch):
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSMTP)

    provider = SmtpEmailProvider(
        host="smtp.gmail.com",
        port=465,
        username=SENDER,
        password="not a real password",
        sender=SENDER,
        use_tls=True,
        timeout=15,
    )
    provider.send_password_reset_otp(RECIPIENT, OTP, 10)

    sent = FakeSMTP.instances[0]
    assert "starttls" not in sent.events
    assert sent.tls_context is not None  # SMTP_SSL builds its own context
    assert sent.logins == [(SENDER, "not a real password")]


# --- error handling -------------------------------------------------------


def test_authentication_failure_is_wrapped_without_leaking_password(monkeypatch):
    monkeypatch.setattr(email_service.smtplib, "SMTP", RejectingSMTP)

    provider = SmtpEmailProvider(
        host="smtp.gmail.com",
        port=587,
        username=SENDER,
        password="not a real password",
        sender=SENDER,
        use_tls=True,
        timeout=15,
    )

    with pytest.raises(EmailDeliveryError) as excinfo:
        provider.send_password_reset_otp(RECIPIENT, OTP, 10)

    assert "not a real password" not in str(excinfo.value)


def test_connection_failure_is_wrapped(monkeypatch):
    monkeypatch.setattr(email_service.smtplib, "SMTP", UnreachableSMTP)

    provider = SmtpEmailProvider(
        host="smtp.gmail.com",
        port=587,
        username=SENDER,
        password="not a real password",
        sender=SENDER,
        use_tls=True,
        timeout=15,
    )

    with pytest.raises(EmailDeliveryError):
        provider.send_password_reset_otp(RECIPIENT, OTP, 10)


def test_top_level_send_returns_false_instead_of_raising(monkeypatch):
    class AlwaysFails:
        name = "always-fails"

        def send_password_reset_otp(self, **kwargs):
            raise EmailDeliveryError("SMTP delivery failed")

    # Patching the registry (not the settings) keeps this independent of the
    # environment, and monkeypatch restores the real provider afterwards.
    monkeypatch.setattr(email_service._registry, "provider", AlwaysFails())

    assert (
        email_service.send_password_reset_otp(RECIPIENT, OTP, 10) is False
    )
