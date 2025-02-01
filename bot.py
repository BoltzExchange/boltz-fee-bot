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
    get_subscribers,
    Base,
    upsert_previous,
    Subscriber,
)
from settings import Settings
from commands.subscribe import subscribe_handler
from utils import encode_url_params

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logging.getLogger("apscheduler").setLevel(logging.WARN)
logging.getLogger("httpx").setLevel(logging.WARN)


def get_fee(fees: Fees, subscriber: Subscriber) -> float | None:
    return fees.get(subscriber.from_asset, {}).get(subscriber.to_asset, None)


async def notify_subscriber(
    bot: Bot,
    subscriber: Subscriber,
    fees: Fees,
):
    from_asset = subscriber.from_asset
    to_asset = subscriber.to_asset

    url = encode_url_params(from_asset, to_asset)
    threshold_msg = (
        f"went below {subscriber.fee_threshold}%"
        if get_fee(fees, subscriber) < subscriber.fee_threshold
        else f"are above {subscriber.fee_threshold}% again"
    )
    message = f"Fees for {from_asset} -> {to_asset} {threshold_msg}: {url}"
    try:
        await bot.send_message(
            chat_id=subscriber.chat_id,
            text=message,
        )
        logging.debug(f"Notification sent to {subscriber.chat_id}")
    except Exception as e:
        logging.error(f"Error notifying subscriber {subscriber.chat_id}: {e}")


def check_subscriber(current: Fees, previous: Fees, subscriber: Subscriber) -> bool:
    fee = get_fee(current, subscriber)
    previous_fee = get_fee(previous, subscriber)
    if fee is None or previous_fee is None:
        return False
    fee_threshold = subscriber.fee_threshold
    below = fee < fee_threshold and previous_fee >= fee_threshold
    above = fee > fee_threshold and previous_fee <= fee_threshold
    return below or above


async def check_fees(session: AsyncSession, current: Fees) -> list[Subscriber]:
    previous = await get_previous(session, ALL_FEES)
    result = []
    if previous:
        result = [
            subscriber
            for subscriber in await get_subscribers(session)
            if check_subscriber(current, previous, subscriber)
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
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            await monitor_fees(app)

        async def post_shutdown(app: Application):
            await client.aclose()

        async def monitor_fees(app: Application):
            current = await get_all_fees(client)
            async with async_session() as session:
                notifications = await check_fees(session, current)
            if len(notifications) > 0:
                logging.info(
                    f"Sending notifications to {len(notifications)} subscribers"
                )
                for subscriber in notifications:
                    await notify_subscriber(app.bot, subscriber, current)

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
