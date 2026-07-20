import logging
import json
import httpx
from datetime import datetime, timedelta, timezone

from typing import Optional, Dict, Any, List
import urllib.parse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.rate_limit import redis_client
from app.models.models import OAuthToken, OAuthProviderEnum, Project, Membership, RoleEnum
from app.core.crypto import decrypt_token

logger = logging.getLogger(__name__)

CACHE_TTL = 12 * 60 * 60  # 12 hours
async def get_gsc_token(db: AsyncSession, project_id: str) -> Optional[OAuthToken]:
    """Finds a valid GSC OAuthToken for a user in the project's org."""
    query = (
        select(OAuthToken)
        .join(Membership, Membership.user_id == OAuthToken.user_id)
        .join(Project, Project.org_id == Membership.org_id)
        .where(
            Project.id == project_id,
            OAuthToken.provider == OAuthProviderEnum.gsc,
            Membership.role.in_([RoleEnum.owner, RoleEnum.admin])
        )
        .limit(1)
    )
    res = await db.execute(query)
    return res.scalar_one_or_none()

async def refresh_gsc_token(db: AsyncSession, token: OAuthToken, project: Project) -> Optional[str]:
    """Refreshes the OAuth token using the encrypted refresh token."""
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
                logger.warning(f"Failed to refresh GSC token (HTTP {resp.status_code}). Revoking connection.")
                # Token expired or revoked -> disconnect project
                project.gsc_connected = False
                await db.commit()
                return None
                
            data = resp.json()
            return data.get("access_token")
    except Exception as e:
        logger.error(f"GSC token refresh request failed: {e}")
        return None

async def query_search_analytics(
    db: AsyncSession, 
    project_id: str, 
    site_url: str, 
    start_date: str, 
    end_date: str, 
    dimensions: List[str] = ["query"]
) -> Optional[List[Dict[str, Any]]]:
    """
    Queries GSC Search Analytics.
    Returns list of rows: {"keys": [...], "clicks": X, "impressions": Y, "ctr": Z, "position": P}
    """
    cache_key = f"gsc_analytics:{project_id}:{site_url}:{start_date}:{end_date}:{','.join(dimensions)}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    project = await db.get(Project, project_id)
    if not project or not project.gsc_connected:
        return None

    token_obj = await get_gsc_token(db, project_id)
    if not token_obj:
        return None

    access_token = await refresh_gsc_token(db, token_obj, project)
    if not access_token:
        return None

    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": 1000
    }

    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site_url, safe='')}/searchAnalytics/query"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url, 
                json=payload, 
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if resp.status_code == 401 or resp.status_code == 403:
                logger.warning("GSC query returned 401/403. Disconnecting project.")
                project.gsc_connected = False
                await db.commit()
                return None
                
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("rows", [])
            
            await redis_client.set(cache_key, json.dumps(rows), ex=CACHE_TTL)
            return rows
    except Exception as e:
        logger.error(f"GSC search analytics query failed: {e}")
        return None

async def get_quick_wins(db: AsyncSession, project_id: str) -> List[Dict[str, Any]]:
    """
    Fetches "Quick Wins" from GSC.
    Quick Wins are queries ranking in positions 8-20 with meaningful volume (e.g. impressions > 100).
    """
    project = await db.get(Project, project_id)
    if not project or not project.gsc_connected:
        return []

    site_url = f"sc-domain:{project.domain}"
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)

    rows = await query_search_analytics(
        db=db,
        project_id=project_id,
        site_url=site_url,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        dimensions=["query", "page"]
    )

    if not rows:
        return []

    quick_wins = []
    for row in rows:
        pos = row.get("position", 0)
        imps = row.get("impressions", 0)
        # 8-20 boundary: exact 8.0 through 20.9
        if 8.0 <= pos < 21.0 and imps >= 100:
            quick_wins.append(row)

    # Sort by impressions desc
    quick_wins.sort(key=lambda x: x.get("impressions", 0), reverse=True)
    return quick_wins
