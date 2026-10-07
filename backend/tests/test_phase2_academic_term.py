from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.academic_term import AcademicTerm


@pytest.mark.asyncio
async def test_create_academic_term(async_client: AsyncClient):
    """Test creating an academic term"""
    payload = {
        "name": "2026-27 Sem I",
        "academic_year": "2026-27",
        "semester": 1,
        "start_date": "2026-07-01",
        "end_date": "2026-12-31",
        "is_active": True,
        "is_current": True,
    }

    response = await async_client.post("/api/v1/academic-terms", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "2026-27 Sem I"
    assert data["academic_year"] == "2026-27"
    assert data["semester"] == 1
    assert data["is_current"] is True


@pytest.mark.asyncio
async def test_create_academic_term_duplicate(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating duplicate academic term fails"""
    term = AcademicTerm(
        name="2026-27 Sem I",
        academic_year="2026-27",
        semester=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31),
    )
    db_session.add(term)
    await db_session.commit()

    payload = {
        "name": "2026-27 Sem I Duplicate",
        "academic_year": "2026-27",
        "semester": 1,
        "start_date": "2026-07-01",
        "end_date": "2026-12-31",
    }

    response = await async_client.post("/api/v1/academic-terms", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_academic_terms(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing academic terms"""
    for i in range(1, 4):
        term = AcademicTerm(
            name=f"2025-26 Sem {i}",
            academic_year="2025-26",
            semester=i,
            start_date=date(2025, 7, 1),
            end_date=date(2025, 12, 31),
        )
        db_session.add(term)
    await db_session.commit()

    response = await async_client.get("/api/v1/academic-terms")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_get_current_academic_term(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting current academic term"""
    # Create non-current term
    term1 = AcademicTerm(
        name="2025-26 Sem I",
        academic_year="2025-26",
        semester=1,
        start_date=date(2025, 7, 1),
        end_date=date(2025, 12, 31),
        is_current=False,
    )
    db_session.add(term1)

    # Create current term
    term2 = AcademicTerm(
        name="2026-27 Sem I",
        academic_year="2026-27",
        semester=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31),
        is_current=True,
    )
    db_session.add(term2)
    await db_session.commit()

    response = await async_client.get("/api/v1/academic-terms/current")
    assert response.status_code == 200
    data = response.json()
    assert data["is_current"] is True
    assert data["academic_year"] == "2026-27"


@pytest.mark.asyncio
async def test_get_academic_term(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting academic term by ID"""
    term = AcademicTerm(
        name="2026-27 Sem I",
        academic_year="2026-27",
        semester=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31),
    )
    db_session.add(term)
    await db_session.commit()
    await db_session.refresh(term)

    response = await async_client.get(f"/api/v1/academic-terms/{term.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(term.id)
    assert data["semester"] == 1


@pytest.mark.asyncio
async def test_update_academic_term(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating academic term"""
    term = AcademicTerm(
        name="2026-27 Sem I",
        academic_year="2026-27",
        semester=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31),
    )
    db_session.add(term)
    await db_session.commit()
    await db_session.refresh(term)

    response = await async_client.put(
        f"/api/v1/academic-terms/{term.id}",
        json={"name": "Updated Name", "is_current": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["is_current"] is True


@pytest.mark.asyncio
async def test_delete_academic_term(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting academic term"""
    term = AcademicTerm(
        name="2026-27 Sem I",
        academic_year="2026-27",
        semester=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31),
    )
    db_session.add(term)
    await db_session.commit()
    await db_session.refresh(term)

    response = await async_client.delete(f"/api/v1/academic-terms/{term.id}")
    assert response.status_code == 204

    # Verify deleted
    response = await async_client.get(f"/api/v1/academic-terms/{term.id}")
    assert response.status_code == 404
