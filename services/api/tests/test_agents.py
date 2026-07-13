import pytest
from app.agents.sitemap_robots import SitemapRobotsAgent
from app.agents.base import AuditContext
from app.schemas.schemas import PageResponse
import uuid

@pytest.mark.asyncio
async def test_sitemap_robots_agent():
    agent = SitemapRobotsAgent()
    page = PageResponse(
        id=uuid.uuid4(),
        audit_id=uuid.uuid4(),
        url="https://example.com/page1",
        status_code=200,
        rendered=False,
        headings=[],
        images=[],
        links=[]
    )
    
    ctx = AuditContext(
        audit_id=str(uuid.uuid4()),
        pages=[page],
        site_graph={"https://example.com/page1": []},
        robots_txt=None,
        sitemap_urls=[],
        industry="saas",
        root_url="https://example.com"
    )
    
    # We can mock the network calls
    with pytest.MonkeyPatch.context() as m:
        async def mock_fetch(self, url):
            if "robots.txt" in url:
                return "User-agent: *\nDisallow:"
            elif "sitemap.xml" in url:
                return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/page1</loc></url></urlset>'
            return None
            
        m.setattr(SitemapRobotsAgent, "fetch_url", mock_fetch)
        
        findings = await agent.run(ctx)
        
        assert any(f["check_id"] == "robots_txt_present" for f in findings)
        assert any(f["check_id"] == "sitemap_valid" for f in findings)
        
        # Check orphan pages pass
        orphan_finding = next((f for f in findings if f["check_id"] == "orphan_pages"), None)
        assert orphan_finding is not None
        assert orphan_finding["status"] == "pass"
