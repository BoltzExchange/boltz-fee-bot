import logging

import aiohttp
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from settings import Settings

from db import init_db, add_subscriber, remove_subscriber, get_subscribers, Base

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


async def notify_subscribers(bot: Bot, session: AsyncSession, fees: float):
    subscribers = await get_subscribers(session)

    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"Alert: Fees are negative! Current value: {fees}",
            )
            logging.info(f"Notification sent to {chat_id}")
        except Exception as e:
            logging.error(f"Error notifying subscriber {chat_id}: {e}")


async def get_fees(api_url: str) -> float:
    # TODO: reuse session
    async with aiohttp.ClientSession(base_url=api_url) as session:
        response = await session.get("/v2/swap/submarine")
        response.raise_for_status()
        data = await response.json()
        fees = data["BTC"]["BTC"]["fees"]["percentage"]
        return fees


def main():
    try:
        settings = Settings()

        engine = init_db(settings.database_url)
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
            previous = app.bot_data.get("fees", current)
            if previous != current and current < settings.fee_threshold:
                async with async_session() as session:
                    await notify_subscribers(app.bot, session, current)
            app.bot_data["fees"] = current

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
