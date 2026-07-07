import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_login_happy_path(client: AsyncClient):
    # 1. Register
    reg_res = await client.post("/v1/auth/register", json={
        "email": "test@example.com",
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
        "email": "test@example.com",
        "password": "strongpassword123"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert "refresh_token" in login_res.cookies

@pytest.mark.asyncio
async def test_duplicate_email(client: AsyncClient):
    await client.post("/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "strongpassword123"
    })
    
    # Register again
    reg_res = await client.post("/v1/auth/register", json={
        "email": "dup@example.com",
        "password": "strongpassword123"
    })
    assert reg_res.status_code == 409
    assert reg_res.json()["detail"] == "Email already registered"

@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse(client: AsyncClient):
    # Register
    reg_res = await client.post("/v1/auth/register", json={
        "email": "rotate@example.com",
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
    assert "Reuse detected" in reuse_res.json()["detail"]
    
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
    # Hit register 6 times (limit is 5/min)
    for i in range(5):
        res = await client.post("/v1/auth/register", json={
            "email": f"limit{i}@example.com",
            "password": "pwd"
        })
        # The first might be 200, others could be anything, but let's just trigger the limit
    
    # 6th request
    res = await client.post("/v1/auth/register", json={
        "email": "limit6@example.com",
        "password": "pwd"
    })
    assert res.status_code == 429
    assert "Retry-After" in res.headers
