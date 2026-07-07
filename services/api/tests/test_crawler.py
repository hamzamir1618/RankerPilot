import pytest
import uuid
import asyncio
from unittest.mock import patch, AsyncMock
from aiohttp import web
from app.crawler.fetcher import fetch_page, SSRFViolation
from app.crawler.validator import validate_target_url

# Helper to start a local aiohttp server
async def run_server(app):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 0)
    await site.start()
    return runner, site.name

@pytest.fixture
async def test_server():
    async def normal_handler(request):
        return web.Response(text="<html><head><title>Normal</title></head><body><h1>Hello</h1></body></html>", content_type='text/html')
        
    async def large_handler(request):
        return web.Response(body=b"A" * (6 * 1024 * 1024), content_type='text/html')
        
    async def thin_handler(request):
        return web.Response(text="<html><div id='root'></div><script>document.getElementById('root').innerHTML = 'rendered';</script></html>", content_type='text/html')
        
    async def redirect_safe_handler(request):
        raise web.HTTPFound('/normal')
        
    async def redirect_unsafe_handler(request):
        # Redirect to a local loopback IP which should be blocked
        raise web.HTTPFound('http://127.0.0.1:8080/secret')
        
    async def robots_handler(request):
        return web.Response(text="User-agent: *\nDisallow: /blocked\n")

    async def blocked_handler(request):
        return web.Response(text="Blocked")

    app = web.Application()
    app.router.add_get('/normal', normal_handler)
    app.router.add_get('/large', large_handler)
    app.router.add_get('/thin', thin_handler)
    app.router.add_get('/redirect_safe', redirect_safe_handler)
    app.router.add_get('/redirect_unsafe', redirect_unsafe_handler)
    app.router.add_get('/robots.txt', robots_handler)
    app.router.add_get('/blocked', blocked_handler)
    
    runner, host_port = await run_server(app)
    # Return base URL. Note: host_port might be something like '127.0.0.1:PORT'. 
    # But wait, 127.0.0.1 will trigger the SSRF protection!
    # To test locally, we must mock the validator for normal tests, OR 
    # allow localhost just for the test. We will mock the validator to return a dummy safe IP 
    # and bypass the exception, except for SSRF specific tests.
    
    yield f"http://{host_port}"
    await runner.cleanup()

@pytest.fixture
def mock_validator_safe():
    with patch("app.crawler.fetcher.validate_target_url", new_callable=AsyncMock) as m:
        m.return_value = "8.8.8.8" # Dummy safe IP for tests
        yield m

@pytest.fixture
def mock_s3_upload():
    with patch("app.crawler.fetcher.upload_html", new_callable=AsyncMock) as m:
        yield m

@pytest.mark.asyncio
async def test_normal_fetch(test_server, mock_validator_safe, mock_s3_upload):
    url = f"{test_server}/normal"
    audit_id = uuid.uuid4()
    
    # We must also mock robots can_fetch since test_server uses 127.0.0.1 which robots fetcher will hit, but wait, robots uses standard aiohttp so it'll work if not blocked.
    
    res = await fetch_page(url, audit_id)
    assert res.status_code == 200
    assert res.title == "Normal"
    assert res.h1 == ["Hello"]
    assert res.rendered is False
    assert res.error is None
    mock_s3_upload.assert_called_once()

@pytest.mark.asyncio
async def test_mocked_dns_ssrf(test_server):
    # Do not mock validator here, we want it to run.
    # The URL will be http://127.0.0.1:port/ 
    # validate_target_url will resolve 127.0.0.1 and raise SSRFViolation
    url = f"{test_server}/normal"
    audit_id = uuid.uuid4()
    
    res = await fetch_page(url, audit_id)
    assert res.status_code == 0
    assert "Forbidden IP range" in res.error

@pytest.mark.asyncio
async def test_redirect_to_private_ip(test_server, mock_validator_safe, mock_s3_upload):
    url = f"{test_server}/redirect_unsafe"
    audit_id = uuid.uuid4()
    
    # The first hop is allowed by mock_validator_safe.
    # The second hop is "http://127.0.0.1:8080/secret".
    # We need the mock to raise SSRFViolation on the second call.
    def side_effect(target_url):
        if "127.0.0.1" in target_url:
            raise SSRFViolation("Forbidden IP range")
        return "8.8.8.8"
    mock_validator_safe.side_effect = side_effect
    
    res = await fetch_page(url, audit_id)
    assert res.status_code == 0
    assert "Forbidden IP range" in res.error

@pytest.mark.asyncio
async def test_robots_txt_blocking(test_server, mock_validator_safe, mock_s3_upload):
    # test_server serves a robots.txt that blocks /blocked
    url = f"{test_server}/blocked"
    audit_id = uuid.uuid4()
    
    res = await fetch_page(url, audit_id)
    assert res.status_code == 403
    assert res.error == "Blocked by robots.txt"

@pytest.mark.asyncio
async def test_response_size_limit(test_server, mock_validator_safe, mock_s3_upload):
    url = f"{test_server}/large"
    audit_id = uuid.uuid4()
    
    res = await fetch_page(url, audit_id)
    assert res.status_code == 200
    assert "exceeded 5MB" in res.error.lower()

@pytest.mark.asyncio
async def test_playwright_fallback(test_server, mock_validator_safe, mock_s3_upload):
    url = f"{test_server}/thin"
    audit_id = uuid.uuid4()
    
    with patch("app.crawler.fetcher.fetch_with_playwright", new_callable=AsyncMock) as m_pw:
        m_pw.return_value = (b"<html><body><h1>Rendered by JS</h1></body></html>", {"LCP": 120})
        
        res = await fetch_page(url, audit_id)
        
        # fallback triggered
        m_pw.assert_called_once()
        assert res.rendered is True
        assert res.h1 == ["Rendered by JS"]
        assert res.lab_vitals == {"LCP": 120}
