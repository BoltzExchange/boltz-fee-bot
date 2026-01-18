import logging

from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from telegram import Bot
from telegram.ext import Application

from api import get_all_fees
from commands.mysubscriptions import mysubscriptions_handler
from commands.start import start_handler
from commands.unsubscribe import unsubscribe_handler
from consts import Fees, ALL_FEES
from db import (
    get_previous,
    upsert_previous,
    Subscription,
    get_subscriptions,
    NtfySubscription,
    get_ntfy_subscriptions,
)
from ntfy import publish as ntfy_publish
from settings import Settings
from commands.subscribe import subscribe_handler
from utils import encode_url_params, get_fee

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logging.getLogger("apscheduler").setLevel(logging.WARN)
logging.getLogger("httpx").setLevel(logging.WARN)


async def notify_subscription(
    bot: Bot,
    subscription: Subscription,
    fees: Fees,
):
    from_asset = subscription.from_asset
    to_asset = subscription.to_asset

    url = encode_url_params(from_asset, to_asset)
    threshold_msg = (
        f"have reached {subscription.fee_threshold}%"
        if get_fee(fees, subscription) <= subscription.fee_threshold
        else f"are above {subscription.fee_threshold}% again"
    )
    message = f"Fees for {from_asset} -> {to_asset} {threshold_msg}: {url}"
    try:
        await bot.send_message(
            chat_id=subscription.chat_id,
            text=message,
        )
        logging.debug(f"Notification sent to {subscription.chat_id}")
    except Exception as e:
        logging.error(f"Error notifying subscription {subscription.chat_id}: {e}")


async def notify_ntfy_subscription(
    client: AsyncClient,
    settings: Settings,
    subscription: NtfySubscription,
    fees: Fees,
):
    from_asset = subscription.from_asset
    to_asset = subscription.to_asset
    current_fee = get_fee(fees, subscription)

    url = encode_url_params(from_asset, to_asset)
    threshold_msg = (
        f"have reached {subscription.fee_threshold}%"
        if current_fee <= subscription.fee_threshold
        else f"are above {subscription.fee_threshold}% again"
    )
    message = f"Fees for {from_asset} -> {to_asset} {threshold_msg}\nCurrent: {current_fee}%\n{url}"
    title = f"Boltz Fee Alert: {from_asset} -> {to_asset}"

    try:
        await ntfy_publish(
            client=client,
            settings=settings,
            topic=subscription.ntfy_topic,
            message=message,
            title=title,
        )
        logging.debug(f"ntfy notification sent to topic '{subscription.ntfy_topic}'")
    except Exception as e:
        logging.error(f"Error notifying ntfy subscription {subscription.ntfy_topic}: {e}")


def check_subscription(
    current: Fees, previous: Fees, subscription: Subscription | NtfySubscription
) -> bool:
    fee = get_fee(current, subscription)
    previous_fee = get_fee(previous, subscription)
    if fee is None or previous_fee is None:
        return False
    fee_threshold = subscription.fee_threshold
    below = fee <= fee_threshold and previous_fee > fee_threshold
    above = fee > fee_threshold and previous_fee <= fee_threshold
    return below or above


async def check_fees(
    session: AsyncSession, current: Fees
) -> tuple[list[Subscription], list[NtfySubscription]]:
    previous = await get_previous(session, ALL_FEES)
    telegram_result = []
    ntfy_result = []

    if previous:
        # Check Telegram subscriptions
        telegram_result = [
            subscription
            for subscription in await get_subscriptions(session)
            if check_subscription(current, previous, subscription)
        ]

        # Check ntfy subscriptions
        ntfy_result = [
            subscription
            for subscription in await get_ntfy_subscriptions(session)
            if check_subscription(current, previous, subscription)
        ]

    await upsert_previous(session, ALL_FEES, current)
    return telegram_result, ntfy_result


def main():
    try:
        settings = Settings()

        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        application = Application.builder().token(settings.telegram_bot_token).build()
        application.bot_data["settings"] = settings
        application.bot_data["session_maker"] = async_session

        application.add_handler(start_handler)
        application.add_handler(mysubscriptions_handler)
        application.add_handler(subscribe_handler)
        application.add_handler(unsubscribe_handler)

        client = AsyncClient(base_url=settings.api_url)

        async def post_init(app: Application):
            await monitor_fees(app)

        async def post_shutdown(app: Application):
            await client.aclose()

        async def monitor_fees(app: Application):
            current = await get_all_fees(client)
            async with async_session() as session:
                telegram_notifications, ntfy_notifications = await check_fees(
                    session, current
                )

            # Send Telegram notifications
            if len(telegram_notifications) > 0:
                logging.info(
                    f"Sending Telegram notifications to {len(telegram_notifications)} subscriptions"
                )
                for subscription in telegram_notifications:
                    await notify_subscription(app.bot, subscription, current)

            # Send ntfy notifications
            if len(ntfy_notifications) > 0:
                logging.info(
                    f"Sending ntfy notifications to {len(ntfy_notifications)} subscriptions"
                )
                for subscription in ntfy_notifications:
                    await notify_ntfy_subscription(
                        client, settings, subscription, current
                    )

        application.post_init = post_init
        application.post_shutdown = post_shutdown
        application.job_queue.run_repeating(
            monitor_fees, interval=settings.check_interval
        )
        application.run_polling()

    except ValidationError as e:
        logging.error(f"Configuration validation error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
