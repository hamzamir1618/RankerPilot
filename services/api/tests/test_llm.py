import pytest
import json
from unittest.mock import AsyncMock, patch

from app.integrations.llm import get_client, LLMClient
from app.agents.base import AuditContext
from app.schemas.schemas import PageResponse

@pytest.fixture
def mock_anthropic():
    with patch("app.integrations.llm.AnthropicBedrock") as mock: # Or whichever underlying client
        yield mock

@pytest.mark.asyncio
async def test_llm_client_initialization():
    client = get_client(tier="small")
    assert isinstance(client, LLMClient)
    assert client.model == "claude-3-haiku-20240307"

@pytest.mark.asyncio
async def test_llm_analyze_success():
    client = get_client(tier="small")
    
    schema = {
        "type": "object",
        "properties": {"score": {"type": "integer"}},
        "required": ["score"]
    }
    
    mock_response = AsyncMock()
    mock_response.content = [AsyncMock(text=json.dumps({"score": 10}))]
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 10
    
    with patch.object(client.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await client.analyze("Test prompt", schema, "test_agent", 1000)
        
        assert result == {"score": 10}
        mock_create.assert_called_once()
