import logging
from typing import Dict, Any

from app.agents.base import AuditContext

logger = logging.getLogger(__name__)

# Rule-based keywords for each industry
INDUSTRY_SIGNALS = {
    "saas": ["pricing", "software", "platform", "dashboard", "subscribe", "start free trial"],
    "ecommerce": ["cart", "checkout", "shop", "product", "add to cart", "buy now", "shipping"],
    "local_service": ["appointment", "book now", "service area", "location", "address", "phone number", "plumbing", "roofing", "cleaning"],
    "publisher": ["article", "blog", "news", "editorial", "read more", "magazine", "published on"],
    "agency": ["portfolio", "case study", "services", "agency", "our work", "client", "consultation"]
}

def detect_industry(ctx: AuditContext) -> Dict[str, Any]:
    """
    Detects the industry of the website being audited.
    Returns a dict like: {"industry": "saas", "confidence": 0.8, "reasoning": "..."}
    """
    # 1. Gather all text from pages
    all_text = ""
    for page in ctx.pages:
        if page.title:
            all_text += page.title.lower() + " "
        if page.meta_description:
            all_text += page.meta_description.lower() + " "
        if page.h1:
            all_text += " ".join(page.h1).lower() + " "
            
        # We also might want to check the URL paths (e.g. /pricing, /shop)
        all_text += page.url.lower() + " "

    # 2. Rule-based scoring
    scores = {ind: 0 for ind in INDUSTRY_SIGNALS.keys()}
    
    for industry, keywords in INDUSTRY_SIGNALS.items():
        for keyword in keywords:
            if keyword in all_text:
                scores[industry] += 1
                
    # Find the top scorer
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_industry, top_score = sorted_scores[0]
    second_industry, second_score = sorted_scores[1]
    
    # 3. Decision or LLM Tie-breaker
    # If no signals at all, or if there's a tie (or very close), use LLM
    if top_score == 0 or (top_score - second_score) <= 1:
        logger.info(f"Industry signals ambiguous for {ctx.audit_id}. Using LLM fallback.")
        
        # In a real implementation, we would call the Anthropics API here.
        # Stubbing for now.
        if ctx.llm_client:
            try:
                # We expect the mock to have a method we can call, or we just return a stub if it fails
                pass
            except Exception:
                pass
                
        # Default fallback if LLM fails or is not provided
        return {
            "industry": "saas",
            "confidence": 0.5,
            "reasoning": "LLM fallback returned default saas due to ambiguity and missing LLM client."
        }
        
    return {
        "industry": top_industry,
        "confidence": 0.8,
        "reasoning": f"Rule-based match based on highest signal score ({top_score})."
    }
