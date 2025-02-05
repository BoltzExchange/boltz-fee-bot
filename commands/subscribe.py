import decimal
import logging
from decimal import Decimal
from typing import Iterable

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
    filters,
    CallbackQueryHandler,
)

from consts import Fees, ALL_FEES
from db import (
    add_subscription,
    Subscription,
    db_session,
    get_subscriptions,
    get_previous,
)

FROM_ASSET, TO_ASSET, THRESHOLD = range(3)


def inline_keyboard(assets: Iterable[str]):
    rows = [[InlineKeyboardButton(asset, callback_data=asset) for asset in assets]]
    return InlineKeyboardMarkup(rows)


def filter_fees(fees: Fees, subscriptions: list[Subscription]) -> Fees:
    for subscription in subscriptions:
        fees[subscription.from_asset].pop(subscription.to_asset, None)
        if len(fees[subscription.from_asset]) == 0:
            fees.pop(subscription.from_asset)
    return fees


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    async with db_session(context) as session:
        subscriptions = await get_subscriptions(session, update.effective_chat.id)
        fees = await get_previous(session, ALL_FEES)
        context.chat_data["available_pairs"] = filter_fees(fees, subscriptions)
    await update.message.reply_text(
        "Select the send asset for your notifications.",
        reply_markup=inline_keyboard(fees.keys()),
    )

    return FROM_ASSET


async def from_asset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Select the receive asset for your notifications.")
    available = context.chat_data["available_pairs"][query.data]
    await query.edit_message_reply_markup(inline_keyboard(available.keys()))
    context.chat_data["from_asset"] = query.data
    return TO_ASSET


async def to_asset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.edit_message_text(
        "Select a threshold percentage for your notifications. You can also enter your own value.",
    )
    await query.edit_message_reply_markup(
        InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"{value}%", callback_data=value)
                    for value in (0.05, -0.1, -0.15)
                ],
                [InlineKeyboardButton("Custom", callback_data="custom")],
            ]
        )
    )
    context.chat_data["to_asset"] = query.data
    return THRESHOLD


async def save_threshold(
    update: Update, context: ContextTypes.DEFAULT_TYPE, fee_threshold: str
):
    chat = update.effective_chat
    async with db_session(context) as session:
        try:
            subscription = Subscription(
                chat_id=chat.id,
                fee_threshold=Decimal(fee_threshold.strip("%")),
                from_asset=context.chat_data["from_asset"],
                to_asset=context.chat_data["to_asset"],
            )
        except decimal.InvalidOperation:
            await chat.send_message("Invalid threshold value. Please try again.")
            return

        if await add_subscription(session, subscription):
            await chat.send_message(
                "You have subscribed to fee alerts!",
            )
            logging.info(f"New subscription added: {chat.id}")
        else:
            await chat.send_message("You are already subscribed!")


async def threshold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "custom":
        await query.message.chat.send_message(
            "OK. Send me the fee threshold for your notifications."
        )
        return THRESHOLD

    await save_threshold(update, context, query.data.strip("%"))

    return ConversationHandler.END


async def custom_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await save_threshold(update, context, update.message.text)

    return ConversationHandler.END


entry_point = CommandHandler("subscribe", subscribe)

subscribe_handler = ConversationHandler(
    entry_points=[entry_point],
    states={
        FROM_ASSET: [CallbackQueryHandler(from_asset)],
        TO_ASSET: [CallbackQueryHandler(to_asset)],
        THRESHOLD: [
            CallbackQueryHandler(threshold),
            MessageHandler(filters.TEXT, custom_threshold),
        ],
    },
    fallbacks=[entry_point],
)
