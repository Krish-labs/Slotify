from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.section import Section


@pytest.mark.asyncio
async def test_create_batch(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a batch"""
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

    payload = {
        "section_id": str(section.id),
        "name": "B1",
        "batch_number": 1,
        "strength": 15,
    }

    response = await async_client.post("/api/v1/batches", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["section_id"] == str(section.id)
    assert data["name"] == "B1"
    assert data["batch_number"] == 1
    assert data["strength"] == 15
    assert "id" in data


@pytest.mark.asyncio
async def test_create_batch_duplicate(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a batch with duplicate name for same section fails"""
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

    batch = Batch(section_id=section.id, name="B1", batch_number=1, strength=15)
    db_session.add(batch)
    await db_session.commit()

    payload = {
        "section_id": str(section.id),
        "name": "B1",
        "batch_number": 2,
        "strength": 15,
    }

    response = await async_client.post("/api/v1/batches", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_batch(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting a batch by ID"""
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

    batch = Batch(section_id=section.id, name="B1", batch_number=1, strength=15)
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)

    response = await async_client.get(f"/api/v1/batches/{batch.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "B1"
    assert data["batch_number"] == 1
    assert data["strength"] == 15


@pytest.mark.asyncio
async def test_get_batch_not_found(async_client: AsyncClient):
    """Test getting a non-existent batch returns 404"""
    response = await async_client.get(f"/api/v1/batches/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_batches(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing batches with pagination"""
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

    batches = [
        Batch(section_id=section.id, name="B1", batch_number=1, strength=15),
        Batch(section_id=section.id, name="B2", batch_number=2, strength=15),
    ]
    for b in batches:
        db_session.add(b)
    await db_session.commit()

    response = await async_client.get("/api/v1/batches")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_batches_filter_by_section(async_client: AsyncClient, db_session: AsyncSession):
    """Test filtering batches by section"""
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
    await db_session.refresh(section1)
    await db_session.refresh(section2)

    batches = [
        Batch(section_id=section1.id, name="B1", batch_number=1, strength=15),
        Batch(section_id=section2.id, name="B1", batch_number=1, strength=15),
    ]
    for b in batches:
        db_session.add(b)
    await db_session.commit()

    response = await async_client.get("/api/v1/batches", params={"section_id": str(section1.id)})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["section_id"] == str(section1.id)


@pytest.mark.asyncio
async def test_list_batches_search(async_client: AsyncClient, db_session: AsyncSession):
    """Test searching batches by name"""
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

    batches = [
        Batch(section_id=section.id, name="B1", batch_number=1, strength=15),
        Batch(section_id=section.id, name="B2", batch_number=2, strength=15),
    ]
    for b in batches:
        db_session.add(b)
    await db_session.commit()

    response = await async_client.get("/api/v1/batches", params={"search": "B1"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "B1"


@pytest.mark.asyncio
async def test_update_batch(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a batch"""
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

    batch = Batch(section_id=section.id, name="B1", batch_number=1, strength=15)
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)

    response = await async_client.put(
        f"/api/v1/batches/{batch.id}",
        json={"strength": 20, "batch_number": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["strength"] == 20
    assert data["batch_number"] == 2
    assert data["name"] == "B1"  # unchanged


@pytest.mark.asyncio
async def test_update_batch_duplicate_name(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a batch to have duplicate name for same section fails"""
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

    batch1 = Batch(section_id=section.id, name="B1", batch_number=1, strength=15)
    batch2 = Batch(section_id=section.id, name="B2", batch_number=2, strength=15)
    db_session.add_all([batch1, batch2])
    await db_session.commit()

    response = await async_client.put(
        f"/api/v1/batches/{batch2.id}",
        json={"name": "B1"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_batch(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting a batch"""
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

    batch = Batch(section_id=section.id, name="B1", batch_number=1, strength=15)
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)

    response = await async_client.delete(f"/api/v1/batches/{batch.id}")
    assert response.status_code == 204

    # Verify deleted
    response = await async_client.get(f"/api/v1/batches/{batch.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_batch_not_found(async_client: AsyncClient):
    """Test deleting a non-existent batch returns 404"""
    response = await async_client.delete(f"/api/v1/batches/{uuid4()}")
    assert response.status_code == 404
