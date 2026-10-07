from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.class_model import Class


@pytest.mark.asyncio
async def test_create_class(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a class"""
    payload = {
        "name": "SE E&TC",
        "year": 2,
        "branch": "E&TC",
        "academic_year": "2025-26",
        "strength": 60,
    }

    response = await async_client.post("/api/v1/classes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "SE E&TC"
    assert data["year"] == 2
    assert data["branch"] == "E&TC"
    assert data["academic_year"] == "2025-26"
    assert data["strength"] == 60
    assert "id" in data


@pytest.mark.asyncio
async def test_create_class_duplicate(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a class with duplicate name and academic year fails"""
    class_obj = Class(
        name="SE E&TC",
        year=2,
        branch="E&TC",
        academic_year="2025-26",
        strength=60,
    )
    db_session.add(class_obj)
    await db_session.commit()

    payload = {
        "name": "SE E&TC",
        "year": 2,
        "branch": "E&TC",
        "academic_year": "2025-26",
        "strength": 60,
    }

    response = await async_client.post("/api/v1/classes", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_class(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting a class by ID"""
    class_obj = Class(
        name="SE E&TC",
        year=2,
        branch="E&TC",
        academic_year="2025-26",
        strength=60,
    )
    db_session.add(class_obj)
    await db_session.commit()
    await db_session.refresh(class_obj)

    response = await async_client.get(f"/api/v1/classes/{class_obj.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "SE E&TC"
    assert data["year"] == 2


@pytest.mark.asyncio
async def test_get_class_not_found(async_client: AsyncClient):
    """Test getting a non-existent class returns 404"""
    response = await async_client.get(f"/api/v1/classes/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_classes(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing classes with pagination"""
    classes = [
        Class(name="SE E&TC", year=2, branch="E&TC", academic_year="2025-26", strength=60),
        Class(name="TE E&TC", year=3, branch="E&TC", academic_year="2025-26", strength=60),
        Class(name="BE E&TC", year=4, branch="E&TC", academic_year="2025-26", strength=60),
        Class(name="SE CS", year=2, branch="CS", academic_year="2025-26", strength=60),
    ]
    for c in classes:
        db_session.add(c)
    await db_session.commit()

    response = await async_client.get("/api/v1/classes")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert len(data["items"]) == 4


@pytest.mark.asyncio
async def test_list_classes_filter_by_year(async_client: AsyncClient, db_session: AsyncSession):
    """Test filtering classes by academic year"""
    classes = [
        Class(name="SE E&TC", year=2, branch="E&TC", academic_year="2025-26", strength=60),
        Class(name="TE E&TC", year=3, branch="E&TC", academic_year="2024-25", strength=60),
    ]
    for c in classes:
        db_session.add(c)
    await db_session.commit()

    response = await async_client.get("/api/v1/classes", params={"academic_year": "2025-26"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["academic_year"] == "2025-26"


@pytest.mark.asyncio
async def test_list_classes_search(async_client: AsyncClient, db_session: AsyncSession):
    """Test searching classes by name"""
    classes = [
        Class(name="SE E&TC", year=2, branch="E&TC", academic_year="2025-26", strength=60),
        Class(name="SE CS", year=2, branch="CS", academic_year="2025-26", strength=60),
    ]
    for c in classes:
        db_session.add(c)
    await db_session.commit()

    response = await async_client.get("/api/v1/classes", params={"search": "E&TC"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["branch"] == "E&TC"


@pytest.mark.asyncio
async def test_update_class(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a class"""
    class_obj = Class(
        name="SE E&TC",
        year=2,
        branch="E&TC",
        academic_year="2025-26",
        strength=60,
    )
    db_session.add(class_obj)
    await db_session.commit()
    await db_session.refresh(class_obj)

    response = await async_client.put(
        f"/api/v1/classes/{class_obj.id}",
        json={"strength": 70, "branch": "E&TC-A"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["strength"] == 70
    assert data["branch"] == "E&TC-A"
    assert data["name"] == "SE E&TC"  # unchanged


@pytest.mark.asyncio
async def test_update_class_duplicate(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a class to have duplicate name/year fails"""
    class1 = Class(name="SE E&TC", year=2, branch="E&TC", academic_year="2025-26", strength=60)
    class2 = Class(name="TE E&TC", year=3, branch="E&TC", academic_year="2025-26", strength=60)
    db_session.add_all([class1, class2])
    await db_session.commit()

    response = await async_client.put(
        f"/api/v1/classes/{class2.id}",
        json={"name": "SE E&TC", "year": 2},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_class(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting a class"""
    class_obj = Class(
        name="SE E&TC",
        year=2,
        branch="E&TC",
        academic_year="2025-26",
        strength=60,
    )
    db_session.add(class_obj)
    await db_session.commit()
    await db_session.refresh(class_obj)

    response = await async_client.delete(f"/api/v1/classes/{class_obj.id}")
    assert response.status_code == 204

    # Verify deleted
    response = await async_client.get(f"/api/v1/classes/{class_obj.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_class_not_found(async_client: AsyncClient):
    """Test deleting a non-existent class returns 404"""
    response = await async_client.delete(f"/api/v1/classes/{uuid4()}")
    assert response.status_code == 404
