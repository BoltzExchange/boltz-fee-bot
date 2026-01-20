"""Tests for TelegramAdapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from platforms.telegram.adapter import TelegramAdapter
from platforms.base import IncomingMessage


@pytest.fixture
def mock_application():
    """Create a mock Telegram Application."""
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot.send_message = AsyncMock()
    app.bot_data = {}
    app.initialize = AsyncMock()
    app.start = AsyncMock()
    app.stop = AsyncMock()
    app.shutdown = AsyncMock()
    app.updater = MagicMock()
    app.updater.start_polling = AsyncMock()
    app.updater.stop = AsyncMock()
    app.add_handler = MagicMock()
    return app


def test_telegram_adapter_platform_name():
    """Test TelegramAdapter returns correct platform name."""
    adapter = TelegramAdapter(token="test_token")
    assert adapter.platform_name == "telegram"


def test_telegram_adapter_register_command():
    """Test TelegramAdapter registers command handlers."""
    adapter = TelegramAdapter(token="test_token")

    async def handler(msg: IncomingMessage):
        pass

    adapter.register_command("test", handler)
    assert "test" in adapter._command_handlers


def test_telegram_adapter_set_bot_data():
    """Test TelegramAdapter stores bot_data correctly."""
    adapter = TelegramAdapter(token="test_token")
    adapter.set_bot_data("key", "value")
    assert adapter._bot_data["key"] == "value"


@pytest.mark.asyncio
async def test_telegram_adapter_send_message(mock_application):
    """Test TelegramAdapter sends messages correctly."""
    with patch("platforms.telegram.adapter.Application") as MockApp:
        MockApp.builder.return_value.token.return_value.build.return_value = (
            mock_application
        )

        adapter = TelegramAdapter(token="test_token")
        adapter.application = mock_application

        await adapter.send_message("123456789", "Test message")

        mock_application.bot.send_message.assert_called_once_with(
            chat_id=123456789,
            text="Test message",
        )


@pytest.mark.asyncio
async def test_telegram_adapter_send_message_converts_to_int():
    """Test TelegramAdapter converts conversation_id to int for Telegram."""
    mock_bot = AsyncMock()
    mock_app = MagicMock()
    mock_app.bot = mock_bot

    adapter = TelegramAdapter(token="test_token")
    adapter.application = mock_app

    await adapter.send_message("999888777", "Hello")

    mock_bot.send_message.assert_called_once_with(
        chat_id=999888777,  # Should be int, not string
        text="Hello",
    )


@pytest.mark.asyncio
async def test_telegram_adapter_not_started_raises():
    """Test TelegramAdapter raises when sending before start."""
    adapter = TelegramAdapter(token="test_token")

    with pytest.raises(RuntimeError, match="not started"):
        await adapter.send_message("123", "test")
