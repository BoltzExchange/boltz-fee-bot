from telethon import TelegramClient
from telethon.sessions import StringSession

from tests.e2e.conftest import Settings

settings = Settings()

with TelegramClient(
    StringSession(), settings.test_api_id, settings.test_api_hash
) as client:
    print("Session string:", client.session.save())
