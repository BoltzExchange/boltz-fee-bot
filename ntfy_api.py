"""
REST API for ntfy subscription management.

Run with: uvicorn ntfy_api:app --host 0.0.0.0 --port 8000
"""

import logging
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from consts import ALL_FEES
from db import (
    NtfySubscription,
    add_ntfy_subscription,
    get_ntfy_subscription,
    get_ntfy_subscriptions,
    remove_ntfy_subscription,
    remove_ntfy_subscriptions_by_topic,
    get_previous,
)
from settings import DbSettings
from utils import get_fee

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


class SubscriptionCreate(BaseModel):
    ntfy_topic: str = Field(..., description="The ntfy topic to receive notifications")
    from_asset: str = Field(..., description="Source asset (e.g., BTC, LN)")
    to_asset: str = Field(..., description="Destination asset (e.g., LN, BTC)")
    fee_threshold: Decimal = Field(..., description="Fee threshold percentage")


class SubscriptionResponse(BaseModel):
    id: int
    ntfy_topic: str
    from_asset: str
    to_asset: str
    fee_threshold: Decimal
    current_fee: float | None = None

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str


_async_session: async_sessionmaker | None = None


def get_session_maker() -> async_sessionmaker:
    global _async_session
    if _async_session is None:
        settings = DbSettings()
        engine = create_async_engine(settings.database_url)
        _async_session = async_sessionmaker(engine, expire_on_commit=False)
    return _async_session


async def get_db() -> AsyncSession:
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


app = FastAPI(
    title="Boltz Fee Bot - ntfy API",
    description="REST API for managing ntfy fee alert subscriptions",
    version="1.0.0",
)


@app.post(
    "/ntfy/subscribe",
    response_model=SubscriptionResponse,
    status_code=201,
    summary="Create a new ntfy subscription",
)
async def create_subscription(
    data: SubscriptionCreate,
    session: AsyncSession = Depends(get_db),
):
    subscription = NtfySubscription(
        ntfy_topic=data.ntfy_topic,
        from_asset=data.from_asset.upper(),
        to_asset=data.to_asset.upper(),
        fee_threshold=data.fee_threshold,
    )

    if not await add_ntfy_subscription(session, subscription):
        raise HTTPException(status_code=400, detail="Failed to create subscription")

    # Get current fee for response
    current_fee = None
    fees = await get_previous(session, ALL_FEES)
    if fees:
        current_fee = get_fee(fees, subscription)

    logging.info(f"Created ntfy subscription: {subscription}")

    return SubscriptionResponse(
        id=subscription.id,
        ntfy_topic=subscription.ntfy_topic,
        from_asset=subscription.from_asset,
        to_asset=subscription.to_asset,
        fee_threshold=subscription.fee_threshold,
        current_fee=current_fee,
    )


@app.get(
    "/ntfy/subscriptions",
    response_model=list[SubscriptionResponse],
    summary="List all ntfy subscriptions",
)
async def list_subscriptions(
    ntfy_topic: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    subscriptions = await get_ntfy_subscriptions(session, ntfy_topic)
    fees = await get_previous(session, ALL_FEES)

    return [
        SubscriptionResponse(
            id=sub.id,
            ntfy_topic=sub.ntfy_topic,
            from_asset=sub.from_asset,
            to_asset=sub.to_asset,
            fee_threshold=sub.fee_threshold,
            current_fee=get_fee(fees, sub) if fees else None,
        )
        for sub in subscriptions
    ]


@app.get(
    "/ntfy/subscriptions/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get a specific subscription",
)
async def get_subscription(
    subscription_id: int,
    session: AsyncSession = Depends(get_db),
):
    subscription = await get_ntfy_subscription(session, subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    fees = await get_previous(session, ALL_FEES)
    current_fee = get_fee(fees, subscription) if fees else None

    return SubscriptionResponse(
        id=subscription.id,
        ntfy_topic=subscription.ntfy_topic,
        from_asset=subscription.from_asset,
        to_asset=subscription.to_asset,
        fee_threshold=subscription.fee_threshold,
        current_fee=current_fee,
    )


@app.delete(
    "/ntfy/subscriptions/{subscription_id}",
    response_model=MessageResponse,
    summary="Delete a subscription",
)
async def delete_subscription(
    subscription_id: int,
    session: AsyncSession = Depends(get_db),
):
    subscription = await get_ntfy_subscription(session, subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    await remove_ntfy_subscription(session, subscription)
    logging.info(f"Deleted ntfy subscription: {subscription}")

    return MessageResponse(message="Subscription deleted successfully")


@app.delete(
    "/ntfy/subscriptions/topic/{ntfy_topic}",
    response_model=MessageResponse,
    summary="Delete all subscriptions for a topic",
)
async def delete_subscriptions_by_topic(
    ntfy_topic: str,
    session: AsyncSession = Depends(get_db),
):
    await remove_ntfy_subscriptions_by_topic(session, ntfy_topic)
    logging.info(f"Deleted all ntfy subscriptions for topic: {ntfy_topic}")

    return MessageResponse(
        message=f"All subscriptions for topic '{ntfy_topic}' deleted"
    )


@app.get("/health", summary="Health check")
async def health_check():
    return {"status": "healthy"}
