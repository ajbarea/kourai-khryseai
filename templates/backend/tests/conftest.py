"""pytest configuration — async test client, test DB, xdist-safe fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.main import create_app
from app.models import Base, async_session

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/app_test"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine():
    """Create test DB tables once per test session."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncIterator[AsyncSession]:
    """Per-test DB session with automatic rollback."""
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP test client for the FastAPI app."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
