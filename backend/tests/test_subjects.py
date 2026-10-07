from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.subject import Subject


@pytest.mark.asyncio
async def test_create_subject(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a subject"""
    payload = {
        "code": "EC101",
        "name": "Signals & Systems",
        "subject_type": "THEORY",
        "credits": 4,
        "theory_hours": 3,
        "practical_hours": 0,
        "tutorial_hours": 1,
        "semester": 3,
        "department": "E&TC",
    }

    response = await async_client.post("/api/v1/subjects", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "EC101"
    assert data["name"] == "Signals & Systems"
    assert data["subject_type"] == "THEORY"
    assert data["credits"] == 4
    assert "id" in data


@pytest.mark.asyncio
async def test_create_subject_duplicate_code(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a subject with duplicate code fails"""
    subject = Subject(
        code="EC101",
        name="Signals & Systems",
        subject_type="THEORY",
        semester=3,
    )
    db_session.add(subject)
    await db_session.commit()

    payload = {
        "code": "EC101",
        "name": "Different Name",
        "subject_type": "PRACTICAL",
        "semester": 4,
    }

    response = await async_client.post("/api/v1/subjects", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_subject(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting a subject by ID"""
    subject = Subject(
        code="EC101",
        name="Signals & Systems",
        subject_type="THEORY",
        credits=4,
        theory_hours=3,
        practical_hours=0,
        tutorial_hours=1,
        semester=3,
    )
    db_session.add(subject)
    await db_session.commit()
    await db_session.refresh(subject)

    response = await async_client.get(f"/api/v1/subjects/{subject.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "EC101"
    assert data["name"] == "Signals & Systems"


@pytest.mark.asyncio
async def test_get_subject_not_found(async_client: AsyncClient):
    """Test getting a non-existent subject returns 404"""
    response = await async_client.get(f"/api/v1/subjects/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_subjects(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing subjects with pagination"""
    subjects = [
        Subject(
            code="EC101", name="Signals & Systems", subject_type="THEORY", credits=4, semester=3
        ),
        Subject(
            code="EC102", name="Digital Electronics", subject_type="BOTH", credits=4, semester=3
        ),
        Subject(code="EC103", name="Network Theory", subject_type="THEORY", credits=3, semester=3),
        Subject(code="EC201", name="Microcontrollers", subject_type="BOTH", credits=4, semester=5),
    ]
    for s in subjects:
        db_session.add(s)
    await db_session.commit()

    response = await async_client.get("/api/v1/subjects")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert len(data["items"]) == 4


@pytest.mark.asyncio
async def test_list_subjects_filter_by_type(async_client: AsyncClient, db_session: AsyncSession):
    """Test filtering subjects by type"""
    subjects = [
        Subject(code="EC101", name="Signals & Systems", subject_type="THEORY", semester=3),
        Subject(code="EC102", name="Digital Electronics", subject_type="BOTH", semester=3),
        Subject(code="EC103", name="Digital Electronics Lab", subject_type="PRACTICAL", semester=3),
    ]
    for s in subjects:
        db_session.add(s)
    await db_session.commit()

    response = await async_client.get("/api/v1/subjects", params={"subject_type": "THEORY"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["subject_type"] == "THEORY"


@pytest.mark.asyncio
async def test_list_subjects_filter_by_semester(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test filtering subjects by semester"""
    subjects = [
        Subject(code="EC101", name="Signals & Systems", subject_type="THEORY", semester=3),
        Subject(code="EC201", name="Microcontrollers", subject_type="BOTH", semester=5),
    ]
    for s in subjects:
        db_session.add(s)
    await db_session.commit()

    response = await async_client.get("/api/v1/subjects", params={"semester": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["semester"] == 3


@pytest.mark.asyncio
async def test_list_subjects_search(async_client: AsyncClient, db_session: AsyncSession):
    """Test searching subjects by code or name"""
    subjects = [
        Subject(code="EC101", name="Signals & Systems", subject_type="THEORY", semester=3),
        Subject(code="EC102", name="Digital Electronics", subject_type="BOTH", semester=3),
    ]
    for s in subjects:
        db_session.add(s)
    await db_session.commit()

    response = await async_client.get("/api/v1/subjects", params={"search": "EC101"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["code"] == "EC101"


@pytest.mark.asyncio
async def test_update_subject(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a subject"""
    subject = Subject(
        code="EC101",
        name="Signals & Systems",
        subject_type="THEORY",
        credits=4,
        theory_hours=3,
        practical_hours=0,
        tutorial_hours=1,
        semester=3,
    )
    db_session.add(subject)
    await db_session.commit()
    await db_session.refresh(subject)

    response = await async_client.put(
        f"/api/v1/subjects/{subject.id}",
        json={"credits": 5, "theory_hours": 4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["credits"] == 5
    assert data["theory_hours"] == 4
    assert data["code"] == "EC101"  # unchanged


@pytest.mark.asyncio
async def test_update_subject_duplicate_code(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a subject to have duplicate code fails"""
    # Use unique codes to avoid conflicts with previous test runs
    unique_suffix = uuid4().hex[:8]
    code1 = f"EC101_{unique_suffix}"
    code2 = f"EC102_{unique_suffix}"
    dup_code = code1

    subject1 = Subject(code=code1, name="Signals & Systems", subject_type="THEORY", semester=3)
    subject2 = Subject(code=code2, name="Digital Electronics", subject_type="BOTH", semester=3)
    db_session.add_all([subject1, subject2])
    await db_session.commit()

    response = await async_client.put(
        f"/api/v1/subjects/{subject2.id}",
        json={"code": dup_code},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_subject(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting a subject"""
    subject = Subject(
        code="EC101",
        name="Signals & Systems",
        subject_type="THEORY",
        credits=4,
        semester=3,
    )
    db_session.add(subject)
    await db_session.commit()
    await db_session.refresh(subject)

    response = await async_client.delete(f"/api/v1/subjects/{subject.id}")
    assert response.status_code == 204

    # Verify deleted
    response = await async_client.get(f"/api/v1/subjects/{subject.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_subject_not_found(async_client: AsyncClient):
    """Test deleting a non-existent subject returns 404"""
    response = await async_client.delete(f"/api/v1/subjects/{uuid4()}")
    assert response.status_code == 404
