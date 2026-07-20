import hmac
import hashlib
import json
import uuid
from typing import Dict, Any
import httpx
from celery import shared_task
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy import select
import asyncio
import logging

from app.core.deps import async_session_factory
from app.models.models import Webhook, WebhookDelivery
from app.crawler.validator import validate_target_url

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
)
async def dispatch_webhook_http(url: str, payload: Dict[str, Any], secret: str):
    await validate_target_url(url)
    
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Rankerpilot-Signature": f"sha256={signature}",
        "User-Agent": "Rankerpilot-Webhook/1.0"
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, content=payload_bytes, headers=headers)
        resp.raise_for_status()
        return resp.status_code

async def async_dispatch_webhook(webhook_id_str: str, payload: dict, event_type: str):
    webhook_id = uuid.UUID(webhook_id_str)
    
    async with async_session_factory() as db:
        webhook = await db.scalar(select(Webhook).where(Webhook.id == webhook_id))
        if not webhook or not webhook.is_active:
            return
            
        delivery = WebhookDelivery(
            id=uuid.uuid4(),
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            status="pending"
        )
        db.add(delivery)
        await db.commit()
        await db.refresh(delivery)
        
        try:
            status_code = await dispatch_webhook_http(webhook.url, payload, webhook.secret)
            delivery.status = "success"
            delivery.response_status = status_code
        except Exception as e:
            delivery.status = "failed"
            delivery.error = str(e)
            
        await db.commit()

@shared_task(bind=True, name="app.workers.webhooks.dispatch_webhook_task")
def dispatch_webhook_task(self, webhook_id_str: str, payload: dict, event_type: str):
    return asyncio.run(async_dispatch_webhook(webhook_id_str, payload, event_type))
