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
    remove_subscriber,
)

SELECT, ACTION, UPDATE_THRESHOLD = range(3)


async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db_session(context) as session:
        chat_id = update.message.chat_id
        subscriptions = await get_subscriptions(session, chat_id)

        if subscriptions:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            f"{sub.from_asset} -> {sub.to_asset} at {sub.fee_threshold}%",
                            callback_data=f"{sub.from_asset}_{sub.to_asset}",
                        )
                    ]
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
    from_asset, to_asset = context.chat_data["selection"].split("_")
    subscriber = await get_subscription(
        session, update.effective_chat.id, from_asset, to_asset
    )
    if not subscriber:
        await update.effective_chat.send_message(
            "Could not get subscription. Try /mysubscriptions again."
        )
    return subscriber


async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "edit":
        await query.message.chat.send_message("OK. Send me the new fee threshold.")
        return UPDATE_THRESHOLD
    elif query.data == "remove":
        async with db_session(context) as session:
            subscriber = await selected_subscription(session, update, context)
            if subscriber:
                await remove_subscriber(session, subscriber)
                await query.message.chat.send_message("Subscription removed.")

        return ConversationHandler.END

    return ConversationHandler.END


async def update_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with db_session(context) as session:
        subscriber = await selected_subscription(session, update, context)
        if subscriber:
            subscriber.fee_threshold = Decimal(update.message.text)
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
