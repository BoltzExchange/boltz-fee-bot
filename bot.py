import logging

import aiohttp
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from settings import Settings

from db import (
    add_subscriber,
    get_previous,
    remove_subscriber,
    get_subscribers,
    Base,
    upsert_previous,
)
from consts import SUBMARINE_SWAP_TYPE, Fees

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def db_session(context: ContextTypes.DEFAULT_TYPE) -> AsyncSession:
    return context.bot_data["session_maker"]()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the boltz pro fee alert bot! Use /subscribe to receive fee updates."
    )


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db_session(context) as session:
        chat_id = update.message.chat_id
        if await add_subscriber(session, chat_id):
            await update.message.reply_text("You have subscribed to fee alerts!")
            logging.info(f"New subscriber added: {chat_id}")
        else:
            await update.message.reply_text("You are already subscribed!")


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db_session(context) as session:
        chat_id = update.message.chat_id

        if await remove_subscriber(session, chat_id):
            await update.message.reply_text("You have unsubscribed from fee alerts.")
            logging.info(f"Subscriber removed: {chat_id}")
        else:
            await update.message.reply_text("You are not subscribed.")


async def notify_subscribers(
    bot: Bot,
    session: AsyncSession,
    swap_type: str,
    from_currency: str,
    to_currency: str,
    fees: float,
):
    subscribers = await get_subscribers(session)
    logging.info(
        f"Notifying {len(subscribers)} subscribers about {from_currency} -> {to_currency} {swap_type} fees"
    )

    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Fees for {swap_type} {from_currency} -> {to_currency} at https://pro.boltz.exchange: {fees}%",
            )
            logging.debug(f"Notification sent to {chat_id}")
        except Exception as e:
            logging.error(f"Error notifying subscriber {chat_id}: {e}")


async def get_fees(api_url: str) -> Fees:
    # TODO: reuse session
    async with aiohttp.ClientSession(base_url=api_url) as session:
        response = await session.get("/v2/swap/submarine", headers={"Referral": "pro"})
        response.raise_for_status()
        data = await response.json()

        fees = {}
        for quote_currency in data:
            fees[quote_currency] = {}
            for base_currency in data[quote_currency]:
                fees[quote_currency][base_currency] = data[quote_currency][
                    base_currency
                ]["fees"]["percentage"]

        return fees


async def check_fees(
    session: AsyncSession,
    bot: Bot,
    fee_threshold: float,
    swap_type: str,
    current: Fees,
    previous: Fees,
):
    for from_currency, pairs in current.items():
        for to_currency, fee in pairs.items():
            if fee == previous.get(from_currency, {}).get(to_currency, 0):
                continue

            if fee < fee_threshold:
                await notify_subscribers(
                    bot,
                    session,
                    swap_type,
                    from_currency,
                    to_currency,
                    fee,
                )


def main():
    try:
        settings = Settings()

        engine = create_async_engine(settings.database_url)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        application = Application.builder().token(settings.telegram_bot_token).build()
        application.bot_data["settings"] = settings
        application.bot_data["session_maker"] = async_session

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("subscribe", subscribe))
        application.add_handler(CommandHandler("unsubscribe", unsubscribe))

        async def post_init(app: Application):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        async def monitor_fees(app: Application):
            current = await get_fees(settings.api_url)

            async with async_session() as session:
                previous = await get_previous(session, SUBMARINE_SWAP_TYPE)

                if previous:
                    await check_fees(
                        session,
                        app.bot,
                        settings.fee_threshold,
                        SUBMARINE_SWAP_TYPE,
                        current,
                        previous,
                    )

                await upsert_previous(session, SUBMARINE_SWAP_TYPE, current)

        application.post_init = post_init
        application.job_queue.run_repeating(
            monitor_fees, interval=settings.check_interval, first=0
        )
        application.run_polling()

    except ValidationError as e:
        logging.error(f"Configuration validation error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
