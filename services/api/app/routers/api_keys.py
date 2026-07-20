import uuid
import secrets
import hashlib
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import datetime

from app.core.deps import get_db, get_current_org
from app.models.models import Organization, ApiKey

router = APIRouter(prefix="/v1/organizations", tags=["API Keys"])

class ApiKeyCreate(BaseModel):
    name: str

class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    prefix: str
    name: str
    last_used_at: datetime.datetime | None

class ApiKeyCreateResponse(ApiKeyResponse):
    secret_key: str

def hash_secret(secret: str) -> bytes:
    return hashlib.sha256(secret.encode()).digest()

@router.post("/{org_id}/api-keys", response_model=ApiKeyCreateResponse)
async def create_api_key(
    org_id: uuid.UUID,
    data: ApiKeyCreate,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    if org_id != org.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Generate a secure 32-byte secret
    raw_secret = secrets.token_urlsafe(32)
    prefix = raw_secret[:8]
    
    full_key = f"rp_live_{prefix}.{raw_secret[8:]}"
    secret_hash = hash_secret(raw_secret[8:])

    api_key = ApiKey(
        id=uuid.uuid4(),
        org_id=org_id,
        prefix=prefix,
        hash=secret_hash,
        name=data.name
    )
    
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return {
        "id": api_key.id,
        "prefix": api_key.prefix,
        "name": api_key.name,
        "last_used_at": api_key.last_used_at,
        "secret_key": full_key
    }

@router.get("/{org_id}/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    org_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    if org_id != org.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    stmt = select(ApiKey).where(ApiKey.org_id == org_id).order_by(ApiKey.name)
    result = await db.execute(stmt)
    keys = result.scalars().all()

    return keys

@router.delete("/{org_id}/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    if org_id != org.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    api_key = await db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id))
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")

    await db.delete(api_key)
    await db.commit()
