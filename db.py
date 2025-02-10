from sqlalchemy import Column, Text, JSON, BigInteger, delete, DECIMAL
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from telegram.ext import ContextTypes

from consts import Fees

Base = declarative_base()


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    from_asset = Column(Text, nullable=False)
    to_asset = Column(Text, nullable=False)
    fee_threshold = Column(DECIMAL, nullable=False)

    def __str__(self):
        return f"Subscription(chat_id={self.chat_id}, from_asset={self.from_asset}, to_asset={self.to_asset}, fee_threshold={self.fee_threshold})"

    def pretty_string(self):
        return f"{self.from_asset} -> {self.to_asset} below {self.fee_threshold}%"


def db_session(context: ContextTypes.DEFAULT_TYPE) -> AsyncSession:
    return context.bot_data["session_maker"]()


async def add_subscription(session: AsyncSession, subscription: Subscription) -> bool:
    try:
        session.add(subscription)
        await session.commit()
    except IntegrityError:
        return False
    return True


async def remove_all_subscriptions(session: AsyncSession, chat_id: int) -> bool:
    statement = delete(Subscription).where(Subscription.chat_id == chat_id)
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
    session: AsyncSession, chat_id: int = None
) -> list[Subscription]:
    query = select(Subscription)
    if chat_id:
        query = query.where(Subscription.chat_id == chat_id)
    return (await session.execute(query)).scalars().all()


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
