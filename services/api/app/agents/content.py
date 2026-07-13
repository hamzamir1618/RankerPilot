import logging
from typing import List

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum
from app.integrations.llm import get_client

logger = logging.getLogger(__name__)

def _get_shingles(text: str, k: int = 5) -> set:
    words = text.lower().split()
    return set(" ".join(words[i:i+k]) for i in range(len(words) - k + 1))

def jaccard_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    s1 = _get_shingles(text1)
    s2 = _get_shingles(text2)
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))

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
        
        schema_out = {
            "type": "object",
            "properties": {
                "eeat_score": {"type": "integer", "description": "Score from 1 to 10"},
                "intent_match": {"type": "string", "enum": ["Informational", "Transactional", "Navigational"]},
                "analysis": {"type": "string"},
                "improvements": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["eeat_score", "intent_match", "analysis", "improvements"]
        }
        
        for page in top_pages:
            prompt = f"""
            You are a Google Quality Rater evaluating E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness).
            Analyze the following page content for its E-E-A-T signals and classify its primary search intent.
            Industry context: {ctx.industry}
            
            Title: {page.title}
            Content (truncated): {page.content_text[:3000]}
            """
            
            try:
                response = await llm.analyze(
                    prompt=prompt,
                    schema=schema_out,
                    agent_id=self.id,
                    budget=ctx.token_budget
                )
                
                score = response.get("eeat_score", 5)
                status = "pass" if score >= 7 else ("warn" if score >= 5 else "fail")
                
                findings.append({
                    "check_id": "eeat_scoring",
                    "status": status,
                    "severity": "medium",
                    "category": self.category.value,
                    "title": f"E-E-A-T Score: {score}/10",
                    "evidence": {
                        "intent": response.get("intent_match"),
                        "analysis": response.get("analysis")
                    },
                    "fix": "\n".join(response.get("improvements", [])),
                    "page_id": str(page.id)
                })
            except Exception as e:
                logger.error(f"E-E-A-T LLM analysis failed for {page.url}: {e}")
                
        return findings
