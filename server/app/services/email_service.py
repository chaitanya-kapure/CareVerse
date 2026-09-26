"""Email delivery, isolated behind a provider interface.

The authentication flow never imports `smtplib` or knows which provider is
configured. It calls `send_password_reset_otp(...)` and gets a boolean. That
is the whole point of the abstraction: switching to a real provider later is
a change to `EMAIL_PROVIDER` in the environment, not an edit to the reset
logic, the controller, or the routes.

Providers
---------
`mock`   Writes the message to the server log and to an in-memory outbox.
         Development only, and `config.py` refuses to start with this
         provider when ENVIRONMENT=production, because the log line is a
         plaintext OTP and logs are not a secret store.
`smtp`   Sends through any SMTP relay. Credentials come from the
         environment and are never logged or returned.
`gmail`  Reserved for a Gmail API client. Not implemented; selecting it
         fails loudly instead of silently dropping the message.

Node note: the original spec suggested Nodemailer. That is a Node library
and this backend is FastAPI, so the equivalent seam is `smtplib` from the
standard library. The interface below is the thing a Nodemailer-backed
implementation would have implemented on the Node side.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised by a provider when a message could not be handed off.

    Carries no recipient detail in its message: it is logged, and the log
    line must not become a way to enumerate accounts.
    """


@dataclass(frozen=True)
class OutgoingEmail:
    """A message the mock provider captured. Test/dev inspection only."""

    to: str
    subject: str
    body: str


class EmailProvider(Protocol):
    name: str

    def send_password_reset_otp(
        self, to_email: str, otp: str, expires_in_minutes: int
    ) -> None:
        ...


def _reset_otp_body(otp: str, expires_in_minutes: int) -> str:
    # No clinical content and no health claims: this is an account-recovery
    # message, so it deliberately does not repeat the medical disclaimer or
    # restate anything about records or summaries.
    return (
        f"Your CAREVERSE verification code is: {otp}\n\n"
        f"It expires in {expires_in_minutes} minutes.\n\n"
        "If you did not ask to reset your password, you can ignore this "
        "message. Nothing has changed on your account.\n\n"
        "This is an automated account message. Please do not reply."
    )


class MockEmailProvider:
    """Development provider: logs the OTP instead of sending it.

    The OTP in the log is the point -- it is what makes this flow testable
    without a mail account. It is also the reason production is refused at
    config validation time, so that convenience can never become a leak.
    """

    name = "mock"

    def __init__(self) -> None:
        self._outbox: list[OutgoingEmail] = []

    def send_password_reset_otp(
        self, to_email: str, otp: str, expires_in_minutes: int
    ) -> None:
        subject = f"Your CAREVERSE verification code: {otp}"
        self._outbox.append(
            OutgoingEmail(to=to_email, subject=subject, body=_reset_otp_body(otp, expires_in_minutes))
        )
        # DEVELOPMENT ONLY -- the log line below contains a live credential.
        # Safe solely because config.py refuses EMAIL_PROVIDER=mock when
        # ENVIRONMENT=production.
        logger.warning(
            "DEVELOPMENT ONLY - password reset OTP for %s: %s (not emailed)",
            to_email,
            otp,
        )

    def drain_outbox(self) -> list[OutgoingEmail]:
        """Return and clear captured messages. Used by the test suite."""
        captured, self._outbox = self._outbox, []
        return captured


class SmtpEmailProvider:
    """Sends through an SMTP relay using stdlib `smtplib`."""

    name = "smtp"

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        use_tls: bool = True,
        timeout: int = 15,
    ) -> None:
        if not host:
            raise EmailDeliveryError("SMTP_HOST must be set when EMAIL_PROVIDER=smtp")
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._use_tls = use_tls
        self._timeout = timeout

    def send_password_reset_otp(
        self, to_email: str, otp: str, expires_in_minutes: int
    ) -> None:
        message = EmailMessage()
        message["Subject"] = "Your CAREVERSE verification code"
        message["From"] = self._sender
        message["To"] = to_email
        message.set_content(_reset_otp_body(otp, expires_in_minutes))

        try:
            if self._port == 465:
                # Implicit TLS; starttls() is not valid on this socket.
                with smtplib.SMTP_SSL(
                    self._host, self._port, timeout=self._timeout, context=ssl.create_default_context()
                ) as smtp:
                    self._authenticate(smtp)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                    smtp.ehlo()
                    if self._use_tls:
                        smtp.starttls(context=ssl.create_default_context())
                        smtp.ehlo()
                    self._authenticate(smtp)
                    smtp.send_message(message)
        except smtplib.SMTPException as exc:
            # The password is never part of this message or the log line.
            raise EmailDeliveryError("SMTP delivery failed") from exc
        except OSError as exc:
            raise EmailDeliveryError("SMTP connection failed") from exc

    def _authenticate(self, smtp: smtplib.SMTP) -> None:
        if self._username:
            smtp.login(self._username, self._password)


class GmailApiEmailProvider:
    """Placeholder for the Gmail API provider.

    The spec allows for Gmail or SMTP. SMTP is implemented and sufficient;
    this exists so that `EMAIL_PROVIDER=gmail` is a recognised, documented
    value rather than an unknown one, and so the wiring point is already in
    place. It raises instead of no-oping, because a silent no-op would mean
    password resets that appear to succeed and never send anything.
    """

    name = "gmail"

    def send_password_reset_otp(
        self, to_email: str, otp: str, expires_in_minutes: int
    ) -> None:
        raise EmailDeliveryError(
            "EMAIL_PROVIDER=gmail is not implemented. Use EMAIL_PROVIDER=smtp, "
            "or implement GmailApiEmailProvider.send_password_reset_otp."
        )


@dataclass
class _Registry:
    """Holds the process-wide provider so a test can swap it."""

    provider: EmailProvider = field(default_factory=MockEmailProvider)


_registry = _Registry()


def build_provider() -> EmailProvider:
    """Construct the provider named by EMAIL_PROVIDER."""
    choice = settings.email_provider.lower()

    if choice == "mock":
        return MockEmailProvider()
    if choice == "smtp":
        return SmtpEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            sender=settings.email_from,
            use_tls=settings.smtp_use_tls,
            timeout=settings.email_timeout_seconds,
        )
    if choice == "gmail":
        return GmailApiEmailProvider()

    # config.py already rejects unknown providers; this is defence in depth
    # for a provider name that arrives some other way.
    raise EmailDeliveryError(f"Unknown EMAIL_PROVIDER '{settings.email_provider}'")


def get_email_provider() -> EmailProvider:
    return _registry.provider


def set_email_provider(provider: EmailProvider) -> None:
    """Override the process-wide provider. Intended for tests."""
    _registry.provider = provider


def reset_email_provider() -> None:
    _registry.provider = build_provider()


def get_mock_outbox() -> list[OutgoingEmail]:
    """Captured mock messages, if the active provider is the mock one.

    Returns an empty list for real providers rather than raising, so a test
    can assert "nothing was emailed" against any configuration.
    """
    provider = _registry.provider
    if isinstance(provider, MockEmailProvider):
        return provider.drain_outbox()
    return []


def send_password_reset_otp(
    to_email: str, otp: str, expires_in_minutes: int
) -> bool:
    """Best-effort delivery. Returns False instead of raising.

    The caller deliberately cannot distinguish "address does not exist" from
    "the mail relay is down". If a send failure propagated as a 5xx, then
    `forgot-password` would return 200 for unknown addresses and 500 for
    real ones, which hands an attacker a working account-enumeration oracle.
    Both paths return 200; the failure is recorded in the server log only.
    """
    try:
        get_email_provider().send_password_reset_otp(
            to_email=to_email, otp=otp, expires_in_minutes=expires_in_minutes
        )
        return True
    except EmailDeliveryError as exc:
        logger.error("Password reset email not delivered: %s", exc)
        return False
    except Exception:  # pragma: no cover - provider bugs must not 500
        logger.exception("Unexpected error delivering password reset email")
        return False
