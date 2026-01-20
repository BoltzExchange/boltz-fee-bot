"""Tests for the notification dispatcher in bot.py."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from db import Subscription, PLATFORM_TELEGRAM, PLATFORM_SIMPLEX
from bot import notify_subscription, check_subscription
from platforms.base import BotPlatform


class MockAdapter(BotPlatform):
    """Mock platform adapter for testing."""

    def __init__(self, name: str):
        self._name = name
        self._send_message_mock = AsyncMock()

    @property
    def platform_name(self) -> str:
        return self._name

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_message(self, conversation_id: str, text: str) -> None:
        await self._send_message_mock(conversation_id, text)

    def register_command(self, command: str, handler) -> None:
        pass


@pytest.fixture
def mock_telegram_adapter():
    return MockAdapter(PLATFORM_TELEGRAM)


@pytest.fixture
def mock_simplex_adapter():
    return MockAdapter(PLATFORM_SIMPLEX)


@pytest.fixture
def telegram_subscription():
    return Subscription(
        id=1,
        platform=PLATFORM_TELEGRAM,
        chat_id=123456789,
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("0.5"),
    )


@pytest.fixture
def simplex_subscription():
    return Subscription(
        id=2,
        platform=PLATFORM_SIMPLEX,
        platform_chat_id="contact_abc",
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("0.5"),
    )


@pytest.fixture
def sample_fees():
    return {"BTC": {"LN": 0.3}}


@pytest.mark.asyncio
async def test_dispatcher_routes_telegram_to_telegram_adapter(
    mock_telegram_adapter, telegram_subscription, sample_fees
):
    """Test Telegram subscriptions route to TelegramAdapter."""
    adapters = {PLATFORM_TELEGRAM: mock_telegram_adapter}

    await notify_subscription(adapters, telegram_subscription, sample_fees)

    mock_telegram_adapter._send_message_mock.assert_called_once()
    call_args = mock_telegram_adapter._send_message_mock.call_args
    assert call_args[0][0] == "123456789"  # conversation_id
    assert "BTC -> LN" in call_args[0][1]  # message contains pair


@pytest.mark.asyncio
async def test_dispatcher_routes_simplex_to_simplex_adapter(
    mock_simplex_adapter, simplex_subscription, sample_fees
):
    """Test SimpleX subscriptions route to SimpleXAdapter."""
    adapters = {PLATFORM_SIMPLEX: mock_simplex_adapter}

    await notify_subscription(adapters, simplex_subscription, sample_fees)

    mock_simplex_adapter._send_message_mock.assert_called_once()
    call_args = mock_simplex_adapter._send_message_mock.call_args
    assert call_args[0][0] == "contact_abc"  # conversation_id
    assert "BTC -> LN" in call_args[0][1]  # message contains pair


@pytest.mark.asyncio
async def test_dispatcher_handles_missing_platform_gracefully(
    mock_telegram_adapter, simplex_subscription, sample_fees, caplog
):
    """Test dispatcher logs warning when platform adapter is missing."""
    adapters = {PLATFORM_TELEGRAM: mock_telegram_adapter}  # No SimpleX adapter

    # Should not raise
    await notify_subscription(adapters, simplex_subscription, sample_fees)

    # Telegram adapter should not be called for SimpleX subscription
    mock_telegram_adapter._send_message_mock.assert_not_called()

    # Should log warning
    assert "No adapter for platform simplex" in caplog.text


@pytest.mark.asyncio
async def test_dispatcher_routes_to_correct_platforms(
    mock_telegram_adapter, mock_simplex_adapter, 
    telegram_subscription, simplex_subscription, sample_fees
):
    """Test multiple subscriptions route to their respective platforms."""
    adapters = {
        PLATFORM_TELEGRAM: mock_telegram_adapter,
        PLATFORM_SIMPLEX: mock_simplex_adapter,
    }

    await notify_subscription(adapters, telegram_subscription, sample_fees)
    await notify_subscription(adapters, simplex_subscription, sample_fees)

    mock_telegram_adapter._send_message_mock.assert_called_once()
    mock_simplex_adapter._send_message_mock.assert_called_once()


@pytest.mark.asyncio
async def test_dispatcher_includes_threshold_reached_message(
    mock_telegram_adapter, sample_fees
):
    """Test notification message indicates threshold reached."""
    subscription = Subscription(
        id=1,
        platform=PLATFORM_TELEGRAM,
        chat_id=123,
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("0.5"),
    )
    adapters = {PLATFORM_TELEGRAM: mock_telegram_adapter}
    fees = {"BTC": {"LN": 0.3}}  # Below threshold

    await notify_subscription(adapters, subscription, fees)

    message = mock_telegram_adapter._send_message_mock.call_args[0][1]
    assert "have reached" in message


@pytest.mark.asyncio
async def test_dispatcher_includes_threshold_exceeded_message(
    mock_telegram_adapter,
):
    """Test notification message indicates threshold exceeded again."""
    subscription = Subscription(
        id=1,
        platform=PLATFORM_TELEGRAM,
        chat_id=123,
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("0.5"),
    )
    adapters = {PLATFORM_TELEGRAM: mock_telegram_adapter}
    fees = {"BTC": {"LN": 0.8}}  # Above threshold

    await notify_subscription(adapters, subscription, fees)

    message = mock_telegram_adapter._send_message_mock.call_args[0][1]
    assert "are above" in message


def test_check_subscription_works_with_telegram():
    """Test check_subscription with Telegram subscription."""
    subscription = Subscription(
        platform=PLATFORM_TELEGRAM,
        chat_id=123,
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("1.0"),
    )
    current = {"BTC": {"LN": 0.8}}
    previous = {"BTC": {"LN": 1.2}}

    result = check_subscription(current, previous, subscription)
    assert result is True


def test_check_subscription_works_with_simplex():
    """Test check_subscription with SimpleX subscription."""
    subscription = Subscription(
        platform=PLATFORM_SIMPLEX,
        platform_chat_id="contact_abc",
        from_asset="BTC",
        to_asset="LN",
        fee_threshold=Decimal("1.0"),
    )
    current = {"BTC": {"LN": 0.8}}
    previous = {"BTC": {"LN": 1.2}}

    result = check_subscription(current, previous, subscription)
    assert result is True
