"""Multi-platform bot orchestrator for Boltz Pro Fee alerts."""

import asyncio
import logging
import signal

from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api import get_all_fees
from consts import Fees, ALL_FEES
from db import (
    get_previous,
    upsert_previous,
    Subscription,
    get_subscriptions,
    PLATFORM_TELEGRAM,
    PLATFORM_SIMPLEX,
)
from platforms.base import BotPlatform
from settings import Settings
from utils import encode_url_params, get_fee

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logging.getLogger("apscheduler").setLevel(logging.WARN)
logging.getLogger("httpx").setLevel(logging.WARN)
logging.getLogger("websockets").setLevel(logging.WARN)


async def notify_subscription(
    adapters: dict[str, BotPlatform],
    subscription: Subscription,
    fees: Fees,
):
    """Send notification to a subscriber via their platform."""
    platform = subscription.platform
    adapter = adapters.get(platform)

    if adapter is None:
        logging.warning(
            f"No adapter for platform {platform}, skipping subscription {subscription.id}"
        )
        return

    from_asset = subscription.from_asset
    to_asset = subscription.to_asset
    recipient_id = subscription.get_recipient_id()

    url = encode_url_params(from_asset, to_asset)
    threshold_msg = (
        f"have reached {subscription.fee_threshold}%"
        if get_fee(fees, subscription) <= subscription.fee_threshold
        else f"are above {subscription.fee_threshold}% again"
    )
    message = f"Fees for {from_asset} -> {to_asset} {threshold_msg}: {url}"

    try:
        await adapter.send_message(recipient_id, message)
        logging.debug(f"Notification sent to {platform}:{recipient_id}")
    except Exception as e:
        logging.error(
            f"Error notifying subscription {subscription.id} on {platform}: {e}"
        )


def check_subscription(
    current: Fees, previous: Fees, subscription: Subscription
) -> bool:
    """Check if a subscription should be notified based on fee changes."""
    fee = get_fee(current, subscription)
    previous_fee = get_fee(previous, subscription)
    if fee is None or previous_fee is None:
        return False
    fee_threshold = subscription.fee_threshold
    below = fee <= fee_threshold and previous_fee > fee_threshold
    above = fee > fee_threshold and previous_fee <= fee_threshold
    return below or above


async def check_fees(session: AsyncSession, current: Fees) -> list[Subscription]:
    """Check all subscriptions and return those that need notifications."""
    previous = await get_previous(session, ALL_FEES)
    result = []
    if previous:
        result = [
            subscription
            for subscription in await get_subscriptions(session)
            if check_subscription(current, previous, subscription)
        ]
    await upsert_previous(session, ALL_FEES, current)
    return result


async def monitor_fees(
    client: AsyncClient,
    async_session: async_sessionmaker,
    adapters: dict[str, BotPlatform],
):
    """Fetch fees and send notifications for threshold crossings."""
    try:
        current = await get_all_fees(client)
        async with async_session() as session:
            notifications = await check_fees(session, current)

        if len(notifications) > 0:
            logging.info(f"Sending notifications to {len(notifications)} subscriptions")
            for subscription in notifications:
                await notify_subscription(adapters, subscription, current)
    except Exception as e:
        logging.error(f"Error in fee monitoring: {e}")


async def run_multiplatform_bot():
    """Main async entry point for the multi-platform bot."""
    settings = Settings()

    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    client = AsyncClient(base_url=settings.api_url)
    adapters: dict[str, BotPlatform] = {}

    if settings.telegram_enabled:
        from telegram.ext import Application

        from commands.mysubscriptions import mysubscriptions_handler
        from commands.start import start_handler
        from commands.subscribe import subscribe_handler
        from commands.unsubscribe import unsubscribe_handler

        logging.info("Initializing Telegram adapter...")
        application = Application.builder().token(settings.telegram_bot_token).build()
        application.bot_data["settings"] = settings
        application.bot_data["session_maker"] = async_session

        application.add_handler(start_handler)
        application.add_handler(mysubscriptions_handler)
        application.add_handler(subscribe_handler)
        application.add_handler(unsubscribe_handler)

        # Create a wrapper adapter for notifications
        class TelegramNotifyAdapter(BotPlatform):
            def __init__(self, app: Application):
                self._app = app

            @property
            def platform_name(self) -> str:
                return PLATFORM_TELEGRAM

            async def start(self) -> None:
                pass  # Started separately

            async def stop(self) -> None:
                pass  # Stopped separately

            async def send_message(self, conversation_id: str, text: str) -> None:
                await self._app.bot.send_message(
                    chat_id=int(conversation_id), text=text
                )

            def register_command(self, command: str, handler) -> None:
                pass  # Using native handlers

        adapters[PLATFORM_TELEGRAM] = TelegramNotifyAdapter(application)

        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logging.info("Telegram adapter started")

    if settings.simplex_enabled:
        from platforms.simplex.adapter import SimpleXAdapter
        from platforms.simplex.handlers import SimpleXCommandHandlers

        logging.info("Initializing SimpleX adapter...")

        simplex_adapter = SimpleXAdapter(
            adapter_url=settings.simplex_adapter_url,
        )
        simplex_handlers = SimpleXCommandHandlers(simplex_adapter, async_session)
        simplex_handlers.register_all()

        await simplex_adapter.start()
        adapters[PLATFORM_SIMPLEX] = simplex_adapter
        logging.info("SimpleX adapter started")

    if not adapters:
        logging.error(
            "No platform adapters configured! Set TELEGRAM_BOT_TOKEN or SIMPLEX_ENABLED=true"
        )
        await client.aclose()
        return

    logging.info(f"Bot started with platforms: {list(adapters.keys())}")

    # Set up graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler():
        logging.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Run initial fee check
    await monitor_fees(client, async_session, adapters)

    # Main loop with periodic fee monitoring
    try:
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(), timeout=settings.check_interval
                )
            except asyncio.TimeoutError:
                await monitor_fees(client, async_session, adapters)
    finally:
        logging.info("Shutting down...")
        for name, adapter in adapters.items():
            try:
                await adapter.stop()
                logging.info(f"Stopped {name} adapter")
            except Exception as e:
                logging.error(f"Error stopping {name} adapter: {e}")

        # Stop Telegram application if running
        if settings.telegram_enabled:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

        await client.aclose()
        logging.info("Shutdown complete")


def main():
    """Entry point for the bot."""
    try:
        asyncio.run(run_multiplatform_bot())
    except ValidationError as e:
        logging.error(f"Configuration validation error: {e}")
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
