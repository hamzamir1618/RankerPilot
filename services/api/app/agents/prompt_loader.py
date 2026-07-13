import os
import yaml
from pathlib import Path
from typing import Dict, Any

def get_prompt_path(agent_id: str, version: str) -> Path:
    base_dir = Path(__file__).parent / "prompts"
    return base_dir / agent_id / f"{version}.yaml"

def load_prompt(agent_id: str, version: str = "v1") -> Dict[str, Any]:
    """
    Loads a YAML prompt pack for a specific agent and version.
    Returns a dictionary with at least 'system' and 'user' keys.
    """
    prompt_path = get_prompt_path(agent_id, version)
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt pack not found: {prompt_path}")
        
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    return data
