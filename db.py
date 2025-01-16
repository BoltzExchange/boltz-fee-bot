from sqlalchemy import Column, Integer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Subscriber(Base):
    __tablename__ = "subscribers"
    chat_id = Column(Integer, primary_key=True, unique=True)


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
