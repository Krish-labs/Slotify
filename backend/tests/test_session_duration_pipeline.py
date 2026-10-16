"""session_duration end to end: FacultyLoad -> TeachingAssignment -> scheduler -> entries.

Runs against in-memory SQLite (no Postgres needed).
"""

from datetime import date, time
from uuid import uuid4

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool

from app.database.connection import Base
from app.database.models import (
    AcademicTerm,
    AuditLog,
    Batch,
    Class,
    Faculty,
    FacultyLoad,
    Leave,
    LoadDistributionSourceRow,
    Notification,
    Resource,
    ResourceAvailability,
    Section,
    Subject,
    Substitution,
    TeachingAssignment,
    TimeSlot,
    Timetable,
    TimetableEntry,
    TimetableJob,
    TimetableTemplate,
    TimetableVersion,
    User,
)
from app.database.models.faculty_load import SessionType
from app.scheduler.solver import SolverConfig, TimetableSolver
from app.schemas.assignment import TeachingAssignmentCreate, TeachingAssignmentUpdate
from app.schemas.load import FacultyLoadCreate
from app.services.assignment_derivation_service import AssignmentDerivationService
from app.workers.timetable_worker import TimetableWorker, build_solver_input

YEAR, SEM = "2026-27", 1


@compiles(INET, "sqlite")
def _inet_as_text(type_, compiler, **kw):  # audit_logs.ip_address is Postgres-only
    return "VARCHAR(45)"


@pytest_asyncio.fixture
async def factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    models = (
        User, TimetableTemplate, AcademicTerm, Class, Subject, Faculty, Section, Batch,
        Resource, ResourceAvailability, TimeSlot, FacultyLoad, TeachingAssignment,
        Timetable, TimetableVersion, TimetableEntry, AuditLog, Notification,
        Leave, Substitution, LoadDistributionSourceRow, TimetableJob,
    )  # fmt: skip
    # Leave/ResourceAvailability/TimetableJob must exist: generation resolves
    # availability blocks and durable jobs against these tables. A subset
    # schema turns those reads into OperationalError ("no such table").
    tables = [Base.metadata.tables[m.__tablename__] for m in models]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed(factory, *, practical_hours=2, session_duration=2, n_batches=2, n_slots=6):
    """One section with `n_batches` batches doing the same lab, plus a 3h lecture."""
    async with factory() as db:
        user = User(email="gen@example.com", hashed_password="x")
        template = TimetableTemplate(name="T", academic_year=YEAR)
        term = AcademicTerm(
            name="Sem I", academic_year=YEAR, semester=SEM,
            start_date=date(2026, 7, 1), end_date=date(2026, 12, 1),
        )  # fmt: skip
        cls = Class(name="SE", year=2, branch="E&TC", academic_year=YEAR, strength=40)
        subject = Subject(code="EC1", name="Signals", subject_type="BOTH", semester=SEM)
        faculty = [
            Faculty(employee_id=f"E{i}", first_name="F", last_name=str(i), email=f"f{i}@x.com")
            for i in range(n_batches + 1)
        ]
        db.add_all([user, template, term, cls, subject, *faculty])
        await db.flush()

        section = Section(class_id=cls.id, name="A", strength=40)
        db.add(section)
        await db.flush()
        batches = [
            Batch(section_id=section.id, name=f"A{i}", batch_number=i, strength=20)
            for i in range(1, n_batches + 1)
        ]
        db.add_all(batches)
        await db.flush()

        db.add_all(
            [
                Resource(name="C1", resource_type="CLASSROOM", capacity=60),
                *[
                    Resource(name=f"L{i}", resource_type="HARDWARE_LAB", capacity=25)
                    for i in range(n_batches)
                ],
            ]
        )
        for p in range(1, n_slots + 1):
            db.add(
                TimeSlot(
                    template_id=template.id, day_of_week=0, period_number=p,
                    start_time=time(8 + p, 0), end_time=time(9 + p, 0),
                    slot_type="TEACHING", shift="MORNING",
                )
            )  # fmt: skip

        def load(fac, **kw):
            return FacultyLoad(
                faculty_id=fac.id, academic_term_id=term.id, subject_id=subject.id,
                class_id=cls.id, section_id=section.id, is_approved=True, **kw,
            )  # fmt: skip

        db.add(load(faculty[0], session_type=SessionType.THEORY, theory_hours=3))
        for fac, batch in zip(faculty[1:], batches, strict=True):
            db.add(
                load(
                    fac,
                    batch_id=batch.id,
                    session_type=SessionType.PRACTICAL,
                    practical_hours=practical_hours,
                    session_duration=session_duration,
                )
            )
        timetable = Timetable(
            name="Sem I", template_id=template.id, academic_year=YEAR, semester=SEM,
            generated_by=user.id,
        )  # fmt: skip
        db.add(timetable)
        await db.commit()
        return {"term_id": term.id, "timetable_id": timetable.id, "user_id": user.id}


def _worker(factory):
    solver = TimetableSolver(
        SolverConfig(time_limit_seconds=20, num_workers=1, log_search_progress=False)
    )
    return TimetableWorker(session_factory=factory, solver=solver)


# ------------------------------------------------------------------ derivation


async def test_derivation_copies_session_duration_to_practical_assignments(factory):
    ids = await _seed(factory, practical_hours=4, session_duration=2)

    async with factory() as db:
        result = await AssignmentDerivationService(db).derive_assignments(
            ids["term_id"], ids["user_id"]
        )
        assert result["errors"] == []
        rows = (await db.execute(select(TeachingAssignment))).scalars().all()

    by_type = {}
    for row in rows:
        by_type.setdefault(row.session_type.value, []).append(row)
    assert {r.session_duration for r in by_type["PRACTICAL"]} == {2}
    assert {r.hours_per_week for r in by_type["PRACTICAL"]} == {4}
    assert [r.session_duration for r in by_type["LECTURE"]] == [1]


async def test_session_duration_does_not_leak_onto_lectures_of_the_same_load(factory):
    ids = await _seed(factory, session_duration=2)
    async with factory() as db:
        load = (
            await db.execute(select(FacultyLoad).where(FacultyLoad.batch_id.is_(None)))
        ).scalar_one()
        load.practical_hours = 0
        load.session_duration = 3  # irrelevant: this load has no practicals
        await db.commit()
        await AssignmentDerivationService(db).derive_assignments(ids["term_id"], ids["user_id"])
        lecture = (
            await db.execute(
                select(TeachingAssignment).where(TeachingAssignment.batch_id.is_(None))
            )
        ).scalar_one()
    assert lecture.session_duration == 1


async def test_indivisible_practical_hours_are_reported_and_create_nothing(factory):
    ids = await _seed(factory, practical_hours=3, session_duration=2)

    async with factory() as db:
        result = await AssignmentDerivationService(db).derive_assignments(
            ids["term_id"], ids["user_id"]
        )
        practicals = (
            (
                await db.execute(
                    select(TeachingAssignment).where(TeachingAssignment.batch_id.is_not(None))
                )
            )
            .scalars()
            .all()
        )

    assert any("cannot be split into sessions of 2" in e for e in result["errors"])
    assert practicals == []
    assert result["derived"] == 1  # only the lecture


async def test_derivation_preview_shows_duration_and_flags_indivisible_hours(factory):
    ids = await _seed(factory, practical_hours=3, session_duration=2)
    async with factory() as db:
        preview = await AssignmentDerivationService(db).get_derivation_preview(ids["term_id"])
    practical = [
        a
        for item in preview["preview"]
        for a in item["assignments_to_create"]
        if a["session_type"] == "PRACTICAL"
    ]
    assert {a["session_duration"] for a in practical} == {2}
    assert any(item["has_ambiguity"] for item in preview["preview"])


# ------------------------------------------------------------------ schemas


def _load_payload(**kw):
    return {
        "faculty_id": uuid4(), "academic_term_id": uuid4(), "subject_id": uuid4(),
        "class_id": uuid4(), "section_id": uuid4(), **kw,
    }  # fmt: skip


def test_load_create_rejects_practical_hours_not_divisible_by_duration():
    with pytest.raises(ValidationError, match="multiple of"):
        FacultyLoadCreate(**_load_payload(practical_hours=3, session_duration=2))
    assert FacultyLoadCreate(**_load_payload(practical_hours=4, session_duration=2))
    assert FacultyLoadCreate(**_load_payload(theory_hours=3, session_duration=2))


def _assignment_payload(**kw):
    return {
        "faculty_id": uuid4(), "subject_id": uuid4(), "section_id": uuid4(),
        "session_type": "PRACTICAL", "academic_year": YEAR, "semester": SEM, **kw,
    }  # fmt: skip


def test_assignment_create_validates_duration():
    ok = TeachingAssignmentCreate(**_assignment_payload(hours_per_week=4, session_duration=2))
    assert ok.session_duration == 2
    assert TeachingAssignmentCreate(**_assignment_payload(hours_per_week=3)).session_duration == 1
    with pytest.raises(ValidationError):
        TeachingAssignmentCreate(**_assignment_payload(hours_per_week=3, session_duration=2))
    with pytest.raises(ValidationError):
        TeachingAssignmentCreate(**_assignment_payload(hours_per_week=2, session_duration=0))


def test_assignment_update_accepts_partial_fields():
    assert TeachingAssignmentUpdate(session_duration=2).hours_per_week is None


# ------------------------------------------------------------------ DB constraint


async def test_database_rejects_hours_not_divisible_by_duration(factory):
    from sqlalchemy.exc import IntegrityError

    ids = await _seed(factory)
    async with factory() as db:
        await AssignmentDerivationService(db).derive_assignments(ids["term_id"], ids["user_id"])
        lab = (
            await db.execute(
                select(TeachingAssignment).where(TeachingAssignment.batch_id.is_not(None))
            )
        ).scalars().first()  # fmt: skip
        lab.hours_per_week = 3  # duration is 2
        with pytest.raises(IntegrityError):
            await db.commit()


# ------------------------------------------------------------------ worker


async def _derive_and_generate(factory, **seed_kw):
    ids = await _seed(factory, **seed_kw)
    async with factory() as db:
        await AssignmentDerivationService(db).derive_assignments(ids["term_id"], ids["user_id"])
        # Derivation is a use case of the session it runs in; commit it so the
        # worker's independent sessions can read the derived assignments.
        await db.commit()
    result = await _worker(factory).generate_timetable(ids["timetable_id"])
    return ids, result


async def _practical_rows(factory):
    async with factory() as db:
        rows = (
            await db.execute(
                select(TimetableEntry, TimeSlot.period_number)
                .join(TimeSlot, TimeSlot.id == TimetableEntry.time_slot_id)
                .where(TimetableEntry.session_type == "PRACTICAL")
            )
        ).all()
    per_batch = {}
    for entry, period in rows:
        per_batch.setdefault(entry.batch_id, []).append((period, entry.resource_id))
    return {b: sorted(v) for b, v in per_batch.items()}


async def test_generated_timetable_has_contiguous_parallel_lab_blocks(factory):
    _, result = await _derive_and_generate(factory, practical_hours=2, session_duration=2)

    assert result.get("success") is True, result
    assert result["entries_count"] == 3 + 2 + 2

    per_batch = await _practical_rows(factory)
    assert len(per_batch) == 2
    period_sets = []
    for rows in per_batch.values():
        periods = [p for p, _ in rows]
        assert periods[1] == periods[0] + 1  # adjacent
        assert len({room for _, room in rows}) == 1  # same room for the whole block
        period_sets.append(periods)
    assert period_sets[0] == period_sets[1]  # batches run in parallel
    assert len({rows[0][1] for rows in per_batch.values()}) == 2  # in different rooms


async def test_four_hour_lab_is_stored_as_two_whole_blocks(factory):
    _, result = await _derive_and_generate(
        factory, practical_hours=4, session_duration=2, n_batches=1, n_slots=8
    )
    assert result.get("success") is True, result

    (rows,) = (await _practical_rows(factory)).values()
    periods = [p for p, _ in rows]
    assert len(periods) == 4
    # every maximal run of adjacent periods has an even length
    runs, run = [], 1
    for a, b in zip(periods, periods[1:], strict=False):
        if b == a + 1:
            run += 1
        else:
            runs.append(run)
            run = 1
    runs.append(run)
    assert all(r % 2 == 0 for r in runs), periods


async def test_infeasible_block_reports_a_reason_and_persists_nothing(factory):
    # 2 batches in parallel need 2 rooms, but only one (L0) stays active. Practicals
    # without a required lab type may also use classrooms, so deactivate those too.
    ids = await _seed(factory, practical_hours=2, session_duration=2)
    async with factory() as db:
        for resource in (
            (await db.execute(select(Resource).where(Resource.name.in_(["L1", "C1"]))))
            .scalars()
            .all()
        ):
            resource.is_active = False
        await db.commit()
        await AssignmentDerivationService(db).derive_assignments(ids["term_id"], ids["user_id"])
        await db.commit()

    result = await _worker(factory).generate_timetable(ids["timetable_id"])

    assert "INFEASIBLE" in result["error"]
    assert any("Parallel batches" in d for d in result["details"])
    async with factory() as db:
        assert (await db.execute(select(TimetableVersion))).first() is None


def test_build_solver_input_carries_session_duration():
    from types import SimpleNamespace

    a = SimpleNamespace(
        id=uuid4(), faculty_id=uuid4(), subject_id=uuid4(), section_id=uuid4(),
        batch_id=None, session_type="PRACTICAL", hours_per_week=4, session_duration=2,
        preferred_days=None, preferred_shifts=None,
    )  # fmt: skip
    solver_input = build_solver_input([a], [], [], sections={}, batches={})
    assert solver_input.assignments[0].session_duration == 2
