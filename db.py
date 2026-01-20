from sqlalchemy import Column, Text, JSON, BigInteger, delete, DECIMAL
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base
from telegram.ext import ContextTypes

from consts import Fees

Base = declarative_base()

# Platform constants
PLATFORM_TELEGRAM = "telegram"
PLATFORM_SIMPLEX = "simplex"


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False, default=PLATFORM_TELEGRAM)
    chat_id = Column(BigInteger, nullable=True)  # Telegram only
    platform_chat_id = Column(Text, nullable=True)  # Non-Telegram platforms
    from_asset = Column(Text, nullable=False)
    to_asset = Column(Text, nullable=False)
    fee_threshold = Column(DECIMAL, nullable=False)

    def __init__(self, **kwargs):
        # Apply Python-side default for platform if not specified
        if "platform" not in kwargs:
            kwargs["platform"] = PLATFORM_TELEGRAM
        super().__init__(**kwargs)

    def __str__(self):
        recipient = self.get_recipient_id()
        return f"Subscription(platform={self.platform}, recipient={recipient}, from_asset={self.from_asset}, to_asset={self.to_asset}, fee_threshold={self.fee_threshold})"

    def pretty_string(self):
        return f"{self.from_asset} -> {self.to_asset} at {self.fee_threshold}%"

    def get_recipient_id(self) -> str:
        """Returns the appropriate ID for sending messages on this platform."""
        if self.platform == PLATFORM_TELEGRAM:
            return str(self.chat_id)
        return self.platform_chat_id or ""


def db_session(context: ContextTypes.DEFAULT_TYPE) -> AsyncSession:
    return context.bot_data["session_maker"]()


async def add_subscription(session: AsyncSession, subscription: Subscription) -> bool:
    try:
        session.add(subscription)
        await session.commit()
    except IntegrityError:
        return False
    return True


async def remove_all_subscriptions(
    session: AsyncSession,
    chat_id: int | None = None,
    platform: str | None = None,
    platform_chat_id: str | None = None,
) -> bool:
    """Remove all subscriptions for a user.

    For Telegram: pass chat_id
    For other platforms: pass platform and platform_chat_id
    """
    if chat_id is not None:
        statement = delete(Subscription).where(Subscription.chat_id == chat_id)
    elif platform and platform_chat_id:
        statement = delete(Subscription).where(
            Subscription.platform == platform,
            Subscription.platform_chat_id == platform_chat_id,
        )
    else:
        return False

    await session.execute(statement)
    await session.commit()
    return True


async def remove_subscription(session: AsyncSession, subscription: Subscription):
    await session.delete(subscription)
    await session.commit()


async def get_subscription(
    session: AsyncSession, subscription_id: int
) -> Subscription | None:
    return await session.get(Subscription, subscription_id)


async def get_subscriptions(
    session: AsyncSession,
    chat_id: int | None = None,
    platform: str | None = None,
    platform_chat_id: str | None = None,
) -> list[Subscription]:
    """Get subscriptions, optionally filtered by user.

    For Telegram: pass chat_id
    For other platforms: pass platform and platform_chat_id
    No args: returns all subscriptions
    """
    query = select(Subscription)
    if chat_id is not None:
        query = query.where(Subscription.chat_id == chat_id)
    elif platform and platform_chat_id:
        query = query.where(
            Subscription.platform == platform,
            Subscription.platform_chat_id == platform_chat_id,
        )
    return list((await session.execute(query)).scalars().all())


class Previous(Base):
    __tablename__ = "previous"
    key = Column(Text, primary_key=True)
    value = Column(JSON)


async def upsert_previous(session: AsyncSession, key: str, value: Fees) -> None:
    previous = await session.get(Previous, key)
    if previous:
        previous.value = value
    else:
        previous = Previous(key=key, value=value)
        session.add(previous)

    await session.commit()


async def get_previous(session: AsyncSession, key: str) -> Fees | None:
    result = await session.get(Previous, key)
    if not result:
        return None
    return result.value  # type: ignore
