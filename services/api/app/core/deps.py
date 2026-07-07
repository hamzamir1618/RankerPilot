from typing import AsyncGenerator
from contextvars import ContextVar
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy import event
from .config import settings
from fastapi import Request
from app.models.base import Base

# Using asyncpg via SQLAlchemy async engine
engine = create_async_engine(str(settings.DATABASE_URL), echo=settings.is_dev)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ContextVar to hold current org_id for isolation
current_org_id: ContextVar[uuid.UUID | None] = ContextVar("current_org_id", default=None)

# Hard security requirement: Organization Isolation
# We intercept every ORM query execution. If there's an active org_id in context,
# we apply a with_loader_criteria filter dynamically. This ensures that even if
# the developer forgets to add .filter(Model.org_id == org_id), the query is safely isolated.
@event.listens_for(AsyncSession, "do_orm_execute")
def _add_org_isolation(execute_state):
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.is_relationship_load
    ):
        org_id = current_org_id.get()
        if org_id is not None:
            execute_state.statement = execute_state.statement.options(
                with_loader_criteria(
                    Base,
                    lambda cls: cls.org_id == org_id if hasattr(cls, "org_id") else True,
                    include_aliases=True
                )
            )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

# Placeholders to be wired to actual auth in future prompt
async def get_current_user():
    pass

async def get_current_org(request: Request):
    # This will extract the org from context or token,
    # and set current_org_id.set(org_id)
    pass
