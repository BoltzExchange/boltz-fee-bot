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


class Settings(DbSettings):
    # Telegram (optional - set to enable Telegram bot)
    telegram_bot_token: str | None = Field(
        None, description="Telegram bot token (set to enable Telegram)"
    )

    # SimpleX (optional - set simplex_enabled=True to enable)
    simplex_enabled: bool = Field(False, description="Enable SimpleX bot")
    simplex_adapter_url: str = Field(
        "http://localhost:3000", description="SimpleX adapter service URL"
    )

    # Common settings
    check_interval: int = Field(60, description="Interval to check API (seconds)")
    api_url: str = Field(
        "https://api.boltz.exchange",
        description="Boltz API URL for submarine swaps",
    )
    database_url: str = Field(
        description="Database URL for PostgreSQL",
    )

    @property
    def telegram_enabled(self) -> bool:
        """Check if Telegram is enabled (token provided and not empty)."""
        return bool(self.telegram_bot_token)
