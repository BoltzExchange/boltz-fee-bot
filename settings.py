from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str = Field(
        ..., env="TELEGRAM_BOT_TOKEN", description="Telegram bot token"
    )
    fee_threshold: float = Field(
        0, env="FEE_THRESHOLD", description="Fee threshold for alerts"
    )
    check_interval: int = Field(
        60, env="CHECK_INTERVAL", description="Interval to check API (seconds)"
    )
    api_url: str = Field(
        "https://api.boltz.exchange",
        env="API_URL",
        description="Boltz API URL for submarine swaps",
    )
    database_url: str = Field(
        env="DATABASE_URL",
        description="Database URL for PostgreSQL",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
