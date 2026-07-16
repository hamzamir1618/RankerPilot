import pytest
import respx
import httpx
from app.integrations.google_psi import fetch_psi_data, psi_breaker, psi_limiter
from app.integrations.google_crux import fetch_crux_data, crux_breaker, crux_limiter
from app.core.rate_limit import redis_client

@pytest.fixture(autouse=True)
async def clear_redis():
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()

@pytest.mark.asyncio
async def test_psi_cache_hit_miss():
    with respx.mock:
        route = respx.get(url__startswith="https://www.googleapis.com/pagespeedonline/v5/runPagespeed").respond(
            json={"lighthouseResult": {"audits": {"render-blocking-resources": {"score": 0.5}}}},
            status_code=200
        )
        
        # Miss
        data1 = await fetch_psi_data("https://example.com")
        assert route.call_count == 1
        assert data1["lighthouseResult"]["audits"]["render-blocking-resources"]["score"] == 0.5
        
        # Hit
        data2 = await fetch_psi_data("https://example.com")
        assert route.call_count == 1  # Should not increase
        assert data2 == data1

@pytest.mark.asyncio
async def test_circuit_breaker_trips():
    with respx.mock:
        route = respx.get(url__startswith="https://www.googleapis.com/pagespeedonline/v5/runPagespeed").respond(
            status_code=500
        )
        
        # tenacity retries 3 times per call. So 2 calls = 6 failures > threshold of 5.
        for _ in range(2):
            try:
                await fetch_psi_data("https://fail.com")
            except Exception:
                pass
                
        # Now it should be open
        assert await psi_breaker.is_open()
        
        # Next call should return None immediately without hitting API
        prev_count = route.call_count
        res = await fetch_psi_data("https://fail.com")
        assert res is None
        assert route.call_count == prev_count

@pytest.mark.asyncio
async def test_crux_cache_and_404():
    with respx.mock:
        # CrUX returns 404 if no data, which should return None without error
        route = respx.post(url__startswith="https://chromeuxreport.googleapis.com/v1/records:queryRecord").respond(
            status_code=404
        )
        
        data = await fetch_crux_data(url="https://nodata.com")
        assert data is None
        assert route.call_count == 1
        assert not await crux_breaker.is_open() # 404 shouldn't trip breaker
