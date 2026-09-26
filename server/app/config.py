"""Application configuration.

All environment-specific values live here so that nothing else in the
codebase reads `os.environ` directly.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# The exact wording shown next to every AI-generated summary. Keeping it as a
# single constant guarantees the disclaimer is never reworded or dropped.
AI_SUMMARY_DISCLAIMER = (
    "AI-generated summary of available records. "
    "Verify important information with the original medical documents."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App -------------------------------------------------------------
    app_name: str = "CAREVERSE API"
    environment: str = "development"
    debug: bool = True

    # --- Database --------------------------------------------------------
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "careverse"

    # --- Auth ------------------------------------------------------------
    jwt_secret_key: str = "change_this_in_development"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- CORS ------------------------------------------------------------
    # Comma-separated in .env, e.g. CORS_ORIGINS=http://localhost:5173
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Storage (Phase 2) ----------------------------------------------
    # "local" for development; "s3" is reserved for the Cloudinary/S3 swap.
    storage_driver: str = "local"
    storage_local_path: str = "storage"
    max_upload_mb: int = 15
    allowed_mime_types: str = "application/pdf"

    # --- AI summarization (Phase 3) -------------------------------------
    # Leave AI_API_KEY empty to run the deterministic mock summarizer.
    ai_provider: str = "mock"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: int = 30

    # --- Password reset (OTP) --------------------------------------------
    # Deliberately short-lived and single-use. The stored record is the only
    # copy of the OTP hash, and a TTL index removes it once it expires.
    otp_length: int = 6
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    reset_token_ttl_minutes: int = 10

    # --- Email ------------------------------------------------------------
    # "mock" prints the OTP to the server log so the flow is testable with no
    # third-party account. It is refused when ENVIRONMENT=production, because
    # logging OTPs in production would hand them to anyone who can read logs.
    # "smtp" sends a real message. "gmail" is reserved for a Gmail API client
    # and is not implemented yet; selecting it fails loudly rather than
    # silently pretending to send.
    email_provider: str = "mock"
    email_from: str = "no-reply@careverse.local"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    # Never committed, never logged. Supplied through the environment only.
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_timeout_seconds: int = 15

    @field_validator("jwt_secret_key")
    @classmethod
    def _reject_default_secret_in_production(cls, value: str, info):
        # pydantic-settings exposes sibling fields through validation context
        environment = (info.data or {}).get("environment", "development")
        if environment == "production" and value == "change_this_in_development":
            raise ValueError(
                "JWT_SECRET_KEY must be set to a real secret when "
                "ENVIRONMENT=production"
            )
        return value

    @field_validator("otp_length")
    @classmethod
    def _validate_otp_length(cls, value: int) -> int:
        # 4-10 digits. Fewer than 4 is trivially guessable even with attempt
        # limits; more than 10 stops being typeable on a phone keyboard.
        if not 4 <= value <= 10:
            raise ValueError("OTP_LENGTH must be between 4 and 10 digits")
        return value

    @field_validator("email_provider")
    @classmethod
    def _validate_email_provider(cls, value: str, info):
        allowed = {"mock", "smtp", "gmail"}
        if value not in allowed:
            raise ValueError(
                f"EMAIL_PROVIDER must be one of {sorted(allowed)}, got '{value}'"
            )

        environment = (info.data or {}).get("environment", "development")
        if environment == "production" and value == "mock":
            # The mock provider writes the OTP into the server log. That is a
            # development convenience and a production vulnerability, so it is
            # refused here rather than left to whoever deploys this.
            raise ValueError(
                "EMAIL_PROVIDER=mock logs OTPs to the server log and is not "
                "allowed when ENVIRONMENT=production. Set EMAIL_PROVIDER=smtp "
                "and provide SMTP credentials."
            )
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_mime_list(self) -> list[str]:
        return [mime.strip() for mime in self.allowed_mime_types.split(",") if mime.strip()]

    @property
    def ai_enabled(self) -> bool:
        """An AI key is present -> use the real provider, else the mock."""
        return bool(self.ai_api_key.strip())

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
