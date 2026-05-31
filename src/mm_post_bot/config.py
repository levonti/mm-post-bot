from cryptography.fernet import Fernet
from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @field_validator("token_encryption_key")
    @classmethod
    def validate_token_encryption_key(cls, value: str) -> str:
        try:
            Fernet(value.encode())
        except (TypeError, ValueError) as exc:
            raise ValueError("TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc
        return value

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
