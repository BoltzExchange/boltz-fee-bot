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
from utils import encode_url_params, get_fee

FROM_ASSET, TO_ASSET, THRESHOLD, CUSTOM_THRESHOLD = range(4)

ASSET_PREFIX = "asset_"
ASSET_PATTERN = rf"^{ASSET_PREFIX}.+$"


def remove_asset_prefix(asset: str) -> str:
    return asset.replace(ASSET_PREFIX, "")


def inline_keyboard(assets: Iterable[str]):
    rows = [
        [
            InlineKeyboardButton(asset, callback_data=ASSET_PREFIX + asset)
            for asset in assets
        ]
    ]
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
    asset = remove_asset_prefix(query.data)
    available = context.chat_data["available_pairs"][asset]
    await query.edit_message_text(
        "Select the receive asset for your notifications.",
        reply_markup=inline_keyboard(available.keys()),
    )
    context.chat_data["from_asset"] = asset
    return TO_ASSET


async def to_asset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Select a threshold percentage for your notifications. You can also enter your own value.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"{value}%", callback_data=value)
                    for value in (0.05, -0.1, -0.15)
                ],
                [InlineKeyboardButton("Custom", callback_data="custom")],
            ]
        ),
    )
    context.chat_data["to_asset"] = remove_asset_prefix(query.data)
    return THRESHOLD


async def save_threshold(
    update: Update, context: ContextTypes.DEFAULT_TYPE, fee_threshold: str
) -> int | None:
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
            latest = await get_previous(session, ALL_FEES)
            current_value = get_fee(latest, subscription)
            url = encode_url_params(subscription.from_asset, subscription.to_asset)
            await chat.send_message(
                f"You have subscribed to fee alerts for *{subscription.pretty_string()}*!\nCurrent fees: [{current_value}%]({url})",
                parse_mode="markdown",
            )
            logging.info(f"Added: {subscription}")
        else:
            await chat.send_message("You are already subscribed!")
        return ConversationHandler.END


async def threshold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "custom":
        await query.message.chat.send_message(
            "OK. Send me the fee threshold for your notifications."
        )
        return CUSTOM_THRESHOLD

    return await save_threshold(update, context, query.data)


async def custom_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await save_threshold(update, context, update.message.text)


entry_point = CommandHandler("subscribe", subscribe)


subscribe_handler = ConversationHandler(
    entry_points=[entry_point],
    states={
        FROM_ASSET: [CallbackQueryHandler(from_asset, pattern=ASSET_PATTERN)],
        TO_ASSET: [CallbackQueryHandler(to_asset, pattern=ASSET_PATTERN)],
        THRESHOLD: [CallbackQueryHandler(threshold, pattern=r"^(custom|-?\d*\.?\d+)$")],
        CUSTOM_THRESHOLD: [MessageHandler(filters.TEXT, custom_threshold)],
    },
    fallbacks=[entry_point],
)
