from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.resource import Resource


@pytest.mark.asyncio
async def test_create_resource(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a resource"""
    payload = {
        "name": "LH-101",
        "resource_type": "CLASSROOM",
        "capacity": 60,
        "building": "Main",
        "floor": "1",
        "room_number": "101",
        "features": ["projector", "whiteboard"],
        "is_emergency": False,
    }

    response = await async_client.post("/api/v1/resources", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "LH-101"
    assert data["resource_type"] == "CLASSROOM"
    assert data["capacity"] == 60
    assert data["building"] == "Main"
    assert data["is_emergency"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_create_resource_duplicate_name(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a resource with duplicate name fails"""
    resource = Resource(
        name="LH-101",
        resource_type="CLASSROOM",
        capacity=60,
    )
    db_session.add(resource)
    await db_session.commit()

    payload = {
        "name": "LH-101",
        "resource_type": "SOFTWARE_LAB",
        "capacity": 20,
    }

    response = await async_client.post("/api/v1/resources", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_resource(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting a resource by ID"""
    resource = Resource(
        name="LH-102",
        resource_type="CLASSROOM",
        capacity=60,
        building="Main",
        floor="1",
        room_number="102",
    )
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)

    response = await async_client.get(f"/api/v1/resources/{resource.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "LH-102"
    assert data["capacity"] == 60


@pytest.mark.asyncio
async def test_get_resource_not_found(async_client: AsyncClient):
    """Test getting a non-existent resource returns 404"""
    response = await async_client.get(f"/api/v1/resources/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_resources(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing resources with pagination"""
    resources = [
        Resource(name=f"LH-{i:03d}", resource_type="CLASSROOM", capacity=60) for i in range(1, 6)
    ]
    resources.extend(
        [
            Resource(name=f"SL-{i:03d}", resource_type="SOFTWARE_LAB", capacity=20)
            for i in range(1, 5)
        ]
    )
    resources.extend(
        [
            Resource(name=f"HL-{i:03d}", resource_type="HARDWARE_LAB", capacity=20)
            for i in range(1, 4)
        ]
    )
    for r in resources:
        db_session.add(r)
    await db_session.commit()

    response = await async_client.get("/api/v1/resources")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 12
    assert len(data["items"]) == 12
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_list_resources_filter_by_type(async_client: AsyncClient, db_session: AsyncSession):
    """Test filtering resources by type"""
    resources = [
        Resource(name="LH-101", resource_type="CLASSROOM", capacity=60),
        Resource(name="SL-101", resource_type="SOFTWARE_LAB", capacity=20),
        Resource(name="HL-101", resource_type="HARDWARE_LAB", capacity=20),
    ]
    for r in resources:
        db_session.add(r)
    await db_session.commit()

    response = await async_client.get("/api/v1/resources", params={"resource_type": "CLASSROOM"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["resource_type"] == "CLASSROOM"


@pytest.mark.asyncio
async def test_list_resources_search(async_client: AsyncClient, db_session: AsyncSession):
    """Test searching resources by name"""
    resources = [
        Resource(name="LH-101", resource_type="CLASSROOM", capacity=60),
        Resource(name="LH-201", resource_type="CLASSROOM", capacity=60),
        Resource(name="SL-101", resource_type="SOFTWARE_LAB", capacity=20),
    ]
    for r in resources:
        db_session.add(r)
    await db_session.commit()

    response = await async_client.get("/api/v1/resources", params={"search": "LH-101"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "LH-101"


@pytest.mark.asyncio
async def test_update_resource(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a resource"""
    resource = Resource(
        name="LH-101",
        resource_type="CLASSROOM",
        capacity=60,
    )
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)

    response = await async_client.put(
        f"/api/v1/resources/{resource.id}",
        json={"capacity": 70, "building": "New Building"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["capacity"] == 70
    assert data["building"] == "New Building"
    assert data["name"] == "LH-101"  # unchanged


@pytest.mark.asyncio
async def test_update_resource_duplicate_name(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a resource to have a duplicate name fails"""
    resource1 = Resource(name="LH-101", resource_type="CLASSROOM", capacity=60)
    resource2 = Resource(name="LH-102", resource_type="CLASSROOM", capacity=60)
    db_session.add_all([resource1, resource2])
    await db_session.commit()

    response = await async_client.put(
        f"/api/v1/resources/{resource2.id}",
        json={"name": "LH-101"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_resource(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting a resource"""
    resource = Resource(
        name="LH-101",
        resource_type="CLASSROOM",
        capacity=60,
    )
    db_session.add(resource)
    await db_session.commit()
    await db_session.refresh(resource)

    response = await async_client.delete(f"/api/v1/resources/{resource.id}")
    assert response.status_code == 204

    # Verify deleted
    response = await async_client.get(f"/api/v1/resources/{resource.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_resource_not_found(async_client: AsyncClient):
    """Test deleting a non-existent resource returns 404"""
    response = await async_client.delete(f"/api/v1/resources/{uuid4()}")
    assert response.status_code == 404
