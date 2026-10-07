from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.academic_term import AcademicTerm
from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.faculty import Faculty
from app.database.models.faculty_load import FacultyLoad, SessionType
from app.database.models.section import Section
from app.database.models.subject import Subject


@pytest.fixture
async def setup_derivation_data(db_session: AsyncSession):
    """Create test data for assignment derivation"""
    # Faculty
    faculty = Faculty(
        employee_id="EMP200",
        first_name="Derive",
        last_name="Faculty",
        email="derive.faculty@example.com",
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
        code="ET201",
        name="Data Structures",
        subject_type="BOTH",
        credits=4,
        theory_hours=3,
        practical_hours=2,
        semester=3,
    )
    db_session.add(subject)

    # Class
    class_ = Class(
        name="TY",
        year=3,
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
async def test_derive_assignments_preview(
    async_client: AsyncClient, setup_derivation_data: dict, db_session: AsyncSession
):
    """Test previewing assignment derivation"""
    data = setup_derivation_data

    # Create approved load with theory and practical
    load = FacultyLoad(
        faculty_id=data["faculty"].id,
        academic_term_id=data["term"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=data["batch"].id,
        session_type=SessionType.THEORY,
        theory_hours=3,
        practical_hours=2,
        is_approved=True,
    )
    db_session.add(load)
    await db_session.commit()

    response = await async_client.get(
        f"/api/v1/assignments/derive/preview?academic_term_id={data['term'].id}"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["total_loads"] == 1
    assert len(result["preview"]) == 1
    preview = result["preview"][0]
    assert preview["faculty"] == "Derive Faculty"
    assert len(preview["assignments_to_create"]) == 2  # Theory + Practical
    assert any(a["session_type"] == "LECTURE" for a in preview["assignments_to_create"])
    assert any(a["session_type"] == "PRACTICAL" for a in preview["assignments_to_create"])


@pytest.mark.asyncio
async def test_derive_assignments(
    async_client: AsyncClient, setup_derivation_data: dict, db_session: AsyncSession
):
    """Test deriving assignments from approved loads"""
    data = setup_derivation_data

    # Create approved loads
    loads = [
        FacultyLoad(
            faculty_id=data["faculty"].id,
            academic_term_id=data["term"].id,
            subject_id=data["subject"].id,
            class_id=data["class"].id,
            section_id=data["section"].id,
            batch_id=data["batch"].id,
            session_type=SessionType.THEORY,
            theory_hours=3,
            is_approved=True,
        ),
        FacultyLoad(
            faculty_id=data["faculty"].id,
            academic_term_id=data["term"].id,
            subject_id=data["subject"].id,
            class_id=data["class"].id,
            section_id=data["section"].id,
            batch_id=data["batch"].id,
            session_type=SessionType.PRACTICAL,
            practical_hours=2,
            is_approved=True,
        ),
    ]
    for load in loads:
        db_session.add(load)
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/assignments/derive?academic_term_id={data['term'].id}"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["derived"] >= 2  # At least 2 assignments (theory + practical)
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_derive_assignments_skip_existing(
    async_client: AsyncClient, setup_derivation_data: dict, db_session: AsyncSession
):
    """Test that derivation skips existing assignments by default"""
    data = setup_derivation_data

    # Create approved load
    load = FacultyLoad(
        faculty_id=data["faculty"].id,
        academic_term_id=data["term"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=data["batch"].id,
        session_type=SessionType.THEORY,
        theory_hours=3,
        is_approved=True,
    )
    db_session.add(load)
    await db_session.commit()
    await db_session.refresh(load)

    # Derive once
    await async_client.post(f"/api/v1/assignments/derive?academic_term_id={data['term'].id}")

    # Derive again - should skip
    response = await async_client.post(
        f"/api/v1/assignments/derive?academic_term_id={data['term'].id}"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["skipped"] >= 1


@pytest.mark.asyncio
async def test_derive_assignments_force(
    async_client: AsyncClient, setup_derivation_data: dict, db_session: AsyncSession
):
    """Test forcing derivation overwrites existing"""
    data = setup_derivation_data

    # Create approved load
    load = FacultyLoad(
        faculty_id=data["faculty"].id,
        academic_term_id=data["term"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=data["batch"].id,
        session_type=SessionType.THEORY,
        theory_hours=3,
        is_approved=True,
    )
    db_session.add(load)
    await db_session.commit()

    # Derive once
    await async_client.post(f"/api/v1/assignments/derive?academic_term_id={data['term'].id}")

    # Derive again with force
    response = await async_client.post(
        f"/api/v1/assignments/derive?academic_term_id={data['term'].id}&force=true"
    )
    assert response.status_code == 200
    result = response.json()
    assert result["derived"] >= 1


@pytest.mark.asyncio
async def test_derive_assignments_practical_requires_batch(
    async_client: AsyncClient, setup_derivation_data: dict, db_session: AsyncSession
):
    """Test that practical loads without batch are flagged"""
    data = setup_derivation_data

    # Create approved practical load WITHOUT batch
    load = FacultyLoad(
        faculty_id=data["faculty"].id,
        academic_term_id=data["term"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=None,  # No batch!
        session_type=SessionType.PRACTICAL,
        practical_hours=2,
        is_approved=True,
    )
    db_session.add(load)
    await db_session.commit()

    response = await async_client.get(
        f"/api/v1/assignments/derive/preview?academic_term_id={data['term'].id}"
    )
    assert response.status_code == 200
    result = response.json()
    preview = result["preview"][0]
    assert preview["has_ambiguity"] is True
    practical = next(
        a for a in preview["assignments_to_create"] if a["session_type"] == "PRACTICAL"
    )
    assert practical["requires_batch"] is True
    assert practical["batch_id"] is None
