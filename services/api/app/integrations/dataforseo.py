import logging
import hashlib
import json
import base64
import httpx
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

from app.core.config import settings
from app.core.rate_limit import RedisCircuitBreaker, redis_client

logger = logging.getLogger(__name__)

dfs_breaker = RedisCircuitBreaker("dataforseo", failure_threshold=5, cooldown_seconds=60)

DFS_API_BASE = "https://api.dataforseo.com"
CACHE_TTL = 24 * 60 * 60  # 24 hours

class DataForSEOError(Exception):
    pass

class CostMeter:
    """Tracks spent budget against a cap."""
    def __init__(self, cap: float):
        self.cap = cap
        self.spent = 0.0

    def can_afford(self, estimated_cost: float) -> bool:
        return (self.spent + estimated_cost) <= self.cap

    def add_cost(self, actual_cost: float):
        self.spent += actual_cost

# Estimated costs per endpoint (USD)
COSTS = {
    "keyword_ideas": 0.001,
    "keyword_overview": 0.001,
    "domain_intersection": 0.001,
    "serp_advanced": 0.002,
    "backlinks_summary": 0.001
}

def get_auth_header() -> str:
    login = settings.DATAFORSEO_LOGIN
    password = settings.DATAFORSEO_PASSWORD.get_secret_value() if settings.DATAFORSEO_PASSWORD else ""
    credentials = f"{login}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode("utf-8")
    return f"Basic {encoded}"

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, DataForSEOError)),
    reraise=True
)
async def _make_dfs_request(
    endpoint: str, 
    payload: List[Dict[str, Any]], 
    endpoint_type: str,
    meter: Optional[CostMeter] = None
) -> dict | None:
    if await dfs_breaker.is_open():
        logger.warning("DataForSEO circuit breaker is open. Skipping.")
        return None

    # 1. Cost Metering Check
    estimated = COSTS.get(endpoint_type, 0.001) * len(payload)
    if meter and not meter.can_afford(estimated):
        logger.warning(f"DataForSEO budget exceeded for {endpoint_type}. Spent: {meter.spent}, Cap: {meter.cap}")
        return {"error": "budget_exceeded"}

    # 2. Caching
    # Hash the payload to create a unique, reproducible cache key
    payload_str = json.dumps(payload, sort_keys=True)
    cache_key = f"dfs_cache:{endpoint_type}:{hashlib.md5(payload_str.encode()).hexdigest()}"
    
    cached = await redis_client.get(cache_key)
    if cached:
        # We don't charge the meter for cached hits!
        return json.loads(cached)

    # 3. HTTP Request
    headers = {
        "Authorization": get_auth_header(),
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{DFS_API_BASE}{endpoint}", json=payload, headers=headers)
            resp.raise_for_status()
            
        data = resp.json()
        await dfs_breaker.record_success()
        
        # Charge the meter the actual cost if provided by DFS, else estimated
        actual_cost = data.get("cost", estimated)
        if meter:
            meter.add_cost(actual_cost)
            
        # Cache the result
        # Note: replace setex with set + ex to avoid deprecation warning
        await redis_client.set(cache_key, json.dumps(data), ex=CACHE_TTL)
        return data

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in (429, 500, 502, 503, 504):
            await dfs_breaker.record_failure()
            logger.error(f"DFS HTTP Error {status}. Tripping breaker check.")
            raise DataForSEOError(f"HTTP {status} from DFS")
        else:
            logger.error(f"DFS HTTP Error {status}: {e.response.text}")
            return None
    except Exception as e:
        await dfs_breaker.record_failure()
        logger.error(f"DFS Request Error: {e}")
        raise DataForSEOError(str(e))

async def keyword_ideas(keywords: List[str], location_code: int = 2840, language_code: str = "en", meter: Optional[CostMeter] = None):
    """Fetch keyword ideas from a seed keyword list."""
    payload = [{"keywords": keywords, "location_code": location_code, "language_code": language_code}]
    return await _make_dfs_request("/v3/dataforseo_labs/google/keyword_ideas/live", payload, "keyword_ideas", meter)

async def keyword_overview(keywords: List[str], location_code: int = 2840, language_code: str = "en", meter: Optional[CostMeter] = None):
    """Fetch metrics for specific keywords."""
    payload = [{"keywords": keywords, "location_code": location_code, "language_code": language_code}]
    return await _make_dfs_request("/v3/dataforseo_labs/google/keyword_overview/live", payload, "keyword_overview", meter)

async def domain_intersection(domain1: str, domain2: str, location_code: int = 2840, language_code: str = "en", meter: Optional[CostMeter] = None):
    """Find keywords that domain1 and domain2 rank for."""
    payload = [{"target1": domain1, "target2": domain2, "location_code": location_code, "language_code": language_code}]
    return await _make_dfs_request("/v3/dataforseo_labs/google/domain_intersection/live", payload, "domain_intersection", meter)

async def serp_advanced(keyword: str, location_code: int = 2840, language_code: str = "en", meter: Optional[CostMeter] = None):
    """Fetch full advanced SERP snapshot for a keyword."""
    payload = [{"keyword": keyword, "location_code": location_code, "language_code": language_code, "depth": 100}]
    return await _make_dfs_request("/v3/serp/google/organic/live/advanced", payload, "serp_advanced", meter)

async def backlinks_summary(domain: str, meter: Optional[CostMeter] = None):
    """Fetch backlinks summary for a domain."""
    payload = [{"target": domain}]
    return await _make_dfs_request("/v3/backlinks/summary/live", payload, "backlinks_summary", meter)
