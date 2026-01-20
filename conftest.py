import pytest
import asyncpg
import pytest_asyncio
from decimal import Decimal
from pydantic import ValidationError
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db import Base, Subscription, PLATFORM_TELEGRAM, PLATFORM_SIMPLEX
from settings import DbSettings


@pytest_asyncio.fixture(scope="session")
async def test_db_url():
    try:
        settings = DbSettings()
    except ValidationError:
        settings = DbSettings(
            database_url="postgresql+asyncpg://boltz:boltz@localhost:5433/fees"
        )
    url = make_url(settings.database_url)
    conn = await asyncpg.connect(
        url.set(drivername="postgresql").render_as_string(False)
    )
    test_db = "fees_test"
    await conn.execute(f"DROP DATABASE IF EXISTS {test_db}")
    await conn.execute(f"CREATE DATABASE {test_db}")
    await conn.close()
    return url.set(database=test_db).render_as_string(hide_password=False)


@pytest_asyncio.fixture(scope="session")
async def db_session(test_db_url):
    engine = create_async_engine(test_db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


# Multi-platform test fixtures


@pytest.fixture
def telegram_subscription_factory():
    """Factory for creating Telegram subscription test data."""

    def _create(
        chat_id: int = 123456789,
        from_asset: str = "BTC",
        to_asset: str = "LN",
        fee_threshold: Decimal = Decimal("0.5"),
    ) -> Subscription:
        return Subscription(
            platform=PLATFORM_TELEGRAM,
            chat_id=chat_id,
            platform_chat_id=None,
            from_asset=from_asset,
            to_asset=to_asset,
            fee_threshold=fee_threshold,
        )

    return _create


@pytest.fixture
def simplex_subscription_factory():
    """Factory for creating SimpleX subscription test data."""

    def _create(
        contact_id: str = "contact_abc",
        from_asset: str = "BTC",
        to_asset: str = "LN",
        fee_threshold: Decimal = Decimal("0.5"),
    ) -> Subscription:
        return Subscription(
            platform=PLATFORM_SIMPLEX,
            chat_id=None,
            platform_chat_id=contact_id,
            from_asset=from_asset,
            to_asset=to_asset,
            fee_threshold=fee_threshold,
        )

    return _create


@pytest.fixture
def sample_fees():
    """Sample fee data for testing."""
    return {
        "BTC": {"LN": 0.1, "L-BTC": 0.25, "RBTC": 0.5},
        "LN": {"BTC": 0.15, "L-BTC": 0.3},
        "L-BTC": {"BTC": 0.2, "LN": 0.35, "RBTC": 0.4},
        "RBTC": {"BTC": 0.45, "LN": 0.55, "L-BTC": 0.6},
    }
