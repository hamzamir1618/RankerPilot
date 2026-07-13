import pytest
from unittest.mock import AsyncMock, patch

from app.integrations.llm import get_client, LLMClient

@pytest.fixture
def mock_anthropic():
    with patch("app.integrations.llm.AnthropicBedrock") as mock: # Or whichever underlying client
        yield mock

@pytest.mark.asyncio
async def test_llm_client_initialization():
    client = get_client(tier="small")
    assert isinstance(client, LLMClient)
    assert client.anthropic_model == "claude-3-haiku-20240307"

@pytest.mark.asyncio
async def test_llm_analyze_success():
    client = get_client(tier="small")
    
    from pydantic import BaseModel
    class TestSchema(BaseModel):
        score: int

    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: {
        "content": [{
            "type": "tool_use",
            "name": "record_findings",
            "input": {"score": 10}
        }]
    }

    with patch("app.integrations.llm.httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        # Provide a dummy key to bypass key check
        client.anthropic_key = "test_key"
        result = await client.analyze("System", "Test prompt", [], 1000, TestSchema)

        assert isinstance(result, TestSchema)
        assert result.score == 10
        mock_post.assert_called_once()
