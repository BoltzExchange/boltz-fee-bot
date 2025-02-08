# tests/e2e/get_session_string.py

from telethon import TelegramClient
from telethon.sessions import StringSession


api_id = ""
api_hash = ""


with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("Session string:", client.session.save())
