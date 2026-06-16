from cryptography.fernet import Fernet
from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .i18n import SUPPORTED_LOCALES, normalize_locale


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    mm_url: HttpUrl = Field(..., description="Base Mattermost URL")
    mm_bot_token: str = Field(..., min_length=1, description="Manager bot PAT")
    mm_admins: str = Field(..., min_length=1, description="Comma-separated admin usernames")
    db_url: str = Field(..., min_length=1, description="PostgreSQL DSN")
    token_encryption_key: str = Field(..., min_length=1, description="Fernet key")
    mm_verify_ssl: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    max_event_tasks: int = Field(default=32, ge=1)
    default_locale: str = Field(default="en")
    web_base_url: HttpUrl = Field(default=HttpUrl("http://localhost:8080"))
    web_session_secret: SecretStr = Field(..., min_length=32)
    web_cookie_secure: bool = Field(default=False)
    web_host: str = Field(default="0.0.0.0", min_length=1)
    web_port: int = Field(default=8080, ge=1, le=65535)
    web_login_token_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    web_session_max_age_seconds: int = Field(default=7 * 24 * 60 * 60, ge=300)

    @field_validator("token_encryption_key")
    @classmethod
    def validate_token_encryption_key(cls, value: str) -> str:
        try:
            Fernet(value.encode())
        except (TypeError, ValueError) as exc:
            raise ValueError("TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc
        return value

    @field_validator("web_session_secret", mode="before")
    @classmethod
    def validate_web_session_secret(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            secret = value.get_secret_value()
        elif isinstance(value, str):
            secret = value
        else:
            return value
        if len(secret) < 32:
            raise ValueError("WEB_SESSION_SECRET must be at least 32 characters")
        return value

    @field_validator("default_locale")
    @classmethod
    def validate_default_locale(cls, value: str) -> str:
        locale = normalize_locale(value)
        if locale is None:
            supported = ", ".join(sorted(SUPPORTED_LOCALES))
            raise ValueError(f"DEFAULT_LOCALE must be one of: {supported}")
        return locale

    @property
    def admin_usernames(self) -> list[str]:
        return [u.strip().lstrip("@") for u in self.mm_admins.split(",") if u.strip()]

    @property
    def mm_rest_base(self) -> str:
        return f"{str(self.mm_url).rstrip('/')}/api/v4"

    @property
    def mm_ws_url(self) -> str:
        base = str(self.mm_url).rstrip("/")
        if base.startswith("https://"):
            ws_base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[len("http://") :]
        else:
            ws_base = base
        return f"{ws_base}/api/v4/websocket"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
