import urllib.parse
import aiohttp
import logging
from typing import List, Set
import xml.etree.ElementTree as ET
import tldextract

logger = logging.getLogger(__name__)

def get_registrable_domain(url: str) -> str:
    """Extracts the registrable domain from a URL using tldextract."""
    ext = tldextract.extract(url)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return ext.domain  # fallback for localhost or IPs

def is_internal(url: str, base_domain: str) -> bool:
    """Checks if a URL belongs to the same registrable domain."""
    return get_registrable_domain(url) == base_domain

def normalize_url(url: str, base_url: str = "") -> str:
    """
    Resolves relative paths, strips fragments, and sorts query params.
    """
    # Resolve relative URL
    if base_url:
        url = urllib.parse.urljoin(base_url, url)
        
    parsed = urllib.parse.urlparse(url)
    
    # Strip fragment
    parsed = parsed._replace(fragment="")
    
    # Sort query params
    if parsed.query:
        query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query_params.sort(key=lambda x: x[0])
        sorted_query = urllib.parse.urlencode(query_params)
        parsed = parsed._replace(query=sorted_query)
        
    # Standardize scheme (lowercase) and netloc (lowercase)
    parsed = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    
    # Ensure no trailing slash if path is empty (it defaults to empty, but some parses yield '/')
    # Actually, it's safer to keep trailing slashes as they might represent different pages in some frameworks,
    # but let's strip trailing slash if it's the root path.
    # We will just use urlunparse.
    
    return urllib.parse.urlunparse(parsed)

async def extract_sitemap_urls(sitemap_url: str, session: aiohttp.ClientSession, max_depth: int = 3) -> List[str]:
    """Recursively parse sitemaps and sitemap indexes."""
    if max_depth <= 0:
        return []
        
    try:
        async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                return []
            content = await response.read()
    except Exception as e:
        logger.warning(f"Failed to fetch sitemap {sitemap_url}: {e}")
        return []

    urls = []
    try:
        # Some sitemaps might have encoding issues, let ElementTree handle bytes
        root = ET.fromstring(content)
        # Handle namespaces e.g. {http://www.sitemaps.org/schemas/sitemap/0.9}
        
        # Strip namespaces for easier parsing
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
                
        if root.tag == 'sitemapindex':
            for sitemap in root.findall('sitemap'):
                loc = sitemap.find('loc')
                if loc is not None and loc.text:
                    sub_urls = await extract_sitemap_urls(loc.text.strip(), session, max_depth - 1)
                    urls.extend(sub_urls)
        elif root.tag == 'urlset':
            for url_elem in root.findall('url'):
                loc = url_elem.find('loc')
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())
                    
    except ET.ParseError:
        logger.warning(f"Failed to parse XML for sitemap {sitemap_url}")
        
    return urls
