from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.class_model import Class
from app.database.models.section import Section


@pytest.mark.asyncio
async def test_create_section(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a section"""
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

    payload = {
        "class_id": str(class_obj.id),
        "name": "A",
        "strength": 30,
    }

    response = await async_client.post("/api/v1/sections", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["class_id"] == str(class_obj.id)
    assert data["name"] == "A"
    assert data["strength"] == 30
    assert "id" in data


@pytest.mark.asyncio
async def test_create_section_duplicate(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a section with duplicate name for same class fails"""
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

    section = Section(class_id=class_obj.id, name="A", strength=30)
    db_session.add(section)
    await db_session.commit()

    payload = {
        "class_id": str(class_obj.id),
        "name": "A",
        "strength": 30,
    }

    response = await async_client.post("/api/v1/sections", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_section(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting a section by ID"""
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

    section = Section(class_id=class_obj.id, name="A", strength=30)
    db_session.add(section)
    await db_session.commit()
    await db_session.refresh(section)

    response = await async_client.get(f"/api/v1/sections/{section.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "A"
    assert data["strength"] == 30


@pytest.mark.asyncio
async def test_get_section_not_found(async_client: AsyncClient):
    """Test getting a non-existent section returns 404"""
    response = await async_client.get(f"/api/v1/sections/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_sections(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing sections with pagination"""
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

    sections = [
        Section(class_id=class_obj.id, name="A", strength=30),
        Section(class_id=class_obj.id, name="B", strength=30),
        Section(class_id=class_obj.id, name="C", strength=30),
    ]
    for s in sections:
        db_session.add(s)
    await db_session.commit()

    response = await async_client.get("/api/v1/sections")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_list_sections_filter_by_class(async_client: AsyncClient, db_session: AsyncSession):
    """Test filtering sections by class"""
    class1 = Class(name="SE E&TC", year=2, branch="E&TC", academic_year="2025-26", strength=60)
    class2 = Class(name="TE E&TC", year=3, branch="E&TC", academic_year="2025-26", strength=60)
    db_session.add_all([class1, class2])
    await db_session.commit()
    await db_session.refresh(class1)
    await db_session.refresh(class2)

    sections = [
        Section(class_id=class1.id, name="A", strength=30),
        Section(class_id=class2.id, name="A", strength=30),
    ]
    for s in sections:
        db_session.add(s)
    await db_session.commit()

    response = await async_client.get("/api/v1/sections", params={"class_id": str(class1.id)})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["class_id"] == str(class1.id)


@pytest.mark.asyncio
async def test_list_sections_search(async_client: AsyncClient, db_session: AsyncSession):
    """Test searching sections by name"""
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

    sections = [
        Section(class_id=class_obj.id, name="A", strength=30),
        Section(class_id=class_obj.id, name="B", strength=30),
    ]
    for s in sections:
        db_session.add(s)
    await db_session.commit()

    response = await async_client.get("/api/v1/sections", params={"search": "A"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "A"


@pytest.mark.asyncio
async def test_update_section(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a section"""
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

    section = Section(class_id=class_obj.id, name="A", strength=30)
    db_session.add(section)
    await db_session.commit()
    await db_session.refresh(section)

    response = await async_client.put(
        f"/api/v1/sections/{section.id}",
        json={"strength": 35},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["strength"] == 35
    assert data["name"] == "A"  # unchanged


@pytest.mark.asyncio
async def test_update_section_duplicate_name(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a section to have duplicate name for same class fails"""
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

    section1 = Section(class_id=class_obj.id, name="A", strength=30)
    section2 = Section(class_id=class_obj.id, name="B", strength=30)
    db_session.add_all([section1, section2])
    await db_session.commit()

    response = await async_client.put(
        f"/api/v1/sections/{section2.id}",
        json={"name": "A"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_section(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting a section"""
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

    section = Section(class_id=class_obj.id, name="A", strength=30)
    db_session.add(section)
    await db_session.commit()
    await db_session.refresh(section)

    response = await async_client.delete(f"/api/v1/sections/{section.id}")
    assert response.status_code == 204

    # Verify deleted
    response = await async_client.get(f"/api/v1/sections/{section.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_section_not_found(async_client: AsyncClient):
    """Test deleting a non-existent section returns 404"""
    response = await async_client.delete(f"/api/v1/sections/{uuid4()}")
    assert response.status_code == 404
