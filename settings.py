from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings


class DbSettings(BaseSettings):
    database_url: str = Field(
        description="Database URL for PostgreSQL",
    )

    model_config = ConfigDict(
        env_file=".env",
        extra="allow",
    )


class NtfySettings(BaseSettings):
    ntfy_base_url: str = Field(
        "https://ntfy.sh",
        description="Base URL for ntfy server",
    )
    ntfy_auth_header: str | None = Field(
        None,
        description="Optional Authorization header for ntfy",
    )
    ntfy_basic_user: str | None = Field(
        None,
        description="Optional basic auth username for ntfy",
    )
    ntfy_basic_pass: str | None = Field(
        None,
        description="Optional basic auth password for ntfy",
    )
    ntfy_default_priority: str | None = Field(
        None,
        description="Default priority for ntfy notifications",
    )


class Settings(DbSettings, NtfySettings):
    telegram_bot_token: str = Field(..., description="Telegram bot token")
    check_interval: int = Field(60, description="Interval to check API (seconds)")
    api_url: str = Field(
        "https://api.boltz.exchange",
        description="Boltz API URL for submarine swaps",
    )
    database_url: str = Field(
        description="Database URL for PostgreSQL",
    )
