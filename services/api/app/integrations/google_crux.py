import logging
import hashlib
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from app.core.config import settings
from app.core.rate_limit import TokenBucketRateLimiter, RedisCircuitBreaker, redis_client

logger = logging.getLogger(__name__)

# CrUX is 150 requests per minute = 2.5 req/sec
crux_limiter = TokenBucketRateLimiter("google_crux", capacity=150, fill_rate=2.5)
crux_breaker = RedisCircuitBreaker("google_crux", failure_threshold=5, cooldown_seconds=60)

CRUX_API_URL = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
CACHE_TTL = 24 * 60 * 60  # 24 hours

class GoogleAPIError(Exception):
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, GoogleAPIError)),
    reraise=True
)
async def fetch_crux_data(url: str = None, origin: str = None, form_factor: str = None) -> dict | None:
    """
    Fetches CrUX data for a given URL or origin.
    Implements Redis caching, rate limiting, retries, and circuit breaking.
    """
    if await crux_breaker.is_open():
        logger.warning(f"CrUX circuit breaker is open. Skipping CrUX call for {url or origin}")
        return None

    api_key = settings.PSI_API_KEY.get_secret_value() if settings.PSI_API_KEY else ""
    
    hash_str = f"{url}:{origin}:{form_factor}:{api_key[:5]}"
    cache_key = f"crux_cache:{hashlib.md5(hash_str.encode()).hexdigest()}"
    
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    if not await crux_limiter.acquire(tokens=1, timeout=30.0):
        logger.warning(f"Failed to acquire CrUX rate limit token for {url or origin}")
        return None

    payload = {}
    if url:
        payload["url"] = url
    elif origin:
        payload["origin"] = origin
        
    if form_factor:
        payload["formFactor"] = form_factor

    params = {}
    if api_key:
        params["key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(CRUX_API_URL, params=params, json=payload)
            # 404 from CrUX just means there is no data for this URL/origin, 
            # we should not retry this or trip the circuit breaker.
            if resp.status_code == 404:
                return None
                
            resp.raise_for_status()
            
        data = resp.json()
        await crux_breaker.record_success()
        
        await redis_client.setex(cache_key, CACHE_TTL, json.dumps(data))
        return data
        
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in (429, 500, 502, 503, 504):
            await crux_breaker.record_failure()
            logger.error(f"CrUX HTTP Error {status} for {url or origin}. Tripping breaker check.")
            raise GoogleAPIError(f"HTTP {status} from CrUX")
        else:
            logger.error(f"CrUX HTTP Error {status} for {url or origin}: {e.response.text}")
            return None
    except Exception as e:
        await crux_breaker.record_failure()
        logger.error(f"CrUX Request Error for {url or origin}: {e}")
        raise GoogleAPIError(str(e))
