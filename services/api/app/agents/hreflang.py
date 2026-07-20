from app.agents.base import BaseAgent, AuditContext
from bs4 import BeautifulSoup

class HreflangAgent(BaseAgent):
    async def run(self, ctx: AuditContext) -> list[dict]:
        import httpx
        findings = []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(ctx.root_url)
                html = res.text
        except Exception:
            return []
            
        soup = BeautifulSoup(html, "html.parser")
        hreflang_tags = soup.find_all("link", rel="alternate", hreflang=True)
        
        if not hreflang_tags:
            return [] 
            
        has_x_default = False
        valid_tags = 0
        invalid_format = 0
        
        for tag in hreflang_tags:
            lang_val = tag.get("hreflang", "")
            lang = lang_val[0] if isinstance(lang_val, list) else lang_val
            lang = str(lang).lower() if lang else ""
            if lang == "x-default":
                has_x_default = True
            elif "_" in lang:
                invalid_format += 1
            else:
                valid_tags += 1
                
        if invalid_format > 0:
            findings.append({
                "audit_id": ctx.audit_id,
                "agent": self.id,
                "check_id": "hreflang_format",
                "status": "fail",
                "severity": "medium",
                "category": "technical",
                "title": "Invalid Hreflang Format",
                "effort": "immediate",
                "evidence": {"invalid_tags": invalid_format},
                "fix": "Use hyphens for region codes in hreflang attributes (e.g., 'en-us' not 'en_us')."
            })
            
        if not has_x_default and valid_tags > 0:
            findings.append({
                "audit_id": ctx.audit_id,
                "agent": self.id,
                "check_id": "hreflang_x_default",
                "status": "fail",
                "severity": "low",
                "category": "technical",
                "title": "Missing x-default Hreflang",
                "effort": "one_week",
                "evidence": {"tags_found": len(hreflang_tags)},
                "fix": "Include a fallback 'x-default' hreflang tag for unmatched regions."
            })
            
        if not findings:
            findings.append({
                "audit_id": ctx.audit_id,
                "agent": self.id,
                "check_id": "hreflang_format",
                "status": "pass",
                "category": "technical",
                "title": "Valid Hreflang Tags",
                "evidence": {"valid_tags": valid_tags}
            })
        
        return findings
