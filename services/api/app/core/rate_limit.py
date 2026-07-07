import time
from fastapi import Request, HTTPException
from app.core.config import settings
import redis.asyncio as redis

# We use the configured REDIS_URL from settings
# We'll share a single Redis pool
redis_client = redis.from_url(str(settings.REDIS_URL), decode_responses=True)

class RateLimiter:
    """
    Sliding window rate limiter using Redis.
    """
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window

    async def __call__(self, request: Request):
        # We can key off client IP or X-Forwarded-For
        # For local dev, request.client might be None
        ip = request.client.host if request.client else "127.0.0.1"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()

        # unique key per route and IP
        key = f"rate_limit:{request.url.path}:{ip}"
        
        now = time.time()
        window_start = now - self.window
        
        # Use a Redis pipeline for atomicity
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window)
            results = await pipe.execute()
        
        # zcard result is at index 1
        current_requests = results[1]
        
        if current_requests >= self.requests:
            raise HTTPException(
                status_code=429,
                detail="Too Many Requests",
                headers={"Retry-After": str(self.window)}
            )

# Commonly used rate limiters
limit_login = RateLimiter(requests=10, window=60)
limit_register = RateLimiter(requests=5, window=60)
