import uuid
import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, HttpUrl

from app.core.deps import get_db, get_current_org
from app.models.models import Organization, Webhook
from app.core.rate_limit import limit_org

router = APIRouter(prefix="/v1/organizations", tags=["Webhooks"], dependencies=[Depends(limit_org)])

class WebhookCreate(BaseModel):
    url: HttpUrl
    events: List[str]

class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    secret: str
    events: List[str]
    is_active: bool

@router.post("/{org_id}/webhooks", response_model=WebhookResponse)
async def create_webhook(
    org_id: uuid.UUID,
    data: WebhookCreate,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    if org_id != org.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    url_str = str(data.url)
    from app.crawler.validator import validate_target_url, SSRFViolation
    try:
        await validate_target_url(url_str)
    except SSRFViolation as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook URL: {str(e)}")

    secret = secrets.token_hex(32)

    webhook = Webhook(
        id=uuid.uuid4(),
        org_id=org_id,
        url=url_str,
        secret=secret,
        events=data.events,
        is_active=True
    )
    
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return {
        "id": webhook.id,
        "url": webhook.url,
        "secret": webhook.secret,
        "events": webhook.events,
        "is_active": webhook.is_active
    }

@router.get("/{org_id}/webhooks", response_model=List[WebhookResponse])
async def list_webhooks(
    org_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    if org_id != org.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    stmt = select(Webhook).where(Webhook.org_id == org_id)
    result = await db.execute(stmt)
    webhooks = result.scalars().all()

    return [
        {
            "id": w.id,
            "url": w.url,
            "secret": w.secret,
            "events": w.events,
            "is_active": w.is_active
        } for w in webhooks
    ]

@router.delete("/{org_id}/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    org_id: uuid.UUID,
    webhook_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    if org_id != org.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    webhook = await db.scalar(select(Webhook).where(Webhook.id == webhook_id, Webhook.org_id == org_id))
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await db.delete(webhook)
    await db.commit()
