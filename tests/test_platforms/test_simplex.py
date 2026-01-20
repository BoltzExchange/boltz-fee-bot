"""Tests for SimpleXAdapter with mocked adapter service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from platforms.simplex.adapter import SimpleXAdapter
from platforms.base import IncomingMessage


@pytest.fixture
def simplex_adapter():
    """Create a SimpleXAdapter instance."""
    return SimpleXAdapter(adapter_url="http://localhost:3000")


def test_simplex_adapter_platform_name(simplex_adapter):
    """Test SimpleXAdapter returns correct platform name."""
    assert simplex_adapter.platform_name == "simplex"


def test_simplex_adapter_url(simplex_adapter):
    """Test SimpleXAdapter stores adapter URL correctly."""
    assert simplex_adapter.adapter_url == "http://localhost:3000"
    assert simplex_adapter.adapter_ws_url == "ws://localhost:3000"


def test_simplex_adapter_custom_url():
    """Test SimpleXAdapter with custom adapter URL."""
    adapter = SimpleXAdapter(adapter_url="http://192.168.1.100:9999")
    assert adapter.adapter_url == "http://192.168.1.100:9999"
    assert adapter.adapter_ws_url == "ws://192.168.1.100:9999"


def test_simplex_adapter_register_command(simplex_adapter):
    """Test SimpleXAdapter registers command handlers."""

    async def handler(msg: IncomingMessage):
        pass

    simplex_adapter.register_command("test", handler)
    assert "test" in simplex_adapter._command_handlers


def test_simplex_adapter_register_text_handler(simplex_adapter):
    """Test SimpleXAdapter registers text handler."""

    async def handler(msg: IncomingMessage):
        pass

    simplex_adapter.register_text_handler(handler)
    assert simplex_adapter._text_handler is not None


@pytest.mark.asyncio
async def test_simplex_adapter_send_message_calls_adapter():
    """Test SimpleXAdapter sends messages via HTTP adapter."""
    adapter = SimpleXAdapter(adapter_url="http://localhost:3000")

    # Mock the HTTP client
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    adapter._http_client = mock_client

    await adapter.send_message("123", "Hello!")

    mock_client.post.assert_called_once_with(
        "/send", json={"contactId": 123, "text": "Hello!"}
    )


@pytest.mark.asyncio
async def test_simplex_adapter_send_message_not_connected():
    """Test SimpleXAdapter raises when sending before connect."""
    adapter = SimpleXAdapter(adapter_url="http://localhost:3000")
    # _http_client is None before start()

    with pytest.raises(RuntimeError, match="not connected"):
        await adapter.send_message("contact", "test")


@pytest.mark.asyncio
async def test_simplex_adapter_handles_new_message_event():
    """Test SimpleXAdapter parses incoming message events from adapter."""
    adapter = SimpleXAdapter(adapter_url="http://localhost:3000")

    handler_called = False
    received_message = None

    async def test_handler(msg: IncomingMessage):
        nonlocal handler_called, received_message
        handler_called = True
        received_message = msg

    adapter.register_command("subscribe", test_handler)

    # Simulate adapter event format
    event = {
        "type": "newMessage",
        "contactId": 123,
        "displayName": "Test User",
        "text": "/subscribe",
        "messageId": 456,
    }

    await adapter._handle_event(event)

    assert handler_called
    assert received_message is not None
    assert received_message.text == "/subscribe"
    assert received_message.conversation_id == "123"
    assert received_message.user.platform == "simplex"
    assert received_message.user.display_name == "Test User"


@pytest.mark.asyncio
async def test_simplex_adapter_handles_text_input():
    """Test SimpleXAdapter forwards plain text to text handler."""
    adapter = SimpleXAdapter(adapter_url="http://localhost:3000")

    handler_called = False
    received_message = None

    async def text_handler(msg: IncomingMessage):
        nonlocal handler_called, received_message
        handler_called = True
        received_message = msg

    adapter.register_text_handler(text_handler)

    # Non-command message
    event = {
        "type": "newMessage",
        "contactId": 123,
        "displayName": "Test User",
        "text": "42",
        "messageId": 789,
    }

    await adapter._handle_event(event)

    assert handler_called
    assert received_message is not None
    assert received_message.text == "42"


@pytest.mark.asyncio
async def test_simplex_adapter_handles_contact_connected():
    """Test SimpleXAdapter handles new contact connections."""
    adapter = SimpleXAdapter(adapter_url="http://localhost:3000")

    start_called = False

    async def start_handler(msg: IncomingMessage):
        nonlocal start_called
        start_called = True
        assert msg.conversation_id == "999"

    adapter.register_command("start", start_handler)

    event = {
        "type": "contactConnected",
        "contactId": 999,
        "displayName": "New User",
    }

    await adapter._handle_event(event)

    assert start_called


@pytest.mark.asyncio
async def test_simplex_adapter_ignores_unknown_commands():
    """Test SimpleXAdapter responds to unknown commands."""
    adapter = SimpleXAdapter(adapter_url="http://localhost:3000")

    # Mock send_message
    adapter.send_message = AsyncMock()

    event = {
        "type": "newMessage",
        "contactId": 123,
        "displayName": "User",
        "text": "/unknown_command",
    }

    await adapter._handle_event(event)

    # Should send help message for unknown command
    adapter.send_message.assert_called_once()
    call_args = adapter.send_message.call_args
    assert "Unknown command" in call_args[0][1]


@pytest.mark.asyncio
async def test_simplex_adapter_stop():
    """Test SimpleXAdapter cleanup on stop."""
    adapter = SimpleXAdapter(adapter_url="http://localhost:3000")
    adapter._running = True
    mock_http_client = AsyncMock()
    mock_http_client.aclose = AsyncMock()
    adapter._http_client = mock_http_client
    adapter.ws = AsyncMock()
    adapter.ws.close = AsyncMock()

    await adapter.stop()

    assert not adapter._running
    assert adapter.ws is None
    assert adapter._http_client is None
    mock_http_client.aclose.assert_called_once()
