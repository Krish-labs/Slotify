from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.academic_term import AcademicTerm
from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.faculty import Faculty
from app.database.models.faculty_load import FacultyLoad, SessionType
from app.database.models.load_distribution_source import LoadDistributionSourceRow
from app.database.models.section import Section
from app.database.models.subject import Subject
from app.database.models.teaching_assignment import TeachingAssignment


@pytest.fixture
async def setup_test_data(db_session: AsyncSession):
    """Create test data for load tests"""
    # Faculty
    faculty = Faculty(
        employee_id="EMP100",
        first_name="Load",
        last_name="Faculty",
        email="load.faculty@example.com",
    )
    db_session.add(faculty)

    # Academic term
    term = AcademicTerm(
        name="2026-27 Sem I",
        academic_year="2026-27",
        semester=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31),
    )
    db_session.add(term)

    # Subject
    subject = Subject(
        code="ET101",
        name="Digital Electronics",
        subject_type="BOTH",
        credits=4,
        theory_hours=3,
        practical_hours=2,
        semester=1,
    )
    db_session.add(subject)

    # Class
    class_ = Class(
        name="SY",
        year=2,
        branch="E&TC",
        academic_year="2026-27",
        strength=60,
    )
    db_session.add(class_)

    await db_session.flush()

    # Section
    section = Section(
        class_id=class_.id,
        name="A",
        strength=30,
    )
    db_session.add(section)
    await db_session.flush()

    # Batch
    batch = Batch(
        section_id=section.id,
        name="A1",
        batch_number=1,
        strength=15,
    )
    db_session.add(batch)
    await db_session.flush()

    await db_session.commit()

    return {
        "faculty": faculty,
        "term": term,
        "subject": subject,
        "class": class_,
        "section": section,
        "batch": batch,
    }


@pytest.mark.asyncio
async def test_create_load(async_client: AsyncClient, setup_test_data: dict):
    """Test creating a faculty load record"""
    data = setup_test_data
    payload = {
        "faculty_id": str(data["faculty"].id),
        "academic_term_id": str(data["term"].id),
        "subject_id": str(data["subject"].id),
        "class_id": str(data["class"].id),
        "section_id": str(data["section"].id),
        "batch_id": str(data["batch"].id),
        "session_type": "THEORY",
        "theory_hours": 3,
        "practical_hours": 0,
        "tutorial_hours": 0,
        "project_hours": 0,
        "session_duration": 1,
        "required_resource_type": "CLASSROOM",
        "notes": "Test load",
    }

    response = await async_client.post("/api/v1/load", json=payload)
    assert response.status_code == 201
    result = response.json()
    assert result["faculty_id"] == str(data["faculty"].id)
    assert result["theory_hours"] == 3
    assert result["session_type"] == "THEORY"
    assert result["is_approved"] is False


@pytest.mark.asyncio
async def test_source_row_mapping_approval_derives_assignment(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    data = setup_test_data
    row = LoadDistributionSourceRow(
        source_file="Load Distribution.xlsx",
        source_sheet="Sheet1",
        source_semester="Semester I • 2026-27",
        source_row_number=1,
        faculty_name="Load Faculty",
        class_name="SY",
        subject_name="Digital Electronics",
        theory="3",
        practical="-",
        tutorial="-",
        project_stage="-",
        total_load="3",
        faculty_id=data["faculty"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        academic_term_id=data["term"].id,
        validation_errors=[],
    )
    db_session.add(row)
    await db_session.commit()

    response = await async_client.post(f"/api/v1/load/source/{row.id}/approve")

    assert response.status_code == 200, response.text
    assert response.json()["is_approved"] is True
    assert response.json()["assignments_created"] == 1
    assert (await db_session.execute(select(FacultyLoad))).scalars().first() is not None
    assert (await db_session.execute(select(TeachingAssignment))).scalars().first() is not None


@pytest.mark.asyncio
async def test_source_rows_are_listed_with_mapping_errors(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    row = LoadDistributionSourceRow(
        source_file="Load Distribution.xlsx",
        source_sheet="Sheet1",
        source_semester="Semester I • 2026-27",
        source_row_number=2,
        faculty_name="Unmapped Faculty",
        subject_name="Unmapped Subject",
        validation_errors=["Map Faculty", "Map Subject"],
    )
    db_session.add(row)
    await db_session.commit()

    response = await async_client.get("/api/v1/load/source")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["validation_errors"] == ["Map Faculty", "Map Subject"]


@pytest.mark.asyncio
async def test_create_load_practical_requires_batch(
    async_client: AsyncClient, setup_test_data: dict
):
    """Test that practical sessions require a batch"""
    data = setup_test_data
    payload = {
        "faculty_id": str(data["faculty"].id),
        "academic_term_id": str(data["term"].id),
        "subject_id": str(data["subject"].id),
        "class_id": str(data["class"].id),
        "section_id": str(data["section"].id),
        "batch_id": None,  # Missing batch for practical
        "session_type": "PRACTICAL",
        "theory_hours": 0,
        "practical_hours": 2,
        "tutorial_hours": 0,
        "project_hours": 0,
    }

    response = await async_client.post("/api/v1/load", json=payload)
    assert response.status_code == 400
    assert "batch" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_load_duplicate(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    """Test duplicate load detection"""
    data = setup_test_data
    payload = {
        "faculty_id": str(data["faculty"].id),
        "academic_term_id": str(data["term"].id),
        "subject_id": str(data["subject"].id),
        "class_id": str(data["class"].id),
        "section_id": str(data["section"].id),
        "batch_id": str(data["batch"].id),
        "session_type": "THEORY",
        "theory_hours": 3,
        "practical_hours": 0,
    }

    # Create first
    await async_client.post("/api/v1/load", json=payload)

    # Try duplicate
    response = await async_client.post("/api/v1/load", json=payload)
    assert response.status_code == 400
    assert "duplicate" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_list_loads(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    """Test listing loads"""
    data = setup_test_data

    # Create multiple loads with different session types to avoid unique constraint violation
    session_types = [SessionType.THEORY, SessionType.PRACTICAL, SessionType.TUTORIAL]
    for i, session_type in enumerate(session_types):
        load = FacultyLoad(
            faculty_id=data["faculty"].id,
            academic_term_id=data["term"].id,
            subject_id=data["subject"].id,
            class_id=data["class"].id,
            section_id=data["section"].id,
            batch_id=data["batch"].id if session_type == SessionType.PRACTICAL else None,
            session_type=session_type,
            theory_hours=3 if session_type == SessionType.THEORY else 0,
            practical_hours=2 if session_type == SessionType.PRACTICAL else 0,
            tutorial_hours=1 if session_type == SessionType.TUTORIAL else 0,
        )
        db_session.add(load)
    await db_session.commit()

    response = await async_client.get("/api/v1/load")
    assert response.status_code == 200
    result = response.json()
    assert result["total"] >= 3


@pytest.mark.asyncio
async def test_get_load(async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession):
    """Test getting a load by ID"""
    data = setup_test_data
    load = FacultyLoad(
        faculty_id=data["faculty"].id,
        academic_term_id=data["term"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=data["batch"].id,
        session_type=SessionType.THEORY,
        theory_hours=3,
    )
    db_session.add(load)
    await db_session.commit()
    await db_session.refresh(load)

    response = await async_client.get(f"/api/v1/load/{load.id}")
    assert response.status_code == 200
    result = response.json()
    assert result["id"] == str(load.id)
    assert result["theory_hours"] == 3


@pytest.mark.asyncio
async def test_update_load(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    """Test updating a load"""
    data = setup_test_data
    load = FacultyLoad(
        faculty_id=data["faculty"].id,
        academic_term_id=data["term"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=data["batch"].id,
        session_type=SessionType.THEORY,
        theory_hours=3,
    )
    db_session.add(load)
    await db_session.commit()
    await db_session.refresh(load)

    response = await async_client.put(
        f"/api/v1/load/{load.id}",
        json={"theory_hours": 4, "notes": "Updated"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["theory_hours"] == 4
    assert result["notes"] == "Updated"


@pytest.mark.asyncio
async def test_approve_load(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    """Test approving a load"""
    data = setup_test_data
    load = FacultyLoad(
        faculty_id=data["faculty"].id,
        academic_term_id=data["term"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=data["batch"].id,
        session_type=SessionType.THEORY,
        theory_hours=3,
    )
    db_session.add(load)
    await db_session.commit()
    await db_session.refresh(load)

    response = await async_client.patch(f"/api/v1/load/{load.id}/approve")
    assert response.status_code == 200
    result = response.json()
    assert result["is_approved"] is True
    assert result["approved_at"] is not None

    assignments = (
        (
            await db_session.execute(
                select(TeachingAssignment).where(
                    TeachingAssignment.academic_term_id == data["term"].id,
                    TeachingAssignment.faculty_id == data["faculty"].id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(assignments) == 1


@pytest.mark.asyncio
async def test_load_reports(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    """Test load summary reports"""
    data = setup_test_data

    # Create loads with different session types
    session_types = [SessionType.THEORY, SessionType.PRACTICAL, SessionType.TUTORIAL]
    for i, session_type in enumerate(session_types):
        load = FacultyLoad(
            faculty_id=data["faculty"].id,
            academic_term_id=data["term"].id,
            subject_id=data["subject"].id,
            class_id=data["class"].id,
            section_id=data["section"].id,
            batch_id=data["batch"].id if session_type == SessionType.PRACTICAL else None,
            session_type=session_type,
            theory_hours=3 if session_type == SessionType.THEORY else 0,
            practical_hours=2 if session_type == SessionType.PRACTICAL else 0,
            tutorial_hours=1 if session_type == SessionType.TUTORIAL else 0,
        )
        db_session.add(load)
    await db_session.commit()

    # Test faculty summary
    response = await async_client.get(
        f"/api/v1/load/reports/faculty-summary?academic_term_id={data['term'].id}"
    )
    assert response.status_code == 200
    result = response.json()
    assert "summary" in result

    # Test class summary
    response = await async_client.get(
        f"/api/v1/load/reports/class-summary?academic_term_id={data['term'].id}"
    )
    assert response.status_code == 200

    # Test subject summary
    response = await async_client.get(
        f"/api/v1/load/reports/subject-summary?academic_term_id={data['term'].id}"
    )
    assert response.status_code == 200

    # Test combined summary
    response = await async_client.get(
        f"/api/v1/load/reports/load-summary?academic_term_id={data['term'].id}"
    )
    assert response.status_code == 200
    result = response.json()
    assert "faculty_summary" in result
    assert "class_summary" in result
    assert "subject_summary" in result


def _mapped_row(data, subject, row_number=10, theory="3", practical="-"):
    return LoadDistributionSourceRow(
        source_file="Load Distribution.xlsx",
        source_sheet="Sheet1",
        source_semester="Semester I \u2022 2026-27",
        source_row_number=row_number,
        faculty_name="Load Faculty",
        class_name="SY",
        subject_name=subject.name,
        theory=theory,
        practical=practical,
        tutorial="-",
        project_stage="-",
        total_load="3",
        faculty_id=data["faculty"].id,
        subject_id=subject.id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=data["batch"].id if practical not in (None, "-", "") else None,
        academic_term_id=data["term"].id,
        validation_errors=[],
    )


@pytest.mark.asyncio
async def test_reapprove_row_derives_nothing_new(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    """Approving an already-approved row must not duplicate assignments."""
    from sqlalchemy import func

    data = setup_test_data
    db_session.add(_mapped_row(data, data["subject"]))
    await db_session.commit()
    row_id = (await db_session.execute(select(LoadDistributionSourceRow))).scalars().first().id

    first = await async_client.post(f"/api/v1/load/source/{row_id}/approve")
    assert first.status_code == 200, first.text
    assert first.json()["assignments_created"] == 1

    second = await async_client.post(f"/api/v1/load/source/{row_id}/approve")
    assert second.status_code == 200, second.text
    assert second.json()["assignments_created"] == 0

    n = (
        await db_session.execute(select(func.count()).select_from(TeachingAssignment))
    ).scalar_one()
    assert n == 1


@pytest.mark.asyncio
async def test_approve_derives_only_the_approved_row(
    async_client: AsyncClient, setup_test_data: dict, db_session: AsyncSession
):
    """Approving one row must not derive assignments for sibling loads."""
    data = setup_test_data
    other_subject = Subject(code="ET102", name="Signals", subject_type="BOTH", semester=1)
    db_session.add(other_subject)
    await db_session.flush()
    db_session.add(_mapped_row(data, data["subject"], row_number=10))
    db_session.add(_mapped_row(data, other_subject, row_number=11))
    await db_session.commit()
    rows = (
        (
            await db_session.execute(
                select(LoadDistributionSourceRow).order_by(
                    LoadDistributionSourceRow.source_row_number
                )
            )
        )
        .scalars()
        .all()
    )

    response = await async_client.post(f"/api/v1/load/source/{rows[0].id}/approve")
    assert response.status_code == 200, response.text

    assignments = (await db_session.execute(select(TeachingAssignment))).scalars().all()
    assert len(assignments) == 1
    assert assignments[0].subject_id == data["subject"].id
