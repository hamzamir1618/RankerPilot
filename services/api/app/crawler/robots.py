import urllib.parse
import urllib.robotparser
from typing import Optional
import aiohttp
from app.core.rate_limit import redis_client

USER_AGENT = "RankerPilotBot/1.0 (+https://rankerpilot.app/bot)"

async def fetch_robots_txt(domain_url: str) -> Optional[str]:
    """Fetch robots.txt for a given domain using aiohttp."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(domain_url, headers={"User-Agent": USER_AGENT}, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    return await response.text()
    except Exception:
        pass
    return None

async def can_fetch(url: str) -> bool:
    """
    Check if the URL can be fetched according to robots.txt.
    Caches the robots.txt content in Redis for 1 hour.
    """
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc:
        return False
        
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    cache_key = f"robots_txt:{parsed.netloc}"
    
    robots_txt_content = await redis_client.get(cache_key)
    
    if robots_txt_content is None:
        robots_txt_content = await fetch_robots_txt(robots_url)
        if robots_txt_content is None:
            # If we can't fetch it, assume allow, but cache an empty string so we don't retry constantly
            robots_txt_content = ""
            
        await redis_client.set(cache_key, robots_txt_content, ex=3600)
        
    # We parse it
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    if robots_txt_content:
        content_str = robots_txt_content.decode('utf-8') if isinstance(robots_txt_content, bytes) else robots_txt_content
        rp.parse(content_str.splitlines())
    else:
        # Default allow all if no robots.txt
        return True
        
    return rp.can_fetch(USER_AGENT, url)
