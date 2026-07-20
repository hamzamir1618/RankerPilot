import logging
import json
import httpx

from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.rate_limit import redis_client
from app.models.models import OAuthToken, OAuthProviderEnum, Project, Membership, RoleEnum

logger = logging.getLogger(__name__)

CACHE_TTL = 12 * 60 * 60

from app.core.crypto import decrypt_token

async def get_gbp_token(db: AsyncSession, project_id: str) -> Optional[OAuthToken]:
    query = (
        select(OAuthToken)
        .join(Membership, Membership.user_id == OAuthToken.user_id)
        .join(Project, Project.org_id == Membership.org_id)
        .where(
            Project.id == project_id,
            OAuthToken.provider == OAuthProviderEnum.gbp,
            Membership.role.in_([RoleEnum.owner, RoleEnum.admin])
        )
        .limit(1)
    )
    res = await db.execute(query)
    return res.scalar_one_or_none()

async def refresh_gbp_token(db: AsyncSession, token: OAuthToken) -> Optional[str]:
    try:
        refresh_token = decrypt_token(token.encrypted_refresh_token)
    except Exception as e:
        logger.error(f"Failed to decrypt GBP refresh token: {e}")
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
                logger.warning(f"Failed to refresh GBP token (HTTP {resp.status_code}).")
                return None
                
            data = resp.json()
            return data.get("access_token")
    except Exception as e:
        logger.error(f"GBP token refresh request failed: {e}")
        return None

async def fetch_gbp_locations(
    db: AsyncSession, 
    project_id: str
) -> Optional[List[Dict[str, Any]]]:
    cache_key = f"gbp_locations:{project_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    project = await db.get(Project, project_id)
    if not project:
        return None

    token_obj = await get_gbp_token(db, project_id)
    if not token_obj:
        return None

    access_token = await refresh_gbp_token(db, token_obj)
    if not access_token:
        return None

    # Google My Business API requires fetching accounts first, then locations
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            accounts_resp = await client.get(
                "https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if accounts_resp.status_code == 401 or accounts_resp.status_code == 403:
                return None
            accounts_resp.raise_for_status()
            accounts = accounts_resp.json().get("accounts", [])
            if not accounts:
                return []
                
            account_name = accounts[0]["name"]
            
            # Fetch locations and reviews
            locations_resp = await client.get(
                f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations?readMask=name,title,storeCode,latlng,primaryCategory,regularHours",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            locations_resp.raise_for_status()
            locations = locations_resp.json().get("locations", [])
            
            # In a real setup, we would also hit the reviews API to get average rating
            # e.g. https://mybusiness.googleapis.com/v4/{account_name}/{location_name}/reviews
            for loc in locations:
                loc["average_rating"] = 4.5 # stub
                loc["review_count"] = 100 # stub
            
            await redis_client.set(cache_key, json.dumps(locations), ex=CACHE_TTL)
            return locations
    except Exception as e:
        logger.error(f"GBP locations fetch failed: {e}")
        return None
