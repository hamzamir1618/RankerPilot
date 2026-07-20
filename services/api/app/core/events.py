import json
import logging
import redis
from app.core.config import settings
from app.core.rate_limit import redis_client
import uuid
from sqlalchemy import select
from app.core.deps import async_session_factory
from app.models.models import Audit, Project, Webhook

logger = logging.getLogger(__name__)

async def publish_event(audit_id: str, event_type: str, payload: dict):
    """
    Publish an event to the Redis PubSub channel for a specific audit.
    The payload must be JSON serializable.
    """
    channel = f"audit_events:{audit_id}"
    message = {
        "type": event_type,
        "audit_id": audit_id,
        **payload
    }
    try:
        await redis_client.publish(channel, json.dumps(message))
    except Exception as e:
        logger.error(f"Failed to publish event {event_type} for audit {audit_id}: {e}")
        
    try:
        await _trigger_webhooks(audit_id, event_type, message)
    except Exception as e:
        logger.error(f"Failed to trigger webhooks for event {event_type}: {e}")

async def _trigger_webhooks(audit_id: str, event_type: str, payload: dict):
    from app.workers.webhooks import dispatch_webhook_task
    async with async_session_factory() as db:
        audit = await db.scalar(select(Audit).where(Audit.id == uuid.UUID(audit_id)))
        if not audit:
            return
        project = await db.scalar(select(Project).where(Project.id == audit.project_id))
        if not project:
            return
        
        result = await db.execute(select(Webhook).where(Webhook.org_id == project.org_id, Webhook.is_active))
        webhooks = result.scalars().all()
        
        for w in webhooks:
            if event_type in w.events or "*" in w.events:
                dispatch_webhook_task.delay(str(w.id), payload, event_type)

# Celery tasks are synchronous by default in Celery.
# We need a synchronous helper to publish events from celery workers if they run synchronously.
# However, celery tasks can run `asyncio.run()` or we can use a sync Redis client.
# Let's provide a synchronous publisher for Celery tasks.


sync_redis_client = redis.from_url(str(settings.REDIS_URL), decode_responses=True)

def publish_event_sync(audit_id: str, event_type: str, payload: dict):
    """Synchronous version for Celery workers."""
    channel = f"audit_events:{audit_id}"
    message = {
        "type": event_type,
        "audit_id": audit_id,
        **payload
    }
    try:
        sync_redis_client.publish(channel, json.dumps(message))
    except Exception as e:
        logger.error(f"Failed to synchronously publish event {event_type} for audit {audit_id}: {e}")
        
    # Also trigger webhooks from sync tasks via an async bridge
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        loop.run_until_complete(_trigger_webhooks(audit_id, event_type, message))
    except Exception as e:
        logger.error(f"Failed to synchronously trigger webhooks: {e}")
