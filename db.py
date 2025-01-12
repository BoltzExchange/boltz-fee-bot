from sqlalchemy import Column, Integer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base

# SQLAlchemy setup
Base = declarative_base()


class Subscriber(Base):
    """
    SQLAlchemy model for the subscribers table.
    """

    __tablename__ = "subscribers"
    chat_id = Column(Integer, primary_key=True, unique=True)


def init_db(database_url: str):
    """
    Initialize the database and create the subscribers table if it doesn't exist.
    """
    engine = create_async_engine(database_url, echo=True)
    # async with engine.begin() as conn:
    #    await conn.run_sync(Base.metadata.create_all)
    return engine


# Database operations
async def add_subscriber(session: AsyncSession, chat_id: int) -> bool:
    """
    Add a subscriber to the database.

    Returns:
        bool: True if the subscriber was added, False if already subscribed.
    """
    result = await session.get(Subscriber, chat_id)
    if result:
        return False
    subscriber = Subscriber(chat_id=chat_id)
    session.add(subscriber)
    await session.commit()
    return True


async def remove_subscriber(session: AsyncSession, chat_id: int) -> bool:
    """
    Remove a subscriber from the database.

    Returns:
        bool: True if the subscriber was removed, False if they were not subscribed.
    """
    subscriber = await session.get(Subscriber, chat_id)
    if not subscriber:
        return False
    await session.delete(subscriber)
    await session.commit()
    return True


async def get_subscribers(session: AsyncSession) -> list[int]:
    """
    Retrieve all subscribers from the database.

    Returns:
        list[int]: A list of chat IDs.
    """

    result = (await session.execute(select(Subscriber))).scalars().all()
    return [subscriber.chat_id for subscriber in result]


