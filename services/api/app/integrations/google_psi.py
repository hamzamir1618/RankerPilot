import logging
import hashlib
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from app.core.config import settings
from app.core.rate_limit import TokenBucketRateLimiter, RedisCircuitBreaker, redis_client

logger = logging.getLogger(__name__)

# 240 requests per minute = 4 req/sec
psi_limiter = TokenBucketRateLimiter("google_psi", capacity=240, fill_rate=4.0)
psi_breaker = RedisCircuitBreaker("google_psi", failure_threshold=5, cooldown_seconds=60)

PSI_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CACHE_TTL = 6 * 60 * 60  # 6 hours

class GoogleAPIError(Exception):
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, GoogleAPIError)),
    reraise=True
)
async def fetch_psi_data(url: str, strategy: str = "mobile") -> dict | None:
    """
    Fetches PSI data for a given URL and strategy.
    Implements Redis caching, rate limiting, retries, and circuit breaking.
    """
    if await psi_breaker.is_open():
        logger.warning(f"PSI circuit breaker is open. Skipping PSI call for {url}")
        return None

    api_key = settings.PSI_API_KEY.get_secret_value() if settings.PSI_API_KEY else ""
    
    # Hash for cache key to avoid exposing URL/Key in cleartext if desired,
    # though URL is fine. We'll hash the combination.
    hash_str = f"{url}:{strategy}:{api_key[:5]}"
    cache_key = f"psi_cache:{hashlib.md5(hash_str.encode()).hexdigest()}"
    
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Acquire rate limit token
    if not await psi_limiter.acquire(tokens=1, timeout=30.0):
        logger.warning(f"Failed to acquire PSI rate limit token for {url}")
        return None

    params = {
        "url": url,
        "strategy": strategy,
        "category": ["performance", "accessibility", "best-practices", "seo"]
    }
    if api_key:
        params["key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(PSI_API_URL, params=params)
            resp.raise_for_status()
            
        data = resp.json()
        await psi_breaker.record_success()
        
        # Cache the result
        await redis_client.setex(cache_key, CACHE_TTL, json.dumps(data))
        return data
        
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in (429, 500, 502, 503, 504):
            await psi_breaker.record_failure()
            logger.error(f"PSI HTTP Error {status} for {url}. Tripping breaker check.")
            raise GoogleAPIError(f"HTTP {status} from PSI")
        else:
            logger.error(f"PSI HTTP Error {status} for {url}: {e.response.text}")
            return None
    except Exception as e:
        await psi_breaker.record_failure()
        logger.error(f"PSI Request Error for {url}: {e}")
        raise GoogleAPIError(str(e))
