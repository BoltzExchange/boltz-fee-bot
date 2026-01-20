"""Platform-agnostic command logic for subscription management."""

import logging
from decimal import Decimal, InvalidOperation
from typing import Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from consts import Fees, ALL_FEES
from db import (
    Subscription,
    add_subscription,
    get_subscriptions,
    get_subscription,
    remove_subscription,
    remove_all_subscriptions,
    get_previous,
    PLATFORM_TELEGRAM,
    PLATFORM_SIMPLEX,
)
from utils import encode_url_params, get_fee


async def get_available_pairs(
    session: AsyncSession, platform: str, recipient_id: str
) -> Fees:
    """Get available trading pairs not yet subscribed by this user."""
    if platform == PLATFORM_TELEGRAM:
        subscriptions = await get_subscriptions(session, chat_id=int(recipient_id))
    else:
        subscriptions = await get_subscriptions(
            session, platform=platform, platform_chat_id=recipient_id
        )

    fees = await get_previous(session, ALL_FEES)
    if fees is None:
        return {}

    # Filter out already subscribed pairs
    available = dict(fees)
    for subscription in subscriptions:
        if subscription.from_asset in available:
            available[subscription.from_asset].pop(subscription.to_asset, None)
            if len(available[subscription.from_asset]) == 0:
                available.pop(subscription.from_asset)

    return available


async def create_subscription(
    session: AsyncSession,
    platform: str,
    recipient_id: str,
    from_asset: str,
    to_asset: str,
    fee_threshold: str,
) -> tuple[bool, str]:
    """
    Create a new subscription.

    Returns:
        Tuple of (success, message)
    """
    try:
        threshold = Decimal(fee_threshold.strip("%"))
    except InvalidOperation:
        return False, "Invalid threshold value. Please enter a valid number."

    if platform == PLATFORM_TELEGRAM:
        subscription = Subscription(
            platform=platform,
            chat_id=int(recipient_id),
            from_asset=from_asset,
            to_asset=to_asset,
            fee_threshold=threshold,
        )
    else:
        subscription = Subscription(
            platform=platform,
            platform_chat_id=recipient_id,
            from_asset=from_asset,
            to_asset=to_asset,
            fee_threshold=threshold,
        )

    if await add_subscription(session, subscription):
        latest = await get_previous(session, ALL_FEES)
        current_value = get_fee(latest, subscription) if latest else None
        url = encode_url_params(from_asset, to_asset)

        if current_value is not None:
            msg = f"Subscribed to {subscription.pretty_string()}!\nCurrent fees: {current_value}% - {url}"
        else:
            msg = f"Subscribed to {subscription.pretty_string()}!\n{url}"

        logging.info(f"Added: {subscription}")
        return True, msg
    else:
        return False, "You are already subscribed to this pair!"


async def get_user_subscriptions(
    session: AsyncSession, platform: str, recipient_id: str
) -> list[Subscription]:
    """Get all subscriptions for a user on a platform."""
    if platform == PLATFORM_TELEGRAM:
        return await get_subscriptions(session, chat_id=int(recipient_id))
    else:
        return await get_subscriptions(
            session, platform=platform, platform_chat_id=recipient_id
        )


async def update_subscription_threshold(
    session: AsyncSession, subscription_id: int, new_threshold: str
) -> tuple[bool, str]:
    """
    Update a subscription's fee threshold.

    Returns:
        Tuple of (success, message)
    """
    subscription = await get_subscription(session, subscription_id)
    if not subscription:
        return False, "Subscription not found."

    try:
        subscription.fee_threshold = Decimal(new_threshold.strip("%"))
    except InvalidOperation:
        return False, "Invalid threshold value. Please enter a valid number."

    await session.commit()
    return True, "Threshold updated."


async def delete_subscription(session: AsyncSession, subscription_id: int) -> tuple[bool, str]:
    """
    Delete a subscription.

    Returns:
        Tuple of (success, message)
    """
    subscription = await get_subscription(session, subscription_id)
    if not subscription:
        return False, "Subscription not found."

    await remove_subscription(session, subscription)
    logging.info(f"Removed: {subscription}")
    return True, "Subscription removed."


async def delete_all_subscriptions(
    session: AsyncSession, platform: str, recipient_id: str
) -> tuple[bool, str]:
    """
    Delete all subscriptions for a user.

    Returns:
        Tuple of (success, message)
    """
    if platform == PLATFORM_TELEGRAM:
        await remove_all_subscriptions(session, chat_id=int(recipient_id))
    else:
        await remove_all_subscriptions(
            session, platform=platform, platform_chat_id=recipient_id
        )

    logging.info(f"Removed all subscriptions for {platform}:{recipient_id}")
    return True, "Unsubscribed from all fee alerts."
