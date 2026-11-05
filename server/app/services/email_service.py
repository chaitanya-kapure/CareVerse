"""Email delivery, isolated behind a provider interface."""

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised by a provider when a message could not be handed off."""


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
    return (
        f"Your CAREVERSE verification code is: {otp}\n\n"
        f"It expires in {expires_in_minutes} minutes.\n\n"
        "If you did not ask to reset your password, you can ignore this "
        "message. Nothing has changed on your account.\n\n"
        "This is an automated account message. Please do not reply."
    )


class MockEmailProvider:
    """Development provider: logs the OTP instead of sending it."""

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
    """Placeholder for the Gmail API provider."""

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
    """Captured mock messages, if the active provider is the mock one."""
    provider = _registry.provider
    if isinstance(provider, MockEmailProvider):
        return provider.drain_outbox()
    return []


def send_password_reset_otp(
    to_email: str, otp: str, expires_in_minutes: int
) -> bool:
    """Best-effort delivery. Returns False instead of raising."""
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
