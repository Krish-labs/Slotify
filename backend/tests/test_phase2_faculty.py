import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.faculty import Faculty


@pytest.mark.asyncio
async def test_create_faculty(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating a faculty member"""
    payload = {
        "employee_id": "EMP001",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "1234567890",
        "department": "E&TC",
        "designation": "Assistant Professor",
        "joining_date": "2020-01-15",
    }

    response = await async_client.post("/api/v1/faculty", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["employee_id"] == "EMP001"
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert data["email"] == "john.doe@example.com"
    assert data["is_active"] is True
    assert data["is_archived"] is False
    assert "id" in data


@pytest.mark.asyncio
async def test_create_faculty_duplicate_employee_id(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test creating faculty with duplicate employee_id fails"""
    payload = {
        "employee_id": "EMP002",
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@example.com",
    }

    # Create first
    await async_client.post("/api/v1/faculty", json=payload)

    # Try to create duplicate
    payload["email"] = "different@example.com"
    response = await async_client.post("/api/v1/faculty", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_faculty(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing faculty"""
    # Create test faculty
    for i in range(3):
        faculty = Faculty(
            employee_id=f"EMP{i:03d}",
            first_name=f"Faculty{i}",
            last_name="Test",
            email=f"faculty{i}@example.com",
        )
        db_session.add(faculty)
    await db_session.commit()

    response = await async_client.get("/api/v1/faculty")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


@pytest.mark.asyncio
async def test_get_faculty(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting a faculty by ID"""
    faculty = Faculty(
        employee_id="EMP003",
        first_name="Test",
        last_name="Faculty",
        email="test.faculty@example.com",
    )
    db_session.add(faculty)
    await db_session.commit()
    await db_session.refresh(faculty)

    response = await async_client.get(f"/api/v1/faculty/{faculty.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(faculty.id)
    assert data["employee_id"] == "EMP003"


@pytest.mark.asyncio
async def test_update_faculty(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating a faculty"""
    faculty = Faculty(
        employee_id="EMP004",
        first_name="Original",
        last_name="Name",
        email="original@example.com",
    )
    db_session.add(faculty)
    await db_session.commit()
    await db_session.refresh(faculty)

    response = await async_client.put(
        f"/api/v1/faculty/{faculty.id}",
        json={"first_name": "Updated", "designation": "Professor"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Updated"
    assert data["designation"] == "Professor"


@pytest.mark.asyncio
async def test_archive_faculty(async_client: AsyncClient, db_session: AsyncSession):
    """Test archiving a faculty"""
    faculty = Faculty(
        employee_id="EMP005",
        first_name="ToArchive",
        last_name="Faculty",
        email="archive@example.com",
    )
    db_session.add(faculty)
    await db_session.commit()
    await db_session.refresh(faculty)

    response = await async_client.patch(f"/api/v1/faculty/{faculty.id}/archive")
    assert response.status_code == 200
    data = response.json()
    assert data["is_archived"] is True
    assert data["is_active"] is False
    assert data["archived_at"] is not None


@pytest.mark.asyncio
async def test_restore_faculty(async_client: AsyncClient, db_session: AsyncSession):
    """Test restoring an archived faculty"""
    faculty = Faculty(
        employee_id="EMP006",
        first_name="ToRestore",
        last_name="Faculty",
        email="restore@example.com",
        is_archived=True,
        is_active=False,
    )
    db_session.add(faculty)
    await db_session.commit()
    await db_session.refresh(faculty)

    response = await async_client.patch(f"/api/v1/faculty/{faculty.id}/restore")
    assert response.status_code == 200
    data = response.json()
    assert data["is_archived"] is False
    assert data["is_active"] is True
    assert data["archived_at"] is None


@pytest.mark.asyncio
async def test_delete_faculty(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting a faculty"""
    faculty = Faculty(
        employee_id="EMP007",
        first_name="ToDelete",
        last_name="Faculty",
        email="delete@example.com",
    )
    db_session.add(faculty)
    await db_session.commit()
    await db_session.refresh(faculty)

    response = await async_client.delete(f"/api/v1/faculty/{faculty.id}")
    assert response.status_code == 204

    # Verify deleted
    response = await async_client.get(f"/api/v1/faculty/{faculty.id}")
    assert response.status_code == 404
