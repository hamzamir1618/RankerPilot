import pytest
import respx
from httpx import Response
from app.integrations.dataforseo import keyword_ideas, CostMeter, DFS_API_BASE

@pytest.mark.asyncio
async def test_dfs_cost_meter_abort():
    # Meter with a very small budget
    meter = CostMeter(cap=0.0005) # less than 0.001
    
    # Should abort before calling API
    res = await keyword_ideas(["test keyword"], meter=meter)
    
    assert res is not None
    assert res.get("error") == "budget_exceeded"
    
@pytest.mark.asyncio
@respx.mock
async def test_dfs_successful_call_with_meter():
    meter = CostMeter(cap=1.0)
    
    respx.post(f"{DFS_API_BASE}/v3/dataforseo_labs/google/keyword_ideas/live").mock(
        return_value=Response(200, json={
            "cost": 0.001,
            "tasks": [{"result": [{"items": [{"keyword": "test keyword", "search_volume": 1000}]}]}]
        })
    )
    
    res = await keyword_ideas(["test keyword"], meter=meter)
    
    assert res is not None
    assert "tasks" in res
    assert meter.spent == 0.001
    
    # Second call should use cache (since caching is enabled by default in DFS module)
    # We will simulate a cache hit by just calling it again
    # It shouldn't charge the meter again.
    res2 = await keyword_ideas(["test keyword"], meter=meter)
    assert res2 is not None
    assert meter.spent == 0.001 # Did not increase!
