import pytest
import uuid
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_login_happy_path(client: AsyncClient):
    email = f"test_{uuid.uuid4().hex}@example.com"
    # 1. Register
    reg_res = await client.post("/v1/auth/register", json={
        "email": email,
        "password": "strongpassword123"
    })
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert "access_token" in data
    assert "user_id" in data
    
    # Check cookie
    assert "refresh_token" in reg_res.cookies

    # 2. Login
    login_res = await client.post("/v1/auth/login", json={
        "email": email,
        "password": "strongpassword123"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert "refresh_token" in login_res.cookies

@pytest.mark.asyncio
async def test_duplicate_email(client: AsyncClient):
    email = f"dup_{uuid.uuid4().hex}@example.com"
    await client.post("/v1/auth/register", json={
        "email": email,
        "password": "strongpassword123"
    })
    
    # Register again
    reg_res = await client.post("/v1/auth/register", json={
        "email": email,
        "password": "strongpassword123"
    })
    assert reg_res.status_code == 409
    assert reg_res.json()["detail"] == "Email already registered"

@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse(client: AsyncClient):
    email = f"rotate_{uuid.uuid4().hex}@example.com"
    # Register
    reg_res = await client.post("/v1/auth/register", json={
        "email": email,
        "password": "strongpassword123"
    })
    refresh_cookie = reg_res.cookies.get("refresh_token")
    
    # 1. Refresh successfully
    refresh_res = await client.post("/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert refresh_res.status_code == 200
    new_refresh_cookie = refresh_res.cookies.get("refresh_token")
    assert new_refresh_cookie != refresh_cookie
    
    # 2. Try reusing old token -> Reuse detection should fire
    reuse_res = await client.post("/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert reuse_res.status_code == 401
    assert "reuse detected" in reuse_res.json()["detail"].lower()
    
    # 3. Try using the new token after family revoked -> Should fail
    revoked_res = await client.post("/v1/auth/refresh", cookies={"refresh_token": new_refresh_cookie})
    assert revoked_res.status_code == 401
    assert "revoked" in revoked_res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_invalid_jwt(client: AsyncClient):
    # Pass arbitrary string as Bearer
    res = await client.get("/v1/projects/", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid token"

@pytest.mark.asyncio
async def test_rate_limit(client: AsyncClient):
    uid = uuid.uuid4().hex
    # Hit register 6 times (limit is 5/min)
    for i in range(5):
        res = await client.post("/v1/auth/register", json={
            "email": f"limit{i}_{uid}@example.com",
            "password": "pwd"
        }, headers={"X-Forwarded-For": "10.0.0.99"})
        # The first might be 200, others could be anything, but let's just trigger the limit
    
    # 6th request
    res = await client.post("/v1/auth/register", json={
        "email": f"limit6_{uid}@example.com",
        "password": "pwd"
    }, headers={"X-Forwarded-For": "10.0.0.99"})
    assert res.status_code == 429
    assert "Retry-After" in res.headers
