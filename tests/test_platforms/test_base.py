"""Tests for the abstract BotPlatform interface."""

import pytest
from platforms.base import BotPlatform, PlatformUser, IncomingMessage


def test_platform_user_creation():
    """Test PlatformUser dataclass creation."""
    user = PlatformUser(
        platform="telegram",
        platform_user_id="123456",
        display_name="Test User",
    )
    assert user.platform == "telegram"
    assert user.platform_user_id == "123456"
    assert user.display_name == "Test User"


def test_platform_user_optional_display_name():
    """Test PlatformUser with optional display_name."""
    user = PlatformUser(platform="simplex", platform_user_id="abc123")
    assert user.display_name is None


def test_incoming_message_creation():
    """Test IncomingMessage dataclass creation."""
    user = PlatformUser(platform="telegram", platform_user_id="123")
    message = IncomingMessage(
        user=user,
        text="/subscribe",
        conversation_id="456",
        message_id="789",
        reply_to=None,
    )
    assert message.user == user
    assert message.text == "/subscribe"
    assert message.conversation_id == "456"
    assert message.message_id == "789"
    assert message.reply_to is None


def test_bot_platform_is_abstract():
    """Verify BotPlatform cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BotPlatform()
