from typing import AsyncGenerator, Optional
from contextvars import ContextVar
import uuid
from fastapi import Request, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy import event, select
import jwt
import hashlib

from .config import settings
from app.models.base import Base
from app.models.models import User, Organization, Membership, ApiKey

from sqlalchemy.pool import NullPool

# Using asyncpg via SQLAlchemy async engine
engine = create_async_engine(str(settings.DATABASE_URL), echo=settings.is_dev, poolclass=NullPool)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ContextVar to hold current org_id for isolation
current_org_id: ContextVar[Optional[uuid.UUID]] = ContextVar("current_org_id", default=None)
from sqlalchemy.orm import Session
@event.listens_for(Session, "do_orm_execute")
def _add_org_isolation(execute_state):
    if not execute_state.execution_options.get('include_loader_criteria', True):
        return

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
                    include_aliases=True,
                    track_closure_variables=False
                )
            )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

# Auth schemes
bearer_scheme = HTTPBearer(auto_error=False)
x_org_id_header = APIKeyHeader(name="X-Org-Id", auto_error=False)

async def get_current_user(
    token: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check if this is an API key (rp_live_ prefix)
    if token.credentials.startswith("rp_live_"):
        # API keys do not resolve to a user, they resolve to an org.
        # This dependency is explicitly for user contexts.
        raise HTTPException(status_code=401, detail="API keys cannot be used for user endpoints")

    try:
        payload = jwt.decode(
            token.credentials,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=["HS256"],
            audience="rankerpilot_api",
            issuer="rankerpilot"
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        # Optional: check type
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="TOKEN_EXPIRED")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = uuid.UUID(user_id_str)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
        
    return user

async def get_current_org(
    request: Request,
    token: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_org_id: Optional[str] = Depends(x_org_id_header),
    db: AsyncSession = Depends(get_db)
) -> Organization:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # API Key Path
    if token.credentials.startswith("rp_live_"):
        try:
            prefix, secret = token.credentials.split(".", 1)
            # length checks
            if len(prefix) != 16 or len(secret) < 16:
                raise ValueError()
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid API key format")
            
        key_hash = hashlib.sha256(secret.encode()).digest()
        
        # Bypass org isolation for this query since we are authenticating the org itself
        from sqlalchemy.orm import ExecutionOptions
        
        # We need the API key
        result = await db.execute(
            select(ApiKey)
            .where(ApiKey.prefix == prefix[8:]) # rp_live_ is 8 chars, prefix in DB is 8 chars
            .where(ApiKey.hash == key_hash)
            .execution_options(include_loader_criteria=False)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        # Update last_used_at (could be done in background to avoid blocking, but simple for now)
        from sqlalchemy import update, func
        await db.execute(
            update(ApiKey).where(ApiKey.id == api_key.id).values(last_used_at=func.now())
        )
        await db.commit()
        
        # Get org
        org_result = await db.execute(
            select(Organization).where(Organization.id == api_key.org_id)
            .execution_options(include_loader_criteria=False)
        )
        org = org_result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=401, detail="Organization not found")
            
        current_org_id.set(org.id)
        return org
        
    # JWT Path
    # Authenticate user first
    try:
        user = await get_current_user(token=token, db=db)
    except HTTPException as e:
        raise e

    # Find memberships
    memberships_res = await db.execute(
        select(Membership, Organization)
        .join(Organization, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id)
        .execution_options(include_loader_criteria=False)
    )
    memberships = memberships_res.all()
    
    if not memberships:
        raise HTTPException(status_code=403, detail="User has no organizations")

    selected_org = None
    if x_org_id:
        try:
            target_org_id = uuid.UUID(x_org_id)
            for m, o in memberships:
                if o.id == target_org_id:
                    selected_org = o
                    break
            if not selected_org:
                raise HTTPException(status_code=403, detail="Not a member of requested organization")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Org-Id format")
    else:
        # Default to first membership
        selected_org = memberships[0][1]

    current_org_id.set(selected_org.id)
    return selected_org
