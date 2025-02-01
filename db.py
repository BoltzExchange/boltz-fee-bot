from sqlalchemy import Column, Text, JSON, BigInteger, delete, DECIMAL
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from telegram.ext import ContextTypes

from consts import Fees

Base = declarative_base()


class Subscriber(Base):
    __tablename__ = "subscribers"
    chat_id = Column(BigInteger, primary_key=True)
    from_asset = Column(Text, primary_key=True)
    to_asset = Column(Text, primary_key=True)
    fee_threshold: float = Column(DECIMAL)


def db_session(context: ContextTypes.DEFAULT_TYPE) -> AsyncSession:
    return context.bot_data["session_maker"]()


async def add_subscriber(session: AsyncSession, subscriber: Subscriber) -> bool:
    try:
        session.add(subscriber)
        await session.commit()
    except IntegrityError:
        return False
    return True


async def remove_all_subscriptions(session: AsyncSession, chat_id: int) -> bool:
    statement = delete(Subscriber).where(Subscriber.chat_id == chat_id)
    await session.execute(statement)
    await session.commit()
    return True


async def remove_subscriber(session: AsyncSession, subscriber: Subscriber):
    await session.delete(subscriber)
    await session.commit()


# async def get_subscriber(
#        session: AsyncSession, from_asset: str, to_asset: str
# ) -> Subscriber:


async def get_subscriptions(
    session: AsyncSession, chat_id: int
) -> list[Subscriber] | None:
    query = select(Subscriber).where(Subscriber.chat_id == chat_id)
    return (await session.execute(query)).scalars().all()


async def get_subscription(
    session: AsyncSession, chat_id: int, from_asset: str, to_asset: str
) -> Subscriber | None:
    return await session.get(Subscriber, (chat_id, from_asset, to_asset))


async def get_subscribers(session: AsyncSession) -> list[Subscriber]:
    query = select(Subscriber)
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
