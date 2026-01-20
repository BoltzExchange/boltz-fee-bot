from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Awaitable


@dataclass
class PlatformUser:
    """Represents a user on any platform."""

    platform: str  # "telegram", "simplex"
    platform_user_id: str  # Platform-specific ID
    display_name: str | None = None


@dataclass
class IncomingMessage:
    """Normalized incoming message from any platform."""

    user: PlatformUser
    text: str
    conversation_id: str  # Platform-specific conversation/chat ID
    message_id: str | None = None
    reply_to: str | None = None


# Type alias for command handlers
CommandHandler = Callable[[IncomingMessage], Awaitable[None]]


class BotPlatform(ABC):
    """Abstract base class for bot platform adapters."""

    @abstractmethod
    async def start(self) -> None:
        """Start the platform adapter (connect, begin listening)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the platform adapter (disconnect, cleanup)."""
        ...

    @abstractmethod
    async def send_message(self, conversation_id: str, text: str) -> None:
        """Send a text message to the specified conversation."""
        ...

    @abstractmethod
    def register_command(self, command: str, handler: CommandHandler) -> None:
        """Register a handler for a specific command (e.g., 'subscribe')."""
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform identifier (e.g., 'telegram', 'simplex')."""
        ...
