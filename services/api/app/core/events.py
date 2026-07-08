import json
import logging
import redis
from app.core.config import settings
from app.core.rate_limit import redis_client

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
