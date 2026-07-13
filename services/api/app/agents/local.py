import logging
from typing import List

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
        
        schema_out = {
            "type": "object",
            "properties": {
                "nap_found": {"type": "boolean"},
                "nap_details": {"type": "string"},
                "gbp_link_found": {"type": "boolean"},
                "service_areas": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "issues": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["nap_found", "gbp_link_found", "service_areas", "issues"]
        }
        
        try:
            response = await llm.analyze(
                prompt=prompt,
                schema=schema_out,
                agent_id=self.id,
                budget=ctx.token_budget
            )
            
            if response.get("nap_found"):
                findings.append({
                    "check_id": "local_nap_present",
                    "status": "pass",
                    "category": self.category.value,
                    "title": "NAP (Name, Address, Phone) Found",
                    "evidence": {"details": response.get("nap_details", "")}
                })
            else:
                findings.append({
                    "check_id": "local_nap_missing",
                    "status": "fail",
                    "severity": "high",
                    "category": self.category.value,
                    "title": "Missing NAP (Name, Address, Phone)",
                    "fix": "Ensure business Name, Address, and Phone number are clearly visible on the site."
                })
                
            if response.get("gbp_link_found"):
                findings.append({
                    "check_id": "gbp_link_present",
                    "status": "pass",
                    "category": self.category.value,
                    "title": "Google Business Profile link found"
                })
            else:
                findings.append({
                    "check_id": "gbp_link_missing",
                    "status": "warn",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": "No Google Business Profile link found",
                    "fix": "Link to your Google Business Profile / Google Maps listing to improve Local SEO."
                })
                
            areas = response.get("service_areas", [])
            if areas:
                findings.append({
                    "check_id": "service_areas_found",
                    "status": "pass",
                    "category": self.category.value,
                    "title": f"Service Areas Identified: {len(areas)}",
                    "evidence": {"areas": areas[:5]}
                })
            else:
                findings.append({
                    "check_id": "service_areas_missing",
                    "status": "info",
                    "category": self.category.value,
                    "title": "No explicit service areas mentioned",
                    "fix": "Consider adding a dedicated Service Areas page or section."
                })
                
            issues = response.get("issues", [])
            if issues:
                findings.append({
                    "check_id": "local_seo_issues",
                    "status": "fail",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": "Local SEO Consistency Issues Detected",
                    "evidence": {"issues": issues}
                })
                
        except Exception as e:
            logger.error(f"Local SEO analysis failed: {e}")
            findings.append({
                "check_id": "local_seo_error",
                "status": "warn",
                "category": self.category.value,
                "title": "Failed to run Local SEO checks"
            })
            
        return findings
