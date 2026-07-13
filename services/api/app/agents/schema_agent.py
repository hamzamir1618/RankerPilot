import logging
import json
from typing import List

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum
from app.integrations.llm import get_client

logger = logging.getLogger(__name__)

class SchemaAgent(BaseAgent):
    id = "schema_agent"
    category = FindingCategoryEnum.schema
    requires_llm = True

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        
        llm = get_client(tier="small")
        
        for page in ctx.pages:
            if page.status_code != 200:
                continue
                
            if not page.json_ld:
                findings.append({
                    "check_id": "schema_missing",
                    "status": "info",
                    "category": self.category.value,
                    "title": "No JSON-LD Schema found",
                    "page_id": str(page.id)
                })
                continue
                
            payload = json.dumps(page.json_ld)
            
            prompt = f"""
            You are an expert SEO JSON-LD validator.
            Analyze the following JSON-LD schema for syntax errors, missing required properties (according to schema.org), and general best practices.
            
            JSON-LD:
            {payload}
            """
            
            schema_out = {
                "type": "object",
                "properties": {
                    "is_valid": {"type": "boolean"},
                    "errors": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "corrected_json": {"type": "string", "description": "The fully corrected JSON-LD payload if there were errors."}
                },
                "required": ["is_valid", "errors", "corrected_json"]
            }
            
            try:
                response = await llm.analyze(
                    prompt=prompt,
                    schema=schema_out,
                    agent_id=self.id,
                    budget=ctx.token_budget
                )
                
                if response.get("is_valid"):
                    findings.append({
                        "check_id": "schema_valid",
                        "status": "pass",
                        "category": self.category.value,
                        "title": "JSON-LD Schema is valid",
                        "page_id": str(page.id)
                    })
                else:
                    findings.append({
                        "check_id": "schema_invalid",
                        "status": "fail",
                        "severity": "medium",
                        "category": self.category.value,
                        "title": "JSON-LD Schema has errors or missing properties",
                        "evidence": {"errors": response.get("errors")},
                        "fix": "Use the corrected JSON-LD:\n" + response.get("corrected_json", ""),
                        "page_id": str(page.id)
                    })
                    
            except Exception as e:
                logger.error(f"LLM validation failed for schema on {page.url}: {e}")
                findings.append({
                    "check_id": "schema_validation_error",
                    "status": "warn",
                    "category": self.category.value,
                    "title": "Failed to validate schema via LLM",
                    "evidence": {"error": str(e)},
                    "page_id": str(page.id)
                })

        return findings
