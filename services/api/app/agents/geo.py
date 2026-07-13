import logging
import aiohttp
from typing import List

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum
from app.integrations.llm import get_client

logger = logging.getLogger(__name__)

class GeoAgent(BaseAgent):
    id = "geo"
    category = FindingCategoryEnum.ai_readiness
    requires_llm = True

    async def fetch_url(self, url: str) -> str | None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return await response.text()
        except Exception:
            pass
        return None

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        llm = get_client(tier="large")
        
        if not ctx.root_url:
            return findings

        # 1. Check AI Crawlers in robots.txt
        robots_url = ctx.root_url.rstrip("/") + "/robots.txt"
        robots_content = await self.fetch_url(robots_url)
        ai_bots = ["gptbot", "ccbot", "anthropic-ai", "google-extended", "perplexitybot"]
        
        if robots_content:
            blocked_bots = []
            lines = [l.strip().lower() for l in robots_content.splitlines()]
            current_agent = None
            for line in lines:
                if line.startswith("user-agent:"):
                    current_agent = line.split(":", 1)[1].strip()
                elif line.startswith("disallow:") and current_agent in ai_bots:
                    path = line.split(":", 1)[1].strip()
                    if path == "/":
                        blocked_bots.append(current_agent)
            
            if blocked_bots:
                findings.append({
                    "check_id": "ai_bots_blocked",
                    "status": "warn",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": f"AI Crawlers blocked in robots.txt",
                    "evidence": {"blocked_bots": list(set(blocked_bots))},
                    "fix": "Consider allowing AI bots to be included in LLM training and AI Overviews."
                })
            else:
                findings.append({
                    "check_id": "ai_bots_allowed",
                    "status": "pass",
                    "category": self.category.value,
                    "title": "AI Crawlers allowed in robots.txt"
                })

        # 2. Check llms.txt
        llms_url = ctx.root_url.rstrip("/") + "/llms.txt"
        llms_content = await self.fetch_url(llms_url)
        if llms_content:
            findings.append({
                "check_id": "llms_txt_present",
                "status": "pass",
                "category": self.category.value,
                "title": "llms.txt file found",
                "evidence": {"url": llms_url}
            })
        else:
            findings.append({
                "check_id": "llms_txt_missing",
                "status": "info",
                "category": self.category.value,
                "title": "Missing llms.txt",
                "fix": "Add an llms.txt file to provide structured context for AI agents.",
                "evidence": {"url": llms_url}
            })

        # 3. AI Overview Readiness (Check the longest page)
        pages_with_content = [p for p in ctx.pages if p.status_code == 200 and p.content_text]
        if pages_with_content:
            target_page = max(pages_with_content, key=lambda x: x.word_count or 0)
            
            prompt = f"""
            You are an AI Overview (AIO) optimizer.
            Analyze the following content to determine if it is structured well for AI summaries (e.g. Google AI Overviews or ChatGPT).
            Look for clear definitions, bulleted lists, and concise answers to common questions.
            
            Title: {target_page.title}
            Content: {target_page.content_text[:3000]}
            """
            
            schema_out = {
                "type": "object",
                "properties": {
                    "readiness_score": {"type": "integer", "description": "Score from 1 to 100"},
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "weaknesses": {"type": "array", "items": {"type": "string"}},
                    "recommendations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["readiness_score", "strengths", "weaknesses", "recommendations"]
            }
            
            try:
                response = await llm.analyze(
                    prompt=prompt,
                    schema=schema_out,
                    agent_id=self.id,
                    budget=ctx.token_budget
                )
                
                score = response.get("readiness_score", 50)
                status = "pass" if score >= 80 else ("warn" if score >= 50 else "fail")
                
                findings.append({
                    "check_id": "aio_readiness",
                    "status": status,
                    "severity": "medium",
                    "category": self.category.value,
                    "title": f"AI Overview Readiness: {score}/100",
                    "evidence": {
                        "strengths": response.get("strengths"),
                        "weaknesses": response.get("weaknesses")
                    },
                    "fix": "\n".join(response.get("recommendations", [])),
                    "page_id": str(target_page.id)
                })
            except Exception as e:
                logger.error(f"AIO readiness LLM analysis failed: {e}")

        return findings
