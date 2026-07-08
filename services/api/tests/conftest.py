import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import uuid

from typing import AsyncGenerator
from app.main import app
from app.core.config import settings
from app.core.deps import get_db, current_org_id
from app.models.base import Base
from app.models import models
from unittest.mock import patch

# Test database URL - override in a real setup to point to a test DB
# Assuming the developer will set this in their local env or CI
TEST_DATABASE_URL = str(settings.DATABASE_URL) + "_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    # Setup tables
    async with engine.begin() as conn:
        # In a real setup, we'd use alembic upgrade head or create_all
        # Since we use postgres specific types (CITEXT) we might need to 
        # ensure extensions are created. For this unit test setup we just rely on create_all
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.drop_all)
        except Exception:
            pass

@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db
    
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
