import os
import subprocess
from typing import Optional

import pytest_asyncio
from telethon.tl.custom import Conversation

from telethon import TelegramClient
from telethon.sessions import StringSession

from settings import Settings


@pytest_asyncio.fixture(autouse=True, scope="session")
def bot(test_db_url):
    """Start bot to be tested."""
    os.environ["DATABASE_URL"] = test_db_url
    process = subprocess.Popen(
        ["uv", "run", "bot.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ,
    )
    yield
    process.terminate()
    process.wait()


class TestSettings(Settings):
    test_api_id: int
    test_api_hash: str
    test_api_session: Optional[str]

    class Config:
        env_file = ".env"
        extra = "allow"


@pytest_asyncio.fixture(scope="session")
async def telegram_client():
    """Connect to Telegram user for testing."""
    settings = TestSettings()

    client = TelegramClient(
        StringSession(settings.test_api_session),
        settings.test_api_id,
        settings.test_api_hash,
        sequential_updates=True,
    )
    await client.connect()
    await client.get_me()
    await client.get_dialogs()

    yield client

    await client.disconnect()


@pytest_asyncio.fixture(scope="session")
async def conv(telegram_client: TelegramClient) -> Conversation:
    """Open conversation with the bot."""
    async with telegram_client.conversation(
        "@boltz_fees_bot", timeout=3, max_messages=10000
    ) as conv:
        yield conv
