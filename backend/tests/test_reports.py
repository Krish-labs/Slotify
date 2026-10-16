from datetime import date, time
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.database.models import (
    Class,
    Faculty,
    FacultyLoad,
    Resource,
    Section,
    Subject,
    TimeSlot,
    Timetable,
    TimetableEntry,
    TimetableTemplate,
    TimetableVersion,
    User,
)
from app.database.models.academic_term import AcademicTerm


async def _create_test_user(db_session: AsyncSession) -> User:
    """Helper to create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("password"),
        full_name="Test User",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _create_test_timetable(db_session: AsyncSession, user: User) -> tuple:
    """Helper to create a complete test timetable with all required relationships."""
    # Create template
    template = TimetableTemplate(name="Test Template", academic_year="2025-26")
    db_session.add(template)
    await db_session.flush()

    # Create time slots
    time_slots = [
        TimeSlot(
            template_id=template.id,
            day_of_week=0,
            period_number=1,
            start_time=time(8, 0),
            end_time=time(8, 50),
            slot_type="TEACHING",
            shift="MORNING",
        ),
        TimeSlot(
            template_id=template.id,
            day_of_week=0,
            period_number=2,
            start_time=time(8, 50),
            end_time=time(9, 40),
            slot_type="TEACHING",
            shift="MORNING",
        ),
    ]
    for ts in time_slots:
        db_session.add(ts)
    await db_session.flush()

    # Create faculty for entries
    faculty1 = Faculty(
        employee_id="EMP001",
        first_name="John",
        last_name="Doe",
        email="john.doe@college.edu",
        department="E&TC",
        designation="Professor",
    )
    faculty2 = Faculty(
        employee_id="EMP002",
        first_name="Jane",
        last_name="Smith",
        email="jane.smith@college.edu",
        department="E&TC",
        designation="Associate Professor",
    )
    db_session.add_all([faculty1, faculty2])
    await db_session.flush()

    # Create subject, class, section for entries
    subject = Subject(code="EC101", name="Signals", subject_type="THEORY", semester=1)
    class_obj = Class(name="SE", year=2, branch="E&TC", academic_year="2025-26", strength=60)
    db_session.add_all([subject, class_obj])
    await db_session.flush()

    section = Section(class_id=class_obj.id, name="A", strength=30)
    db_session.add(section)
    await db_session.flush()

    # Create resources for entries
    resource1 = Resource(name="LH-101", resource_type="CLASSROOM", capacity=60)
    resource2 = Resource(name="LH-102", resource_type="CLASSROOM", capacity=60)
    db_session.add_all([resource1, resource2])
    await db_session.flush()

    # Create template
    template = TimetableTemplate(name="Test Template", academic_year="2025-26")
    db_session.add(template)
    await db_session.flush()

    # Create time slots
    time_slots = [
        TimeSlot(
            template_id=template.id,
            day_of_week=0,
            period_number=1,
            start_time=time(8, 0),
            end_time=time(8, 50),
            slot_type="TEACHING",
            shift="MORNING",
        ),
        TimeSlot(
            template_id=template.id,
            day_of_week=0,
            period_number=2,
            start_time=time(8, 50),
            end_time=time(9, 40),
            slot_type="TEACHING",
            shift="MORNING",
        ),
    ]
    for ts in time_slots:
        db_session.add(ts)
    await db_session.flush()

    # Create timetable
    timetable = Timetable(
        name="Test Timetable",
        template_id=template.id,
        academic_year="2025-26",
        semester=1,
        status="PUBLISHED",
    )
    db_session.add(timetable)
    await db_session.flush()

    # Create version with created_by
    version = TimetableVersion(
        timetable_id=timetable.id,
        version_number=1,
        status="VALIDATED",
        change_type="FULL_REGENERATION",
        created_by=user.id,
    )
    db_session.add(version)
    await db_session.flush()

    # Create entries
    entries = [
        TimetableEntry(
            version_id=version.id,
            faculty_id=faculty1.id,
            subject_id=subject.id,
            section_id=section.id,
            resource_id=resource1.id,
            time_slot_id=time_slots[0].id,
            day_of_week=0,
            period_number=1,
            session_type="LECTURE",
        ),
        TimetableEntry(
            version_id=version.id,
            faculty_id=faculty2.id,
            subject_id=subject.id,
            section_id=section.id,
            resource_id=resource2.id,
            time_slot_id=time_slots[1].id,
            day_of_week=0,
            period_number=2,
            session_type="LECTURE",
        ),
    ]
    for e in entries:
        db_session.add(e)
    await db_session.commit()

    return timetable, version, time_slots, faculty1, faculty2, resource1, resource2


@pytest.mark.asyncio
async def test_timetable_summary_report(async_client: AsyncClient, db_session: AsyncSession):
    """Test timetable summary report"""
    user = await _create_test_user(db_session)
    (
        timetable,
        version,
        time_slots,
        faculty1,
        faculty2,
        resource1,
        resource2,
    ) = await _create_test_timetable(db_session, user)

    response = await async_client.get(
        "/api/v1/reports/timetable-summary",
        params={"timetable_id": str(timetable.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["timetable_id"] == str(timetable.id)
    assert data["version_number"] == 1
    assert data["total_entries"] == 2


@pytest.mark.asyncio
async def test_timetable_summary_report_honors_selected_version(
    async_client: AsyncClient, db_session: AsyncSession
):
    """A report view must not silently replace the user's selected version with the latest one."""
    user = await _create_test_user(db_session)
    timetable, version, *_ = await _create_test_timetable(db_session, user)
    newer = TimetableVersion(
        timetable_id=timetable.id,
        version_number=2,
        status="GENERATED",
        change_type="FULL_REGENERATION",
        created_by=user.id,
    )
    db_session.add(newer)
    await db_session.commit()

    latest_response = await async_client.get(
        "/api/v1/reports/timetable-summary",
        params={"timetable_id": str(timetable.id)},
    )
    assert latest_response.status_code == 200
    assert latest_response.json()["version_number"] == 2
    assert latest_response.json()["total_entries"] == 0

    selected_response = await async_client.get(
        "/api/v1/reports/timetable-summary",
        params={"timetable_id": str(timetable.id), "version_id": str(version.id)},
    )
    assert selected_response.status_code == 200
    assert selected_response.json()["version_number"] == 1
    assert selected_response.json()["total_entries"] == 2


@pytest.mark.asyncio
async def test_timetable_summary_report_not_found(async_client: AsyncClient):
    """Test timetable summary report with non-existent timetable"""
    from uuid import uuid4

    response = await async_client.get(
        "/api/v1/reports/timetable-summary",
        params={"timetable_id": str(uuid4())},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_faculty_load_report(async_client: AsyncClient, db_session: AsyncSession):
    """Test faculty load report"""

    term = AcademicTerm(
        name="Sem I",
        academic_year="2025-26",
        semester=1,
        start_date=date(2025, 7, 1),
        end_date=date(2025, 12, 31),
    )
    db_session.add(term)
    await db_session.flush()

    # Create faculty and loads
    faculty = Faculty(
        employee_id="EMP001",
        first_name="John",
        last_name="Doe",
        email="john.doe@college.edu",
        department="E&TC",
        designation="Professor",
    )
    db_session.add(faculty)
    await db_session.flush()

    subject = Subject(code="EC101", name="Signals", subject_type="THEORY", semester=1)
    class_obj = Class(name="SE", year=2, branch="E&TC", academic_year="2025-26", strength=60)
    db_session.add_all([subject, class_obj])
    await db_session.flush()

    section = Section(class_id=class_obj.id, name="A", strength=30)
    db_session.add(section)
    await db_session.flush()

    load = FacultyLoad(
        faculty_id=faculty.id,
        academic_term_id=term.id,
        subject_id=subject.id,
        class_id=class_obj.id,
        section_id=section.id,
        session_type="THEORY",
        theory_hours=3,
        practical_hours=0,
        tutorial_hours=0,
        project_hours=0,
        session_duration=1,
        is_active=True,
        is_approved=True,
    )
    db_session.add(load)
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/reports/faculty-load",
        params={"academic_term_id": str(term.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["academic_term_id"] == str(term.id)
    assert "summary" in data


@pytest.mark.asyncio
async def test_conflicts_report(async_client: AsyncClient, db_session: AsyncSession):
    """Test conflicts report"""
    user = await _create_test_user(db_session)
    (
        timetable,
        version,
        time_slots,
        faculty1,
        faculty2,
        resource1,
        resource2,
    ) = await _create_test_timetable(db_session, user)

    # The conflict detection is done at the validation level, not DB constraint level.
    # Test with a valid timetable - no conflicts in the base setup
    response = await async_client.get(
        "/api/v1/reports/conflicts",
        params={"timetable_id": str(timetable.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["timetable_id"] == str(timetable.id)
    # No conflicts in the base setup
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_validation_report(async_client: AsyncClient, db_session: AsyncSession):
    """Test validation report"""
    user = await _create_test_user(db_session)
    (
        timetable,
        version,
        time_slots,
        faculty1,
        faculty2,
        resource1,
        resource2,
    ) = await _create_test_timetable(db_session, user)

    response = await async_client.get(
        "/api/v1/reports/validation",
        params={"timetable_id": str(timetable.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["timetable_id"] == str(timetable.id)
    assert "status" in data
    assert data["total_entries"] == 2


@pytest.mark.asyncio
async def test_resource_utilization_report(async_client: AsyncClient, db_session: AsyncSession):
    """Test resource utilization report"""
    # This test requires access to the subject and section from the helper
    # We'll create a minimal setup here
    user = await _create_test_user(db_session)

    # Create template
    template = TimetableTemplate(name="Test Template", academic_year="2025-26")
    db_session.add(template)
    await db_session.flush()

    # Create time slot
    time_slot_id = uuid4()
    time_slot = TimeSlot(
        id=time_slot_id,
        template_id=template.id,
        day_of_week=0,
        period_number=1,
        start_time=time(8, 0),
        end_time=time(8, 50),
        slot_type="TEACHING",
        shift="MORNING",
    )
    db_session.add(time_slot)
    await db_session.flush()

    # Create faculty
    faculty = Faculty(
        employee_id="EMP001",
        first_name="John",
        last_name="Doe",
        email="john.doe@college.edu",
        department="E&TC",
        designation="Professor",
    )
    db_session.add(faculty)
    await db_session.flush()

    # Create subject, class, section
    subject = Subject(code="EC101", name="Signals", subject_type="THEORY", semester=1)
    class_obj = Class(name="SE", year=2, branch="E&TC", academic_year="2025-26", strength=60)
    db_session.add_all([subject, class_obj])
    await db_session.flush()

    section = Section(class_id=class_obj.id, name="A", strength=30)
    db_session.add(section)
    await db_session.flush()

    # Create resource
    resource = Resource(name="LH-101", resource_type="CLASSROOM", capacity=60)
    db_session.add(resource)
    await db_session.flush()

    # Create timetable
    timetable = Timetable(
        name="Test Timetable",
        template_id=template.id,
        academic_year="2025-26",
        semester=1,
        status="PUBLISHED",
    )
    db_session.add(timetable)
    await db_session.flush()

    # Create version
    version = TimetableVersion(
        timetable_id=timetable.id,
        version_number=1,
        status="VALIDATED",
        change_type="FULL_REGENERATION",
        created_by=user.id,
    )
    db_session.add(version)
    await db_session.flush()

    # Create entry
    entry = TimetableEntry(
        version_id=version.id,
        faculty_id=faculty.id,
        subject_id=subject.id,
        section_id=section.id,
        resource_id=resource.id,
        time_slot_id=time_slot_id,
        day_of_week=0,
        period_number=1,
        session_type="LECTURE",
    )
    db_session.add(entry)
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/reports/resource-utilization",
        params={"timetable_id": str(timetable.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["timetable_id"] == str(timetable.id)
    assert "utilization" in data

    response = await async_client.get(
        "/api/v1/reports/resource-utilization",
        params={"timetable_id": str(timetable.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["timetable_id"] == str(timetable.id)
    assert "utilization" in data
