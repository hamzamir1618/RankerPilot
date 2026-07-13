import logging
import urllib.parse
import xml.etree.ElementTree as ET
import aiohttp
from typing import List, Dict, Any

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum
from app.crawler.discovery import normalize_url

logger = logging.getLogger(__name__)

class SitemapRobotsAgent(BaseAgent):
    id = "sitemap_robots"
    category = FindingCategoryEnum.technical
    requires_llm = False

    async def fetch_url(self, url: str) -> str | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.text()
        except Exception:
            pass
        return None

    def validate_robots_txt(self, content: str) -> bool:
        """Basic syntax validation for robots.txt"""
        if not content.strip():
            return True
        lines = content.splitlines()
        has_user_agent = any(line.lower().startswith("user-agent:") for line in lines)
        has_directive = any(line.lower().startswith(("allow:", "disallow:")) for line in lines)
        # It's valid if it has User-agent and some directive, or if it's just comments
        return has_user_agent and has_directive

    def parse_sitemap(self, content: str) -> List[str]:
        """Parse sitemap XML and extract URLs."""
        urls = []
        try:
            root = ET.fromstring(content)
            # Handle namespaces usually present in sitemaps: {http://www.sitemaps.org/schemas/sitemap/0.9}
            for child in root:
                if 'url' in child.tag.lower() or 'sitemap' in child.tag.lower():
                    for loc in child:
                        if 'loc' in loc.tag.lower() and loc.text:
                            urls.append(loc.text.strip())
        except Exception as e:
            logger.warning(f"Failed to parse sitemap XML: {e}")
            raise ValueError("Invalid XML format")
        return urls

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        
        if not ctx.root_url:
            return findings

        # 1. robots.txt
        robots_url = ctx.root_url.rstrip("/") + "/robots.txt"
        robots_content = await self.fetch_url(robots_url)
        
        if robots_content is None:
            findings.append({
                "check_id": "robots_txt_missing",
                "status": "fail",
                "severity": "MEDIUM",
                "category": self.category.value,
                "title": "Missing robots.txt",
                "evidence": {"robots_url": robots_url}
            })
        else:
            if not self.validate_robots_txt(robots_content):
                findings.append({
                    "check_id": "robots_txt_syntax",
                    "status": "fail",
                    "severity": "HIGH",
                    "category": self.category.value,
                    "title": "Invalid robots.txt Syntax",
                    "evidence": {"robots_url": robots_url, "content_preview": robots_content[:200]}
                })
            else:
                findings.append({
                    "check_id": "robots_txt_present",
                    "status": "pass",
                    "category": self.category.value,
                    "title": "Valid robots.txt found",
                    "evidence": {"robots_url": robots_url}
                })

        # 2. sitemap.xml
        sitemap_url = ctx.root_url.rstrip("/") + "/sitemap.xml"
        sitemap_content = await self.fetch_url(sitemap_url)
        sitemap_urls = []
        
        if sitemap_content is None:
            findings.append({
                "check_id": "sitemap_missing",
                "status": "fail",
                "severity": "MEDIUM",
                "category": self.category.value,
                "title": "Missing sitemap.xml at root",
                "evidence": {"sitemap_url": sitemap_url}
            })
        else:
            try:
                raw_urls = self.parse_sitemap(sitemap_content)
                sitemap_urls = [normalize_url(u, ctx.root_url) for u in raw_urls]
                findings.append({
                    "check_id": "sitemap_valid",
                    "status": "pass",
                    "category": self.category.value,
                    "title": "Valid sitemap.xml found",
                    "evidence": {"sitemap_url": sitemap_url, "urls_count": len(sitemap_urls)}
                })
            except ValueError:
                findings.append({
                    "check_id": "sitemap_syntax",
                    "status": "fail",
                    "severity": "HIGH",
                    "category": self.category.value,
                    "title": "Invalid sitemap.xml Syntax",
                    "evidence": {"sitemap_url": sitemap_url, "content_preview": sitemap_content[:200]}
                })

        # 3. Orphan Pages
        # Calculate inlinks
        inlinks = {p.url: 0 for p in ctx.pages}
        for source_url, outlinks in ctx.site_graph.items():
            for link in outlinks:
                norm_link = normalize_url(link, ctx.root_url)
                if norm_link in inlinks and norm_link != source_url:
                    inlinks[norm_link] += 1
        
        sitemap_set = set(sitemap_urls)
        orphan_urls = []
        
        for p in ctx.pages:
            if p.status_code == 200:
                if p.url not in sitemap_set and inlinks.get(p.url, 0) == 0:
                    # It's an orphan (and also missing from sitemap)
                    orphan_urls.append(p.url)
        
        if orphan_urls:
            findings.append({
                "check_id": "orphan_pages",
                "status": "FAIL",
                "severity": "HIGH",
                "category": self.category.value,
                "title": f"Found {len(orphan_urls)} Orphan Pages",
                "evidence": {"orphan_urls": orphan_urls[:10]},
                "fix": "Ensure all important pages are linked internally or included in the sitemap."
            })
        else:
            findings.append({
                "check_id": "orphan_pages",
                "status": "PASS",
                "category": self.category.value,
                "title": "No orphan pages found",
                "evidence": {}
            })

        return findings
