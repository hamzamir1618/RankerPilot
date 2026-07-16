import logging
from typing import List, Literal
from pydantic import BaseModel
from app.utils.clustering import jaccard_similarity

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum
from app.integrations.llm import get_client
from app.integrations.dataforseo import serp_advanced, CostMeter
from app.core.config import settings

logger = logging.getLogger(__name__)

class ContentAgent(BaseAgent):
    id = "content"
    category = FindingCategoryEnum.content
    requires_llm = True

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        llm = get_client(tier="large")
        
        # 1. Deduplication
        pages_with_content = [p for p in ctx.pages if p.status_code == 200 and p.content_text]
        duplicate_pairs = set()
        
        for i in range(len(pages_with_content)):
            for j in range(i + 1, len(pages_with_content)):
                p1 = pages_with_content[i]
                p2 = pages_with_content[j]
                sim = jaccard_similarity(p1.content_text, p2.content_text)
                if sim > 0.8: # 80% similar
                    pair = tuple(sorted([p1.url, p2.url]))
                    duplicate_pairs.add(pair)
                    
        for p1_url, p2_url in duplicate_pairs:
            findings.append({
                "check_id": "duplicate_content",
                "status": "fail",
                "severity": "high",
                "category": self.category.value,
                "title": "Near-Duplicate Content Detected",
                "evidence": {"urls": [p1_url, p2_url]},
                "fix": "Consolidate duplicate pages using 301 redirects or rel=canonical."
            })

        # 2. E-E-A-T and Intent matching (we'll just pick a sample of pages to avoid blowing up tokens)
        pages_with_content.sort(key=lambda x: x.word_count or 0, reverse=True)
        top_pages = pages_with_content[:3]
        
        class EEATResult(BaseModel):
            eeat_score: int
            intent_match: Literal["Informational", "Transactional", "Navigational"]
            analysis: str
            improvements: List[str]
        
        for page in top_pages:
            # 1. Fetch real SERP snapshot for the page's core topic (approximated by title)
            topic = page.title.split("-")[0].strip() if page.title else "default topic"
            meter = CostMeter(cap=settings.DFS_AUDIT_BUDGET_USD)
            serp_data = await serp_advanced(topic, meter=meter)
            
            serp_summary = "No SERP data available due to budget or API constraints."
            if serp_data and serp_data.get("tasks"):
                items = serp_data["tasks"][0].get("result", [])
                if items:
                    results = items[0].get("items", [])[:10]
                    # Compute average word count if available in DFS results, else fallback
                    word_counts = [r.get("metrics", {}).get("word_count", 0) for r in results if r.get("metrics", {}).get("word_count")]
                    avg_word_count = sum(word_counts) // len(word_counts) if word_counts else "Unknown"
                    
                    titles = [r.get("title", "") for r in results]
                    serp_summary = f"Top 10 SERP Titles: {', '.join(titles)}\nAverage SERP Word Count: {avg_word_count}"
                    
            prompt = f"""
            You are a Google Quality Rater evaluating E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness).
            Analyze the following page content for its E-E-A-T signals and classify its primary search intent.
            Industry context: {ctx.industry}
            
            Real SERP Snapshot for '{topic}':
            {serp_summary}
            
            Compare the page's word count ({page.word_count}) and content intent against the real SERP average.
            
            Page Title: {page.title}
            Content (truncated): {(page.content_text or "")[:3000]}
            """
            
            try:
                response = await llm.analyze(
                    system="You are a Google Quality Rater evaluating E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness).",
                    prompt=prompt,
                    pages_data=[],
                    budget=ctx.token_budget,
                    schema_model=EEATResult
                )
                
                if not response:
                    raise ValueError("LLM returned None")
                    
                score = response.eeat_score
                status = "pass" if score >= 7 else ("warn" if score >= 5 else "fail")
                
                findings.append({
                    "check_id": "eeat_scoring",
                    "status": status,
                    "severity": "medium",
                    "category": self.category.value,
                    "title": f"E-E-A-T Score: {score}/10",
                    "evidence": {
                        "intent": response.intent_match,
                        "analysis": response.analysis
                    },
                    "fix": "\n".join(response.improvements),
                    "page_id": str(page.id)
                })
            except Exception as e:
                logger.error(f"E-E-A-T LLM analysis failed for {page.url}: {e}")
                
        return findings
