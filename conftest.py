import asyncpg
import pytest_asyncio
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db import Base
from settings import Settings


@pytest_asyncio.fixture(scope="session")
async def db_session():
    settings = Settings()

    url = make_url(settings.database_url)
    conn = await asyncpg.connect(
        url.set(drivername="postgresql").render_as_string(False)
    )
    test_db = "fees_test"
    await conn.execute(f"DROP DATABASE IF EXISTS {test_db}")
    await conn.execute(f"CREATE DATABASE {test_db}")
    await conn.close()

    engine = create_async_engine(url.set(database=test_db))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
