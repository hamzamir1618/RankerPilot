import logging
import json
import httpx

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.rate_limit import redis_client
from app.models.models import OAuthToken, OAuthProviderEnum, Project, Membership, RoleEnum
from app.core.crypto import decrypt_token

logger = logging.getLogger(__name__)

CACHE_TTL = 12 * 60 * 60
async def get_ga4_token(db: AsyncSession, project_id: str) -> Optional[OAuthToken]:
    query = (
        select(OAuthToken)
        .join(Membership, Membership.user_id == OAuthToken.user_id)
        .join(Project, Project.org_id == Membership.org_id)
        .where(
            Project.id == project_id,
            OAuthToken.provider == OAuthProviderEnum.ga4,
            Membership.role.in_([RoleEnum.owner, RoleEnum.admin])
        )
        .limit(1)
    )
    res = await db.execute(query)
    return res.scalar_one_or_none()

async def refresh_ga4_token(db: AsyncSession, token: OAuthToken) -> Optional[str]:
    try:
        refresh_token = decrypt_token(token.encrypted_refresh_token)
    except Exception as e:
        logger.error(f"Failed to decrypt refresh token: {e}")
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data={
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            })
            if resp.status_code != 200:
                logger.warning(f"Failed to refresh GA4 token (HTTP {resp.status_code}).")
                return None
                
            data = resp.json()
            return data.get("access_token")
    except Exception as e:
        logger.error(f"GA4 token refresh request failed: {e}")
        return None

async def query_ga4_conversions(
    db: AsyncSession, 
    project_id: str, 
    property_id: str, 
    start_date: str, 
    end_date: str
) -> Optional[List[Dict[str, Any]]]:
    cache_key = f"ga4_conversions:{project_id}:{property_id}:{start_date}:{end_date}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    project = await db.get(Project, project_id)
    if not project:
        return None

    token_obj = await get_ga4_token(db, project_id)
    if not token_obj:
        return None

    access_token = await refresh_ga4_token(db, token_obj)
    if not access_token:
        return None

    payload = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [{"name": "conversions"}, {"name": "screenPageViews"}],
        "limit": 1000
    }

    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url, 
                json=payload, 
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if resp.status_code == 401 or resp.status_code == 403:
                logger.warning("GA4 query returned 401/403.")
                return None
                
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("rows", [])
            
            # Format rows
            results = []
            for r in rows:
                dim = r.get("dimensionValues", [{}])[0].get("value", "")
                metrics = r.get("metricValues", [])
                conv = float(metrics[0].get("value", "0")) if len(metrics) > 0 else 0
                views = float(metrics[1].get("value", "0")) if len(metrics) > 1 else 0
                results.append({"pagePath": dim, "conversions": conv, "views": views})

            await redis_client.set(cache_key, json.dumps(results), ex=CACHE_TTL)
            return results
    except Exception as e:
        logger.error(f"GA4 report query failed: {e}")
        return None
