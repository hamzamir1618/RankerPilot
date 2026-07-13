import logging
import aiohttp
from typing import List

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum

logger = logging.getLogger(__name__)

class SecurityHeadersAgent(BaseAgent):
    id = "security_headers"
    category = FindingCategoryEnum.technical
    requires_llm = False

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        if not ctx.root_url:
            return findings

        headers = {}
        try:
            async with aiohttp.ClientSession() as session:
                # Use GET with a small range to avoid downloading body if HEAD is blocked
                async with session.get(ctx.root_url, headers={"Range": "bytes=0-1024"}, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    headers = {k.lower(): v for k, v in response.headers.items()}
        except Exception as e:
            logger.warning(f"Failed to fetch security headers for {ctx.root_url}: {e}")
            findings.append({
                "check_id": "security_headers_fetch_error",
                "status": "fail",
                "severity": "medium",
                "category": self.category.value,
                "title": "Failed to fetch security headers",
                "evidence": {"error": str(e)}
            })
            return findings

        # 1. HSTS
        hsts = headers.get("strict-transport-security")
        if not hsts:
            findings.append({
                "check_id": "hsts_missing",
                "status": "fail",
                "severity": "high",
                "category": self.category.value,
                "title": "Missing HSTS Header",
                "fix": "Add Strict-Transport-Security header to enforce HTTPS.",
                "evidence": {}
            })
        else:
            findings.append({
                "check_id": "hsts_present",
                "status": "pass",
                "category": self.category.value,
                "title": "HSTS Header Present",
                "evidence": {"header": hsts}
            })

        # 2. CSP
        csp = headers.get("content-security-policy")
        if not csp:
            findings.append({
                "check_id": "csp_missing",
                "status": "fail",
                "severity": "medium",
                "category": self.category.value,
                "title": "Missing Content-Security-Policy Header",
                "fix": "Implement CSP to prevent XSS attacks.",
                "evidence": {}
            })
        else:
            findings.append({
                "check_id": "csp_present",
                "status": "pass",
                "category": self.category.value,
                "title": "CSP Header Present",
                "evidence": {"header": csp}
            })

        # 3. X-Content-Type-Options
        xcto = headers.get("x-content-type-options")
        if xcto != "nosniff":
            findings.append({
                "check_id": "x_content_type_options_missing",
                "status": "fail",
                "severity": "low",
                "category": self.category.value,
                "title": "Missing or Invalid X-Content-Type-Options",
                "fix": "Set X-Content-Type-Options: nosniff",
                "evidence": {}
            })
        else:
            findings.append({
                "check_id": "x_content_type_options_present",
                "status": "pass",
                "category": self.category.value,
                "title": "X-Content-Type-Options Valid",
                "evidence": {"header": xcto}
            })

        # 4. Referrer-Policy
        rp = headers.get("referrer-policy")
        if not rp:
            findings.append({
                "check_id": "referrer_policy_missing",
                "status": "fail",
                "severity": "low",
                "category": self.category.value,
                "title": "Missing Referrer-Policy Header",
                "fix": "Set Referrer-Policy to control referrer information.",
                "evidence": {}
            })
        else:
            findings.append({
                "check_id": "referrer_policy_present",
                "status": "pass",
                "category": self.category.value,
                "title": "Referrer-Policy Header Present",
                "evidence": {"header": rp}
            })

        return findings
