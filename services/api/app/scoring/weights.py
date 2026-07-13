from typing import Dict
from app.models.models import IndustryEnum

# Base category weights (sum to 1.0 or close to it)
WEIGHTS: Dict[str, float] = {
    "content": 0.23,
    "technical": 0.22,
    "onpage": 0.20,
    "schema": 0.10,
    "performance": 0.10,
    "ai_readiness": 0.10,
    "images": 0.05,
}

# Override for local_service industry.
# Drops onpage to 0.12 and gives local 0.08.
LOCAL_SERVICE_WEIGHTS: Dict[str, float] = {
    "content": 0.23,
    "technical": 0.22,
    "onpage": 0.12,
    "schema": 0.10,
    "performance": 0.10,
    "ai_readiness": 0.10,
    "images": 0.05,
    "local": 0.08,
}

def get_category_weights(industry: str | None) -> Dict[str, float]:
    """
    Returns the appropriate weights table based on the project's industry.
    """
    if industry == IndustryEnum.local_service:
        return LOCAL_SERVICE_WEIGHTS.copy()
    return WEIGHTS.copy()
