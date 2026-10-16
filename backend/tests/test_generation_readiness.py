"""Generation-readiness endpoint: pre-generation checks surface before solving."""

import uuid
from datetime import date, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AcademicTerm,
    Class,
    Faculty,
    FacultyLoad,
    Resource,
    Section,
    Subject,
    TeachingAssignment,
    TimeSlot,
    Timetable,
    TimetableTemplate,
)

YEAR, SEM = "2026-27", 1


async def _seed_minimal(db: AsyncSession, with_slots: bool = True) -> Timetable:
    template = TimetableTemplate(name="T", academic_year=YEAR)
    db.add(template)
    await db.flush()
    timetable = Timetable(
        name="Gen", template_id=template.id, academic_year=YEAR, semester=SEM, status="DRAFT"
    )
    db.add(timetable)
    if with_slots:
        db.add(
            TimeSlot(
                template_id=template.id,
                day_of_week=0,
                period_number=1,
                start_time=time(8, 0),
                end_time=time(9, 0),
                slot_type="TEACHING",
                shift="MORNING",
            )
        )
    await db.commit()
    return timetable


async def _seed_full_chain(db: AsyncSession) -> Timetable:
    timetable = await _seed_minimal(db)
    term = AcademicTerm(
        name="Sem I",
        academic_year=YEAR,
        semester=SEM,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 1),
    )
    cls = Class(name="SE", year=2, branch="E&TC", academic_year=YEAR, strength=40)
    subject = Subject(code="EC1", name="Signals", subject_type="BOTH", semester=SEM)
    faculty = Faculty(employee_id="E1", first_name="F", last_name="L", email="f1@example.com")
    db.add_all([term, cls, subject, faculty])
    await db.flush()
    section = Section(class_id=cls.id, name="A", strength=40)
    db.add(section)
    await db.flush()
    load = FacultyLoad(
        faculty_id=faculty.id,
        academic_term_id=term.id,
        subject_id=subject.id,
        class_id=cls.id,
        section_id=section.id,
        batch_id=None,
        session_type="THEORY",
        theory_hours=3,
        session_duration=1,
        is_active=True,
        is_approved=True,
    )
    db.add(load)
    db.add(
        TeachingAssignment(
            faculty_id=faculty.id,
            academic_term_id=term.id,
            subject_id=subject.id,
            section_id=section.id,
            batch_id=None,
            session_type="LECTURE",
            hours_per_week=3,
            session_duration=1,
            is_active=True,
        )
    )
    db.add(Resource(name="C1", resource_type="CLASSROOM", capacity=60, is_active=True))
    await db.commit()
    return timetable


@pytest.mark.asyncio
async def test_readiness_reports_missing_term(async_client, db_session: AsyncSession):
    timetable = await _seed_minimal(db_session)
    response = await async_client.get(f"/api/v1/timetable/{timetable.id}/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert any("No academic term" in e for e in body["errors"])


@pytest.mark.asyncio
async def test_readiness_reports_missing_loads_and_assignments(
    async_client, db_session: AsyncSession
):
    timetable = await _seed_minimal(db_session)
    db_session.add(
        AcademicTerm(
            name="Sem I",
            academic_year=YEAR,
            semester=SEM,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 12, 1),
        )
    )
    await db_session.commit()
    response = await async_client.get(f"/api/v1/timetable/{timetable.id}/readiness")
    body = response.json()
    assert body["ready"] is False
    assert any("approved FacultyLoad" in e for e in body["errors"])


@pytest.mark.asyncio
async def test_readiness_ready_when_chain_complete(async_client, db_session: AsyncSession):
    timetable = await _seed_full_chain(db_session)
    response = await async_client.get(f"/api/v1/timetable/{timetable.id}/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True, body["errors"]
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_readiness_404_for_unknown_timetable(async_client):
    response = await async_client.get(f"/api/v1/timetable/{uuid.uuid4()}/readiness")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_workbook_readiness_exposes_unreviewed_source_rows(
    async_client, db_session: AsyncSession, monkeypatch, tmp_path
):
    from app.api import timetable as timetable_api
    from app.scheduler.workbook_demand import (
        DemandParseResult,
        SourceRowDisposition,
        WorkbookDemand,
    )

    timetable = await _seed_minimal(db_session)
    source = tmp_path / "source.xlsx"
    reference = tmp_path / "reference.xlsx"
    source.touch()
    reference.touch()
    monkeypatch.setattr(timetable_api, "source_workbook_path", lambda: source)
    monkeypatch.setattr(timetable_api, "timing_reference_path", lambda: reference)
    monkeypatch.setattr(timetable_api, "reference_teaching_times", lambda _path: [object()])
    monkeypatch.setattr(
        timetable_api,
        "parse_workbook_demand",
        lambda *_args, **_kwargs: DemandParseResult(
            source_file=source.name,
            semester="Semester I • 2026-27",
            rows_read=3,
            demands=(
                WorkbookDemand(1, "Semester I • 2026-27", "F", "FY", "S", "LECTURE", 1, 1, 0),
            ),
            invalid_rows=(),
            row_dispositions=tuple(
                SourceRowDisposition(row, "zero_load_review_required", "Review workload")
                for row in (54, 55, 98)
            ),
        ),
    )

    response = await async_client.get(
        f"/api/v1/timetable/{timetable.id}/workbook-readiness"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is False
    assert [row["source_row_number"] for row in body["row_dispositions"]] == [54, 55, 98]
    assert all(row["source_file"] == source.name for row in body["row_dispositions"])
