from pydantic import Field, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., description="Telegram bot token")
    check_interval: int = Field(60, description="Interval to check API (seconds)")
    api_url: str = Field(
        "https://api.boltz.exchange",
        description="Boltz API URL for submarine swaps",
    )
    database_url: str = Field(
        description="Database URL for PostgreSQL",
    )

    model_config = ConfigDict(
        env_file=".env",
        extra="allow",
    )
