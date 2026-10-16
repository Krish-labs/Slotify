"""Regression tests for derivation idempotency defects found on PostgreSQL.

A repeated full-term derivation duplicated every practical, tutorial, and
project assignment whose load carried no theory hours: the existence check
was keyed on ``load.session_type`` (always THEORY for approved source rows)
instead of on each derived component. Approving one source row also derived
the whole term. These tests pin the fixed behavior.
"""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.academic_term import AcademicTerm
from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.faculty import Faculty
from app.database.models.faculty_load import FacultyLoad, SessionType
from app.database.models.section import Section
from app.database.models.subject import Subject
from app.database.models.teaching_assignment import TeachingAssignment


@pytest.fixture
async def single_component_setup(db_session: AsyncSession):
    faculty = Faculty(
        employee_id="EMP300",
        first_name="Idem",
        last_name="Potent",
        email="idem.potent@example.com",
    )
    term = AcademicTerm(
        name="2026-27 Sem I",
        academic_year="2026-27",
        semester=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31),
    )
    subject = Subject(code="ET301", name="Idempotency 101", subject_type="BOTH", semester=1)
    class_ = Class(name="TY-IDEM", year=3, branch="E&TC", academic_year="2026-27")
    db_session.add_all([faculty, term, subject, class_])
    await db_session.flush()
    section = Section(class_id=class_.id, name="A")
    db_session.add(section)
    await db_session.flush()
    batch = Batch(section_id=section.id, name="A1", batch_number=1)
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


def _load(data, **hours):
    return FacultyLoad(
        faculty_id=data["faculty"].id,
        academic_term_id=data["term"].id,
        subject_id=data["subject"].id,
        class_id=data["class"].id,
        section_id=data["section"].id,
        batch_id=data["batch"].id,
        session_type=SessionType.THEORY,
        theory_hours=hours.get("theory_hours", 0),
        practical_hours=hours.get("practical_hours", 0),
        tutorial_hours=hours.get("tutorial_hours", 0),
        project_hours=hours.get("project_hours", 0),
        is_approved=True,
    )


async def _assignment_count(db_session: AsyncSession) -> int:
    return (
        await db_session.execute(select(func.count()).select_from(TeachingAssignment))
    ).scalar_one()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hours,expected_type",
    [
        ({"practical_hours": 2}, "PRACTICAL"),
        ({"tutorial_hours": 2}, "TUTORIAL"),
        ({"project_hours": 2}, "PROJECT"),
        ({"theory_hours": 3}, "LECTURE"),
        ({"theory_hours": 2, "practical_hours": 2}, "MIXED"),
    ],
)
async def test_repeated_derive_never_duplicates_components(
    async_client: AsyncClient,
    single_component_setup: dict,
    db_session: AsyncSession,
    hours: dict,
    expected_type: str,
):
    """Deriving twice (or N times) yields the same assignment set."""
    data = single_component_setup
    db_session.add(_load(data, **hours))
    await db_session.commit()

    first = await async_client.post(
        f"/api/v1/assignments/derive?academic_term_id={data['term'].id}"
    )
    assert first.status_code == 200, first.text
    n_after_first = await _assignment_count(db_session)

    second = await async_client.post(
        f"/api/v1/assignments/derive?academic_term_id={data['term'].id}"
    )
    assert second.status_code == 200, second.text
    assert second.json()["derived"] == 0
    assert await _assignment_count(db_session) == n_after_first
    assert n_after_first == len(hours)


@pytest.mark.asyncio
async def test_derive_creates_only_missing_components(
    async_client: AsyncClient, single_component_setup: dict, db_session: AsyncSession
):
    """A load whose lecture exists but practical does not derives just the practical."""
    from app.services.assignment_derivation_service import AssignmentDerivationService

    data = single_component_setup
    db_session.add(_load(data, theory_hours=2, practical_hours=2))
    await db_session.commit()

    async with db_session as session:
        service = AssignmentDerivationService(session)
        loads = (
            (
                await session.execute(
                    select(FacultyLoad).where(FacultyLoad.academic_term_id == data["term"].id)
                )
            )
            .scalars()
            .all()
        )
        first = await service.derive_load(loads[0], data["faculty"].id)
        assert first == {"derived": 2, "skipped": 0, "errors": []}

        # Delete the practical only: the next run must recreate exactly it.
        practical = (
            await session.execute(
                select(TeachingAssignment).where(TeachingAssignment.session_type == "PRACTICAL")
            )
        ).scalar_one()
        await session.delete(practical)
        await session.commit()

        second = await service.derive_load(loads[0], data["faculty"].id)
        assert second == {"derived": 1, "skipped": 1, "errors": []}
