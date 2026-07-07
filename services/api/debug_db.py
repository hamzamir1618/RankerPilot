import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.models import Base

engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5432/rankerpilot_test', echo=True)

async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(run())
