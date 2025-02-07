import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from db import (
    remove_all_subscriptions,
    db_session,
)


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db_session(context) as session:
        chat_id = update.message.chat_id

        if await remove_all_subscriptions(session, chat_id):
            await update.message.reply_text(
                "You have unsubscribed from all fee alerts."
            )
            logging.info(f"Removed all subscriptions from {chat_id=}")
        else:
            await update.message.reply_text("You are not subscribed.")


unsubscribe_handler = CommandHandler("unsubscribe", unsubscribe)
