import logging
from typing import List, Optional
from pydantic import BaseModel

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum
from app.integrations.llm import get_client

logger = logging.getLogger(__name__)

class LocalAgent(BaseAgent):
    id = "local"
    category = FindingCategoryEnum.local
    requires_llm = True

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        llm = get_client(tier="small")
        
        if ctx.industry != "local_service":
            logger.info(f"Skipping LocalAgent for industry: {ctx.industry}")
            return findings

        # Check GBP
        try:
            from app.integrations.gbp import fetch_gbp_locations
            from app.core.deps import async_session_factory
            
            async with async_session_factory() as session:
                gbp_locations = await fetch_gbp_locations(session, str(ctx.project_id))
                
            if gbp_locations:
                findings.append(self.create_finding(
                    ctx,
                    check_id="gbp_connected_locations",
                    status="pass",
                    category="local",
                    title="Google Business Profile Connected",
                    evidence={"locations_count": len(gbp_locations), "names": [loc.get("title") for loc in gbp_locations[:3]]}
                ))
            else:
                findings.append(self.create_finding(
                    ctx,
                    check_id="gbp_not_connected",
                    status="warn",
                    severity="low",
                    category="local",
                    title="Google Business Profile Not Connected",
                    fix="Connect your Google Business Profile to pull local listing data directly into Rankerpilot."
                ))
        except Exception as e:
            logger.warning(f"Failed to fetch GBP locations in LocalAgent: {e}")

        target_pages = []
        for p in ctx.pages:
            if p.status_code != 200:
                continue
            if p.url == ctx.root_url or p.url == ctx.root_url + "/" or "contact" in p.url.lower() or "about" in p.url.lower():
                target_pages.append(p)
                
        if not target_pages and ctx.pages:
            target_pages = ctx.pages[:1]
            
        if not target_pages:
            return findings
            
        combined_text = "\n---\n".join([f"URL: {p.url}\nContent: {p.content_text[:1500]}" for p in target_pages if p.content_text])
        
        prompt = f"""
        You are a Local SEO expert. Analyze the following website content for Local SEO signals.
        Extract the NAP (Name, Address, Phone number) if present. Check if it's consistently formatted across pages if multiple pages are provided.
        Identify any links or mentions of Google Business Profile (GBP) or Google Maps.
        Extract the service areas mentioned.
        
        Content:
        {combined_text[:6000]}
        """
        
        class LocalSEOAnalysis(BaseModel):
            nap_found: bool
            nap_details: Optional[str]
            gbp_link_found: bool
            service_areas: List[str]
            issues: List[str]
        
        try:
            response = await llm.analyze(
                system="You are a Local SEO expert.",
                prompt=prompt,
                pages_data=[],
                budget=ctx.token_budget,
                schema_model=LocalSEOAnalysis
            )
            
            if not response:
                raise ValueError("LLM returned None")
                
            if response.nap_found:
                findings.append(self.create_finding(
                    ctx,
                    check_id="local_nap_present",
                    status="pass",
                    category="local",
                    title="NAP (Name, Address, Phone) Found",
                    evidence={"details": response.nap_details or ""}
                ))
            else:
                findings.append(self.create_finding(
                    ctx,
                    check_id="local_nap_missing",
                    status="fail",
                    severity="high",
                    category="local",
                    title="Missing NAP (Name, Address, Phone)",
                    effort="one_week",
                    fix="Ensure business Name, Address, and Phone number are clearly visible on the site."
                ))
                
            if response.gbp_link_found:
                findings.append(self.create_finding(
                    ctx,
                    check_id="gbp_link_present",
                    status="pass",
                    category="local",
                    title="Google Business Profile link found"
                ))
            else:
                findings.append(self.create_finding(
                    ctx,
                    check_id="gbp_link_missing",
                    status="warn",
                    severity="medium",
                    category="local",
                    title="No Google Business Profile link found",
                    effort="immediate",
                    fix="Link to your Google Business Profile / Google Maps listing to improve Local SEO."
                ))
                
            areas = response.service_areas
            if areas:
                findings.append(self.create_finding(
                    ctx,
                    check_id="service_areas_found",
                    status="pass",
                    category="local",
                    title=f"Service Areas Identified: {len(areas)}",
                    evidence={"areas": areas[:5]}
                ))
            else:
                findings.append(self.create_finding(
                    ctx,
                    check_id="service_areas_missing",
                    status="info",
                    category="local",
                    title="No explicit service areas mentioned",
                    fix="Consider adding a dedicated Service Areas page or section."
                ))
                
            issues = response.issues
            if issues:
                findings.append(self.create_finding(
                    ctx,
                    check_id="local_seo_issues",
                    status="fail",
                    severity="medium",
                    category="local",
                    title="Local SEO Consistency Issues Detected",
                    effort="one_month",
                    evidence={"issues": issues}
                ))
                
        except Exception as e:
            logger.error(f"Local SEO analysis failed: {e}")
            findings.append({
                "check_id": "local_seo_error",
                "status": "warn",
                "category": self.category.value,
                "title": "Failed to run Local SEO checks"
            })
            
        return findings
