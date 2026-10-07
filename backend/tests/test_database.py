import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import AsyncSessionLocal, Base, engine, get_db

# Tests run against whatever URL conftest selects (sqlite by default, a real
# postgres instance when DATABASE_URL says so), so never assert one driver.
ASYNC_DRIVERS = {"postgresql+asyncpg", "sqlite+aiosqlite"}


def test_engine_creation():
    """Test SQLAlchemy engine is created"""
    assert engine is not None
    assert engine.url.drivername in ASYNC_DRIVERS


def test_session_factory():
    """Test async session factory is configured"""
    assert AsyncSessionLocal is not None
    session = AsyncSessionLocal()
    assert isinstance(session, AsyncSession)
    # Don't close here, let it be garbage collected


def test_base_metadata():
    """Test declarative base has metadata"""
    assert Base.metadata is not None


@pytest.mark.asyncio
async def test_get_db_dependency():
    """Test get_db dependency yields a session"""
    async for session in get_db():
        assert isinstance(session, AsyncSession)
        # Session will be closed after yield
        break


def test_database_url_from_settings():
    """Test database URL from settings is an async driver URL."""
    from app.core.config import settings

    settings_url = make_url(settings.DATABASE_URL)
    assert settings_url.drivername in ASYNC_DRIVERS
    assert engine.url.drivername == settings_url.drivername
    assert engine.url.database == settings_url.database
