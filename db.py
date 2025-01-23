from sqlalchemy import Column, Text, JSON, BigInteger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base

from consts import Fees

Base = declarative_base()


class Subscriber(Base):
    __tablename__ = "subscribers"
    chat_id = Column(BigInteger, primary_key=True, unique=True)


async def add_subscriber(session: AsyncSession, chat_id: int) -> bool:
    result = await session.get(Subscriber, chat_id)
    if result:
        return False
    subscriber = Subscriber(chat_id=chat_id)
    session.add(subscriber)
    await session.commit()
    return True


async def remove_subscriber(session: AsyncSession, chat_id: int) -> bool:
    subscriber = await session.get(Subscriber, chat_id)
    if not subscriber:
        return False
    await session.delete(subscriber)
    await session.commit()
    return True


async def get_subscribers(session: AsyncSession) -> list[int]:
    result = (await session.execute(select(Subscriber))).scalars().all()
    return [subscriber.chat_id for subscriber in result]


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
