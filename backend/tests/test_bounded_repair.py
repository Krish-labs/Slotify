"""Bounded repair workflow: retry limits, approval gates, audit, integrity.

Runs against in-memory SQLite (no Postgres needed). Full schema on purpose:
subset fixtures turn availability/job reads into OperationalError instead of
real results (see the test_session_duration_pipeline fixture fix).
"""

from datetime import date, time

import pytest_asyncio
from sqlalchemy import func, select
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
    Resource,
    Section,
    Subject,
    TeachingAssignment,
    TimeSlot,
    Timetable,
    TimetableTemplate,
    TimetableVersion,
    User,
)
from app.database.models.leave import Leave
from app.scheduler.solver import SolverConfig, TimetableSolver
from app.schemas.repair import (
    ABSOLUTE_MAX_REPAIR_ATTEMPTS,
    DEFAULT_MAX_REPAIR_ATTEMPTS,
)
from app.services.repair_service import (
    RepairService,
)
from app.workers.timetable_worker import TimetableWorker

YEAR, SEM = "2026-27", 1


@compiles(INET, "sqlite")
def _inet_as_text(type_, compiler, **kw):  # audit_logs.ip_address is Postgres-only
    return "VARCHAR(45)"


@pytest_asyncio.fixture
async def factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _solver():
    return TimetableSolver(
        SolverConfig(time_limit_seconds=20, num_workers=1, log_search_progress=False)
    )


def _repair(factory):
    return RepairService(session_factory=factory, solver=_solver())


async def _seed(
    factory, *, lecture_hours=2, n_slots=3, n_days=2, with_leave=False, practical=False
):
    """One section; a lecture plus optionally parallel 1h practicals per batch."""
    async with factory() as db:
        user = User(email="repair@example.com", hashed_password="x")
        template = TimetableTemplate(name="T", academic_year=YEAR)
        term = AcademicTerm(
            name="Sem I", academic_year=YEAR, semester=SEM,
            start_date=date(2026, 7, 1), end_date=date(2026, 12, 1),
        )  # fmt: skip
        cls = Class(name="SE", year=2, branch="E&TC", academic_year=YEAR, strength=40)
        subject = Subject(code="EC1", name="Signals", subject_type="BOTH", semester=SEM)
        f_lec = Faculty(employee_id="E1", first_name="F", last_name="1", email="f1@x.com")
        db.add_all([user, template, term, cls, subject, f_lec])
        await db.flush()

        section = Section(class_id=cls.id, name="A", strength=40)
        db.add(section)
        await db.flush()

        assignments = [
            TeachingAssignment(
                faculty_id=f_lec.id,
                academic_term_id=term.id,
                subject_id=subject.id,
                section_id=section.id,
                session_type="LECTURE",
                hours_per_week=lecture_hours,
            )
        ]
        lab = Resource(name="C1", resource_type="CLASSROOM", capacity=60)
        db.add(lab)
        resources = [lab]
        if practical:
            batch_rows = []
            for i in (1, 2):
                fac = Faculty(
                    employee_id=f"EP{i}",
                    first_name="P",
                    last_name=str(i),
                    email=f"p{i}@x.com",
                )
                db.add(fac)
                await db.flush()
                batch = Batch(section_id=section.id, name=f"A{i}", batch_number=i, strength=20)
                db.add(batch)
                await db.flush()
                batch_rows.append((fac, batch))
                assignments.append(
                    TeachingAssignment(
                        faculty_id=fac.id,
                        academic_term_id=term.id,
                        subject_id=subject.id,
                        section_id=section.id,
                        batch_id=batch.id,
                        session_type="PRACTICAL",
                        hours_per_week=1,
                        required_lab_type="HARDWARE_LAB",
                    )
                )
            lab2 = Resource(name="L1", resource_type="HARDWARE_LAB", capacity=25)
            lab3 = Resource(name="L2", resource_type="HARDWARE_LAB", capacity=25)
            db.add_all([lab2, lab3])
            await db.flush()
            resources.extend([lab2, lab3])
            extra_lab = lab2
        else:
            extra_lab = None
        db.add_all(assignments)
        for day in range(n_days):
            for p in range(1, n_slots + 1):
                db.add(
                    TimeSlot(
                        template_id=template.id, day_of_week=day, period_number=p,
                        start_time=time(8 + p, 0), end_time=time(9 + p, 0),
                        slot_type="TEACHING", shift="MORNING",
                    )
                )  # fmt: skip
        if with_leave:
            db.add(
                Leave(
                    faculty_id=f_lec.id,
                    leave_type="CASUAL",
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                    status="APPROVED",
                )
            )
        timetable = Timetable(
            name="Sem I", template_id=template.id, academic_year=YEAR, semester=SEM,
            generated_by=user.id,
        )  # fmt: skip
        db.add(timetable)
        await db.commit()
        return {
            "timetable_id": timetable.id,
            "user_id": user.id,
            "faculty_id": f_lec.id,
            "extra_lab_id": extra_lab.id if extra_lab else None,
        }


async def _generate(factory, timetable_id):
    worker = TimetableWorker(session_factory=factory, solver=_solver())
    return await worker.generate_timetable(timetable_id)


async def _version_count(factory):
    async with factory() as db:
        return (await db.execute(select(func.count()).select_from(TimetableVersion))).scalar_one()


# ------------------------------------------------------------------ outcomes


async def test_repair_is_a_noop_when_the_latest_version_validates(factory):
    ids = await _seed(factory)
    generated = await _generate(factory, ids["timetable_id"])
    assert generated.get("success") is True, generated

    result = await _repair(factory).repair_timetable(ids["timetable_id"], ids["user_id"])

    assert result["repaired"] is False
    assert result["repair_attempts"] == 0
    assert result["validation_status"] == "PASS"
    assert await _version_count(factory) == 1


async def test_repair_exhausted_returns_diagnostics_and_persists_nothing(factory):
    ids = await _seed(factory, lecture_hours=9, n_slots=3, n_days=1)

    result = await _repair(factory).repair_timetable(
        ids["timetable_id"], ids["user_id"], max_retries=2
    )

    assert "error" in result
    assert result["stage"] == "repair_exhausted"
    assert result["outcome"] in ("infeasible", "incomplete")
    assert 1 <= result["repair_attempts"] <= DEFAULT_MAX_REPAIR_ATTEMPTS
    assert result["original_diagnostics"], "original diagnostics must be returned"
    assert result["unscheduled"], "unscheduled demand must be explicit"
    # Failed repair cannot leave partial entries or a validated version.
    assert await _version_count(factory) == 0
    async with factory() as db:
        assert (await db.get(Timetable, ids["timetable_id"])).status == "DRAFT"
        failed = (
            (await db.execute(select(AuditLog).where(AuditLog.action == "REPAIR_FAILED")))
            .scalars()
            .all()
        )
        assert len(failed) == 1
        assert failed[0].new_values["repair_attempts"] == result["repair_attempts"]


async def test_repair_retry_limit_caps_attempts(factory):
    ids = await _seed(factory, lecture_hours=9, n_slots=3, n_days=1)
    adjustments = [
        {"kind": "extend_time_limit", "time_limit_seconds": 5, "reason": f"try {i}"}
        for i in range(3)
    ]

    result = await _repair(factory).repair_timetable(
        ids["timetable_id"],
        ids["user_id"],
        adjustments=adjustments,
        max_retries=2,
    )

    assert result["repair_attempts"] == 2
    assert len(result["attempts"]) == 2
    assert len(result["not_attempted"]) == 1
    assert await _version_count(factory) == 0


async def test_repair_rejects_out_of_range_retry_bounds(factory):
    ids = await _seed(factory)

    for bad in (0, ABSOLUTE_MAX_REPAIR_ATTEMPTS + 1):
        result = await _repair(factory).repair_timetable(
            ids["timetable_id"], ids["user_id"], max_retries=bad
        )
        assert "error" in result and result["repair_attempts"] == 0


# ------------------------------------------------------------------ approval


async def test_repair_requires_approval_for_availability_overrides(factory):
    ids = await _seed(factory)

    result = await _repair(factory).repair_timetable(
        ids["timetable_id"],
        ids["user_id"],
        adjustments=[
            {
                "kind": "lift_availability_block",
                "faculty_slot_ids": [str(ids["faculty_id"])],
                "reason": "no approval",
            }
        ],
    )

    assert result["stage"] == "approval_required"
    assert result["repair_attempts"] == 0
    assert "approve_hard_relaxation" in result["error"]


async def test_repair_rejects_unsupported_adjustment_kinds(factory):
    ids = await _seed(factory)

    result = await _repair(factory).repair_timetable(
        ids["timetable_id"],
        ids["user_id"],
        adjustments=[{"kind": "ignore_faculty_conflict", "reason": "hard rules stay hard"}],
    )

    assert result["stage"] == "adjustment_validation"
    assert result["repair_attempts"] == 0
    assert "full_regeneration" in result["supported_kinds"]
    assert await _version_count(factory) == 0


async def test_repair_rejects_unknown_resource_ids(factory):
    ids = await _seed(factory)

    result = await _repair(factory).repair_timetable(
        ids["timetable_id"],
        ids["user_id"],
        adjustments=[{"kind": "include_resources", "resource_ids": ["no-such-room"]}],
        approve_hard_relaxation=True,
        max_retries=1,
    )

    assert "error" in result
    assert await _version_count(factory) == 0


# ------------------------------------------------------------------ recovery


async def test_repair_lift_block_recovers_leave_infeasibility(factory):
    ids = await _seed(factory, lecture_hours=1, n_slots=1, n_days=1, with_leave=True)

    blocked = await _generate(factory, ids["timetable_id"])
    assert "INFEASIBLE" in blocked["error"], blocked

    result = await _repair(factory).repair_timetable(
        ids["timetable_id"],
        ids["user_id"],
        adjustments=[
            {
                "kind": "lift_availability_block",
                "faculty_slot_ids": [str(ids["faculty_id"])],
                "reason": "approved exception for one faculty day",
            }
        ],
        approve_hard_relaxation=True,
        max_retries=1,
    )

    assert result.get("success") is True, result
    assert result["validation_status"] == "PASS"
    assert result["entries_count"] == 1
    assert result["unscheduled"] == []
    assert result["repair_attempts"] == 1
    async with factory() as db:
        version = (await db.execute(select(TimetableVersion))).scalar_one()
        assert version.status == "VALIDATED"
        assert version.change_type == "REPAIR"
        assert version.version_number == 1
        repairs = (
            (await db.execute(select(AuditLog).where(AuditLog.action == "REPAIR"))).scalars().all()
        )
        assert len(repairs) == 1
        logged = repairs[0].new_values
        assert logged["solver_status"] == result["solver_status"]
        assert logged["repair_attempts"] == 1
        assert logged["applied_adjustment"]["kind"] == "lift_availability_block"
        assert logged["diff"]["added"] == 1


async def test_repair_include_resources_recovers_room_shortage(factory):
    ids = await _seed(factory, lecture_hours=0, n_slots=2, n_days=1, practical=True)
    # Only the active HARDWARE_LAB stays usable; deactivate nothing else, but
    # make the classroom unusable for labs by requiring HARDWARE_LAB (seeded).
    async with factory() as db:
        room = (await db.execute(select(Resource).where(Resource.name == "L1"))).scalar_one()
        room.is_active = False
        await db.commit()
        inactive_id = str(room.id)

    short = await _generate(factory, ids["timetable_id"])
    assert "error" in short, short  # parallel batches need 2 rooms at once

    result = await _repair(factory).repair_timetable(
        ids["timetable_id"],
        ids["user_id"],
        adjustments=[
            {
                "kind": "include_resources",
                "resource_ids": [inactive_id],
                "reason": "approved use of the second lab for this solve",
            }
        ],
        approve_hard_relaxation=True,
        max_retries=1,
    )

    assert result.get("success") is True, result
    assert result["entries_count"] == 2
    assert result["unscheduled"] == []


async def test_repair_preserves_unaffected_entries_and_versions(factory):
    ids = await _seed(factory, lecture_hours=2, n_slots=3, n_days=2)
    first = await _generate(factory, ids["timetable_id"])
    assert first.get("success") is True, first

    # A new satisfiable assignment: only it is unscheduled, so the pinned
    # scope must keep every previously placed entry.
    async with factory() as db:
        term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.academic_year == YEAR, AcademicTerm.semester == SEM
                )
            )
        ).scalar_one()
        section = (await db.execute(select(Section))).scalar_one()
        subject = (await db.execute(select(Subject))).scalar_one()
        extra_faculty = Faculty(employee_id="EX", first_name="E", last_name="X", email="ex@x.com")
        db.add(extra_faculty)
        await db.flush()
        db.add(
            TeachingAssignment(
                faculty_id=extra_faculty.id,
                academic_term_id=term.id,
                subject_id=subject.id,
                section_id=section.id,
                session_type="LECTURE",
                hours_per_week=1,
            )
        )
        await db.commit()

    result = await _repair(factory).repair_timetable(
        ids["timetable_id"],
        ids["user_id"],
        adjustments=[
            {"kind": "extend_time_limit", "time_limit_seconds": 20, "reason": "scoped re-solve"}
        ],
        max_retries=1,
    )

    assert result.get("success") is True, result
    assert result["version_number"] == 2
    assert result["diff"]["kept"] == first["entries_count"]
    async with factory() as db:
        v2 = (
            await db.execute(select(TimetableVersion).where(TimetableVersion.version_number == 2))
        ).scalar_one()
        assert str(v2.parent_version_id) == first["version_id"]
