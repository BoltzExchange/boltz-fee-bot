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
)
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
        f"went below {subscription.fee_threshold}%"
        if get_fee(fees, subscription) < subscription.fee_threshold
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


def check_subscription(
    current: Fees, previous: Fees, subscription: Subscription
) -> bool:
    fee = get_fee(current, subscription)
    previous_fee = get_fee(previous, subscription)
    if fee is None or previous_fee is None:
        return False
    fee_threshold = subscription.fee_threshold
    below = fee < fee_threshold and previous_fee >= fee_threshold
    above = fee > fee_threshold and previous_fee <= fee_threshold
    return below or above


async def check_fees(session: AsyncSession, current: Fees) -> list[Subscription]:
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
                notifications = await check_fees(session, current)
            if len(notifications) > 0:
                logging.info(
                    f"Sending notifications to {len(notifications)} subscriptions"
                )
                for subscription in notifications:
                    await notify_subscription(app.bot, subscription, current)

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
