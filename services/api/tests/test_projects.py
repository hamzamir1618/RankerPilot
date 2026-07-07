import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_org_isolation(client: AsyncClient):
    # 1. Register User A
    user_a_res = await client.post("/v1/auth/register", json={
        "email": "usera@example.com",
        "password": "pwd"
    })
    token_a = user_a_res.json()["access_token"]
    
    # 2. Register User B
    user_b_res = await client.post("/v1/auth/register", json={
        "email": "userb@example.com",
        "password": "pwd"
    })
    token_b = user_b_res.json()["access_token"]
    
    # 3. User A creates a project
    proj_a_res = await client.post(
        "/v1/projects/", 
        headers={"Authorization": f"Bearer {token_a}"},
        json={"domain": "example-a.com", "name": "A", "industry": "saas"}
    )
    assert proj_a_res.status_code == 200
    project_a_id = proj_a_res.json()["id"]
    
    # 4. User B creates a project
    proj_b_res = await client.post(
        "/v1/projects/", 
        headers={"Authorization": f"Bearer {token_b}"},
        json={"domain": "example-b.com", "name": "B", "industry": "saas"}
    )
    assert proj_b_res.status_code == 200
    
    # 5. User A tries to GET User B's project (should be 404, not 403, to prevent leaking existence)
    project_b_id = proj_b_res.json()["id"]
    get_b_res = await client.get(
        f"/v1/projects/{project_b_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert get_b_res.status_code == 404

    # 6. User A lists projects, should only see their own
    list_a_res = await client.get(
        "/v1/projects/",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert list_a_res.status_code == 200
    items = list_a_res.json()
    assert len(items) == 1
    assert items[0]["id"] == project_a_id

@pytest.mark.asyncio
async def test_duplicate_domain_in_same_org(client: AsyncClient):
    # Register
    user_res = await client.post("/v1/auth/register", json={
        "email": "org1@example.com",
        "password": "pwd"
    })
    token = user_res.json()["access_token"]
    
    # Create project 1
    await client.post(
        "/v1/projects/", 
        headers={"Authorization": f"Bearer {token}"},
        json={"domain": "dup.com", "name": "1"}
    )
    
    # Create project 2 with same domain
    res = await client.post(
        "/v1/projects/", 
        headers={"Authorization": f"Bearer {token}"},
        json={"domain": "https://www.dup.com/", "name": "2"} # normalization will make it dup.com
    )
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"]
