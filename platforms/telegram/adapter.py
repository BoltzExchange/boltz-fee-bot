import logging
from typing import Callable, Awaitable

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from platforms.base import (
    BotPlatform,
    PlatformUser,
    IncomingMessage,
    CommandHandler as BaseCommandHandler,
)


class TelegramAdapter(BotPlatform):
    """Telegram platform adapter using python-telegram-bot."""

    def __init__(self, token: str, bot_data: dict | None = None):
        self.token = token
        self.application: Application | None = None
        self._bot_data = bot_data or {}
        self._command_handlers: dict[str, BaseCommandHandler] = {}

    @property
    def platform_name(self) -> str:
        return "telegram"

    @property
    def bot(self) -> Bot:
        """Get the underlying Telegram Bot instance."""
        if self.application is None:
            raise RuntimeError("TelegramAdapter not started")
        return self.application.bot

    async def start(self) -> None:
        """Initialize and start the Telegram bot."""
        self.application = Application.builder().token(self.token).build()

        # Copy bot_data
        for key, value in self._bot_data.items():
            self.application.bot_data[key] = value

        # Register command handlers
        for command, handler in self._command_handlers.items():
            telegram_handler = self._wrap_handler(command, handler)
            self.application.add_handler(CommandHandler(command, telegram_handler))

        # Register any pending native handlers added before start()
        if hasattr(self, "_pending_native_handlers"):
            for native_handler in self._pending_native_handlers:
                self.application.add_handler(native_handler)
            self._pending_native_handlers.clear()

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logging.info("TelegramAdapter started")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logging.info("TelegramAdapter stopped")

    async def send_message(self, conversation_id: str, text: str) -> None:
        """Send a message to a Telegram chat."""
        if self.application is None:
            raise RuntimeError("TelegramAdapter not started")
        await self.application.bot.send_message(
            chat_id=int(conversation_id),
            text=text,
        )

    def register_command(self, command: str, handler: BaseCommandHandler) -> None:
        """Register a command handler."""
        self._command_handlers[command] = handler

    def _wrap_handler(
        self, command: str, handler: BaseCommandHandler
    ) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]:
        """Wrap a platform-agnostic handler into a Telegram handler."""

        async def telegram_handler(
            update: Update, context: ContextTypes.DEFAULT_TYPE
        ) -> None:
            if (
                update.effective_user is None
                or update.message is None
                or update.effective_chat is None
            ):
                return

            user = PlatformUser(
                platform="telegram",
                platform_user_id=str(update.effective_user.id),
                display_name=update.effective_user.full_name,
            )
            message = IncomingMessage(
                user=user,
                text=update.message.text or "",
                conversation_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
            )
            await handler(message)

        return telegram_handler

    def add_native_handler(self, handler) -> None:
        """Add a native python-telegram-bot handler (for complex handlers like ConversationHandler)."""
        if self.application is None:
            # Store for later if not started yet
            if not hasattr(self, "_pending_native_handlers"):
                self._pending_native_handlers = []
            self._pending_native_handlers.append(handler)
        else:
            self.application.add_handler(handler)

    def set_bot_data(self, key: str, value) -> None:
        """Set a value in bot_data."""
        self._bot_data[key] = value
        if self.application:
            self.application.bot_data[key] = value
