import uuid
import json
import logging
import urllib.parse
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Error as PlaywrightError

from app.crawler.validator import validate_target_url, SSRFViolation
from app.crawler.robots import can_fetch, USER_AGENT
from app.crawler.politeness import politeness_lock
from app.crawler.s3_client import upload_html

logger = logging.getLogger(__name__)

class PinnedResolver(aiohttp.abc.AbstractResolver):  # type: ignore
    def __init__(self, ip: str):
        self.ip = ip
        
    async def resolve(self, host: str, port: int, family: int) -> list:
        return [{
            'hostname': host,
            'host': self.ip,
            'port': port,
            'family': family,
            'proto': 0,
            'flags': 0
        }]
        
    async def close(self):
        pass

@dataclass
class PageResult:
    url: str
    status_code: int
    rendered: bool
    title: Optional[str] = None
    meta_description: Optional[str] = None
    h1: Optional[List[str]] = None
    word_count: Optional[int] = None
    snapshot_key: Optional[str] = None
    screenshot_key: Optional[str] = None
    lab_vitals: Optional[Dict[str, Any]] = None
    links: Optional[List[str]] = None
    error: Optional[str] = None

def extract_metadata(html: bytes) -> Dict[str, Any]:
    soup = BeautifulSoup(html, 'lxml')
    
    # Title
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    
    # Meta Description
    meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
    meta_content = meta_desc_tag.get('content', '') if meta_desc_tag else ''
    meta_description = str(meta_content[0] if isinstance(meta_content, list) else meta_content).strip() if meta_desc_tag else None
    
    # H1
    h1s = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
    
    # Word count (visible text)
    # Strip scripts and styles
    for script in soup(["script", "style"]):
        script.extract()
    text = soup.get_text(separator=' ')
    words = text.split()
    word_count = len(words)
    
    # Links
    links = [a.get('href') for a in soup.find_all('a', href=True)]
    
    return {
        "title": title,
        "meta_description": meta_description,
        "h1": h1s,
        "word_count": word_count,
        "links": links
    }

def needs_js_render(html: bytes) -> bool:
    """Heuristics to determine if a page needs JS rendering."""
    soup = BeautifulSoup(html, 'lxml')
    text_len = len(soup.get_text(strip=True))
    html_len = len(html)
    
    # If text-to-html ratio is very low
    if html_len > 0 and (text_len / html_len) < 0.02:
        return True
        
    html_str = html.decode('utf-8', errors='ignore')
    if '__next' in html_str or 'ng-app' in html_str or 'root' in html_str:
        return True
        
    main = soup.find('main')
    if main and len(main.get_text(strip=True)) < 50:
        return True
        
    return False

async def fetch_with_playwright(url: str, pinned_ip: str, browser_context=None) -> Tuple[bytes, Dict[str, Any]]:
    # If a context is provided from a pool, we use it directly (note: cannot dynamically apply host rules to existing context)
    if browser_context:
        page = await browser_context.new_page()
        try:
            # Enable CDP for performance metrics
            client = await page.context.new_cdp_session(page)
            await client.send("Performance.enable")
            
            response = await page.goto(url, timeout=30000, wait_until="networkidle")
            content = await page.content()
            html_bytes = content.encode('utf-8')
            
            perf_metrics = await client.send("Performance.getMetrics")
            metrics_dict = {m['name']: m['value'] for m in perf_metrics['metrics']}
            
            return html_bytes, metrics_dict
        except PlaywrightError as e:
            raise Exception(f"Playwright error: {str(e)}")
        finally:
            await page.close()
            
    # host-resolver-rules map the hostname to the pinned IP explicitly
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""
    
    args = [f"--host-resolver-rules=MAP {hostname} {pinned_ip}"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=args, headless=True)
        context = await browser.new_context(user_agent=USER_AGENT)
        
        # Block images/fonts/media
        await context.route("**/*", lambda route: 
            route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_()
        )
        
        page = await context.new_page()
        
        # Enable CDP for performance metrics
        client = await page.context.new_cdp_session(page)
        await client.send("Performance.enable")
        
        try:
            response = await page.goto(url, timeout=30000, wait_until="networkidle")
            content = await page.content()
            html_bytes = content.encode('utf-8')
            
            perf_metrics = await client.send("Performance.getMetrics")
            metrics_dict = {m['name']: m['value'] for m in perf_metrics['metrics']}
            
            return html_bytes, metrics_dict
            
        except PlaywrightError as e:
            raise Exception(f"Playwright error: {str(e)}")
        finally:
            await browser.close()


async def fetch_page(url: str, audit_id: uuid.UUID, browser_context=None) -> PageResult:
    current_url = url
    hops = 0
    max_hops = 5
    max_size = 5 * 1024 * 1024 # 5MB
    
    # Check robots.txt (initial URL)
    if not await can_fetch(current_url):
        return PageResult(url=current_url, status_code=403, rendered=False, error="Blocked by robots.txt")
        
    html_content = b""
    status_code = 0
    final_url = url
    lab_vitals = None
    rendered = False
    
    while hops < max_hops:
        # Validate current URL for SSRF & get Pinned IP
        try:
            pinned_ip = await validate_target_url(current_url)
        except SSRFViolation as e:
            return PageResult(url=current_url, status_code=0, rendered=False, error=str(e))
            
        parsed = urllib.parse.urlparse(current_url)
        
        # Enforce politeness
        async with politeness_lock(parsed.hostname or ""):
            # Setup aiohttp with Pinned Resolver
            resolver = PinnedResolver(pinned_ip)
            connector = aiohttp.TCPConnector(resolver=resolver)
            
            try:
                async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15), headers={"User-Agent": USER_AGENT}) as session:
                    async with session.get(current_url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        status_code = response.status
                        if status_code in (301, 302, 303, 307, 308):
                            # Follow redirect manually
                            location = response.headers.get("Location")
                            if not location:
                                break
                            current_url = urllib.parse.urljoin(current_url, location)
                            hops += 1
                            continue
                            
                        # Not a redirect, read body
                        size = 0
                        chunks = []
                        async for chunk in response.content.iter_chunked(8192):
                            size += len(chunk)
                            if size > max_size:
                                return PageResult(url=current_url, status_code=status_code, rendered=False, error="Response exceeded 5MB limit")
                            chunks.append(chunk)
                            
                        html_content = b"".join(chunks)
                        final_url = current_url
                        break # Successfully fetched
                        
            except aiohttp.ClientError as e:
                return PageResult(url=current_url, status_code=0, rendered=False, error=f"Request failed: {str(e)}")
            except asyncio.TimeoutError:
                return PageResult(url=current_url, status_code=0, rendered=False, error="Request timed out")

    if hops >= max_hops:
        return PageResult(url=current_url, status_code=status_code, rendered=False, error="Exceeded maximum redirects")
        
    if not html_content:
        return PageResult(url=final_url, status_code=status_code, rendered=False, error="Empty response body")
        
    # Check JS Fallback
    if needs_js_render(html_content):
        try:
            # We must re-validate IP just in case? We already have pinned_ip for final_url from the loop
            html_content, lab_vitals = await fetch_with_playwright(final_url, pinned_ip, browser_context=browser_context)
            rendered = True
        except Exception as e:
            # Fallback to the raw HTML if playwright fails
            logger.warning(f"Playwright fallback failed for {final_url}: {e}")
            rendered = False
            
    # Extract
    meta = extract_metadata(html_content)
    
    # S3 Upload
    await upload_html(audit_id, final_url, html_content)
    
    # Calculate keys
    import hashlib
    url_hash = hashlib.sha1(final_url.encode('utf-8')).hexdigest()
    snapshot_key = f"snapshots/{audit_id}/{url_hash}.html.gz"
    
    return PageResult(
        url=final_url,
        status_code=status_code,
        rendered=rendered,
        title=meta.get("title"),
        meta_description=meta.get("meta_description"),
        h1=meta.get("h1"),
        word_count=meta.get("word_count"),
        snapshot_key=snapshot_key,
        lab_vitals=lab_vitals,
        links=meta.get("links")
    )
