import decimal
import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from db import (
    db_session,
    get_subscriptions,
    get_subscription,
    remove_subscription,
)

SELECT, ACTION, UPDATE_THRESHOLD = range(3)


async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db_session(context) as session:
        chat_id = update.message.chat_id
        subscriptions = await get_subscriptions(session, chat_id)

        if subscriptions:
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(sub.pretty_string(), callback_data=sub.id)]
                    for sub in subscriptions
                ]
            )
            await update.message.reply_text(
                "You are subscribed to the following fee alerts.",
                reply_markup=keyboard,
            )

            return SELECT
        else:
            await update.message.reply_text("You are not subscribed to any alerts.")

            return ConversationHandler.END


async def select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.chat_data["selection"] = query.data

    await query.edit_message_text("Edit the fee threshold or remove the subscription.")
    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Edit threshold", callback_data="edit"),
                    InlineKeyboardButton("Remove subscription", callback_data="remove"),
                ]
            ]
        )
    )

    return ACTION


async def selected_subscription(
    session: AsyncSession, update: Update, context: ContextTypes.DEFAULT_TYPE
):
    subscription = await get_subscription(session, int(context.chat_data["selection"]))
    if not subscription:
        await update.effective_chat.send_message(
            "Could not get subscription. Try /mysubscriptions again."
        )
    return subscription


async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "edit":
        await query.message.chat.send_message("OK. Send me the new fee threshold.")
        return UPDATE_THRESHOLD
    elif query.data == "remove":
        async with db_session(context) as session:
            subscription = await selected_subscription(session, update, context)
            if subscription:
                await remove_subscription(session, subscription)
                await query.message.chat.send_message("Subscription removed.")
                logging.info(f"Removed: {subscription}")

        return ConversationHandler.END

    return ConversationHandler.END


async def update_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db_session(context) as session:
        subscription = await selected_subscription(session, update, context)
        if subscription:
            try:
                subscription.fee_threshold = Decimal(update.message.text)
            except decimal.InvalidOperation:
                await update.message.reply_text("Invalid threshold. Try again.")
                return UPDATE_THRESHOLD
            await session.commit()
            await update.message.reply_text("Threshold updated.")

    return ConversationHandler.END


entry_point = CommandHandler("mysubscriptions", list_subscriptions)

mysubscriptions_handler = ConversationHandler(
    entry_points=[entry_point],
    states={
        SELECT: [CallbackQueryHandler(select)],
        ACTION: [CallbackQueryHandler(action)],
        UPDATE_THRESHOLD: [MessageHandler(filters.TEXT, update_threshold)],
    },
    fallbacks=[entry_point],
)
