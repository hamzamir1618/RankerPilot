from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel

from app.models.models import FindingCategoryEnum
from app.schemas.schemas import PageResponse

@dataclass
class AuditContext:
    audit_id: str
    pages: List[PageResponse]
    site_graph: Dict[str, List[str]] # URL -> List[URLs] it links to
    robots_txt: Optional[str]
    sitemap_urls: List[str]
    industry: str
    
    # Stubbed clients
    llm_client: Any = None
    psi_client: Any = None
    dfs_client: Any = None

class BaseAgent(ABC):
    id: str
    category: FindingCategoryEnum
    requires_llm: bool

    @abstractmethod
    async def run(self, ctx: AuditContext) -> List[dict]:
        """
        Executes the agent logic.
        Must return a list of dictionaries that match the FindingCreate schema format.
        """
        pass
