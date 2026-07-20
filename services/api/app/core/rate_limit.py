import time
import asyncio
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

        # If it's an org-level limiter, we can key off X-Org-Id if present
        org_id = request.headers.get("X-Org-Id")
        identifier = org_id if org_id else ip

        # unique key per route and identifier
        key = f"rate_limit:{request.url.path}:{identifier}"
        
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
limit_org = RateLimiter(requests=100, window=60)
limit_project = RateLimiter(requests=100, window=60)

class TokenBucketRateLimiter:
    """
    Redis-backed token bucket rate limiter for external APIs (like PSI).
    """
    def __init__(self, key: str, capacity: int, fill_rate: float):
        """
        fill_rate: tokens added per second
        """
        self.key = f"token_bucket:{key}"
        self.capacity = capacity
        self.fill_rate = fill_rate

    async def acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Blocks until tokens are acquired or timeout is reached.
        Uses a simple Redis polling mechanism.
        """
        start = time.time()
        while time.time() - start < timeout:
            now = time.time()
            async with redis_client.pipeline(transaction=True) as pipe:
                # We store a hash with 'tokens' and 'last_update'
                pipe.hgetall(self.key)
                results = await pipe.execute()
                
            data = results[0]
            if not data:
                current_tokens = self.capacity
                last_update = now
            else:
                current_tokens = float(data.get("tokens", self.capacity))
                last_update = float(data.get("last_update", now))
                
            # Add tokens based on elapsed time
            elapsed = now - last_update
            current_tokens = min(self.capacity, current_tokens + elapsed * self.fill_rate)
            
            if current_tokens >= tokens:
                current_tokens -= tokens
                async with redis_client.pipeline(transaction=True) as pipe:
                    pipe.hset(self.key, mapping={"tokens": current_tokens, "last_update": now})
                    pipe.expire(self.key, int(self.capacity / self.fill_rate) + 60)
                    await pipe.execute()
                return True
                
            # Wait before trying again
            await asyncio.sleep(0.5)
            
        return False

class RedisCircuitBreaker:
    """
    Redis-backed circuit breaker to prevent cascading failures to external APIs.
    """
    def __init__(self, key: str, failure_threshold: int = 5, cooldown_seconds: int = 60):
        self.key = f"circuit_breaker:{key}"
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

    async def is_open(self) -> bool:
        """Returns True if the circuit is open (should not make requests)."""
        state = await redis_client.get(f"{self.key}:state")
        return state == "open"

    async def record_failure(self):
        """Records a failure and trips the breaker if threshold is met."""
        fails_key = f"{self.key}:failures"
        fails = await redis_client.incr(fails_key)
        if fails == 1:
            await redis_client.expire(fails_key, self.cooldown_seconds)
            
        if fails >= self.failure_threshold:
            # Trip the breaker
            await redis_client.setex(f"{self.key}:state", self.cooldown_seconds, "open")
            # We don't reset fails here so it stays open if more failures happen, 
            # but it will naturally expire.

    async def record_success(self):
        """Records a success, closing the breaker if it was open."""
        await redis_client.delete(f"{self.key}:state")
        await redis_client.delete(f"{self.key}:failures")
