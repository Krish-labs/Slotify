"""Leave / substitution lifecycle: mass assignment, audit, and approval guards.

Before this coverage existed, a client could set ``status``/``approved_by``
directly on create, and an auto-created substitution could reach approval with
no ``timetable_id`` (guaranteed failure at apply time).
"""

from datetime import date, time
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AcademicTerm,
    AuditLog,
    Class,
    Faculty,
    Resource,
    Section,
    Subject,
    Substitution,
    TeachingAssignment,
    TimeSlot,
    Timetable,
    TimetableEntry,
    TimetableTemplate,
    TimetableVersion,
)
from app.database.models.leave import Leave
from app.database.models.teaching_assignment import SessionType
from app.database.models.user import User
from app.services.leave_service import LeaveService, SubstitutionService


async def _seed(db_session: AsyncSession) -> dict:
    template = TimetableTemplate(name="T", academic_year="2030-31")
    cls = Class(name="SE", year=2, branch="E&TC", academic_year="2030-31", strength=40)
    subject = Subject(code="EC1", name="Signals", subject_type="BOTH", semester=1)
    original = Faculty(
        employee_id="F-1",
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        department="E&TC",
        designation="Professor",
    )
    substitute = Faculty(
        employee_id="F-2",
        first_name="Alan",
        last_name="Turing",
        email="alan@example.com",
        department="E&TC",
        designation="Professor",
    )
    db_session.add_all([template, cls, subject, original, substitute])
    await db_session.flush()

    slot = TimeSlot(
        template_id=template.id,
        day_of_week=0,
        period_number=1,
        start_time=time(9, 0),
        end_time=time(9, 50),
        slot_type="TEACHING",
        shift="MORNING",
    )
    db_session.add(slot)
    await db_session.flush()

    section = Section(class_id=cls.id, name="A", strength=40)
    db_session.add(section)
    await db_session.flush()

    return {
        "template": template,
        "class": cls,
        "subject": subject,
        "slot": slot,
        "original": original,
        "substitute": substitute,
        "section": section,
    }


def _leave_payload(seed: dict, **extra) -> dict:
    payload = {
        "faculty_id": str(seed["original"].id),
        "leave_type": "SICK",
        "start_date": "2030-07-01",
        "end_date": "2030-07-02",
        "reason": "flu",
    }
    payload.update(extra)
    return payload


def _substitution_payload(seed: dict, **extra) -> dict:
    payload = {
        "original_faculty_id": str(seed["original"].id),
        "substitute_faculty_id": str(seed["substitute"].id),
        "subject_id": str(seed["subject"].id),
        "section_id": str(seed["section"].id),
        "batch_id": None,
        "date": "2030-07-01",
        "time_slot_id": str(seed["slot"].id),
        "status": "APPROVED",
    }
    payload.update(extra)
    return payload


@pytest.mark.asyncio
async def test_leave_create_ignores_client_supplied_lifecycle_fields(
    async_client: AsyncClient, db_session: AsyncSession
):
    seed = await _seed(db_session)
    response = await async_client.post(
        "/api/v1/leave/",
        json=_leave_payload(
            seed,
            status="APPROVED",
            approved_by="00000000-0000-0000-0000-000000000001",
            id="00000000-0000-0000-0000-000000000002",
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["approved_by"] is None


@pytest.mark.asyncio
async def test_leave_create_writes_audit_log(async_client: AsyncClient, db_session: AsyncSession):
    seed = await _seed(db_session)
    response = await async_client.post("/api/v1/leave/", json=_leave_payload(seed))
    assert response.status_code == 201, response.text

    leave_id = response.json()["id"]
    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "LEAVE",
                    AuditLog.entity_id == UUID(leave_id),
                    AuditLog.action == "CREATE",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "creating a leave must leave an audit trail"
    assert rows[0].new_values["status"] == "PENDING"


@pytest.mark.asyncio
async def test_leave_update_cannot_promote_itself(
    async_client: AsyncClient, db_session: AsyncSession
):
    seed = await _seed(db_session)
    created = await async_client.post("/api/v1/leave/", json=_leave_payload(seed))
    leave_id = created.json()["id"]

    response = await async_client.put(
        f"/api/v1/leave/{leave_id}",
        json={"reason": "still ill", "status": "APPROVED"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "PENDING"

    reloaded = await db_session.get(Leave, UUID(leave_id))
    assert reloaded.status == "PENDING", "status must only move through approve/reject/cancel"


@pytest.mark.asyncio
async def test_service_layer_whitelist_survives_bypassing_the_schema(
    db_session: AsyncSession,
):
    seed = await _seed(db_session)
    service = LeaveService(db_session)
    leave = await service.create(
        {
            "faculty_id": seed["original"].id,
            "leave_type": "CASUAL",
            "start_date": date(2030, 8, 1),
            "end_date": date(2030, 8, 2),
            "status": "APPROVED",
            "approved_by": seed["substitute"].id,
            "id": "00000000-0000-0000-0000-0000000000ff",
        }
    )
    await db_session.flush()
    assert leave.status == "PENDING"
    assert leave.approved_by is None


@pytest.mark.asyncio
async def test_substitution_cannot_be_created_without_a_resolvable_timetable(
    async_client: AsyncClient, db_session: AsyncSession
):
    """A substitution with no timetable is unusable: approval must not be reachable."""
    seed = await _seed(db_session)
    payload = {
        "original_faculty_id": str(seed["original"].id),
        "substitute_faculty_id": str(seed["substitute"].id),
        "subject_id": str(seed["subject"].id),
        "section_id": str(seed["section"].id),
        "batch_id": None,
        "date": "2030-07-01",
        "time_slot_id": str(seed["slot"].id),
        "status": "APPROVED",
    }
    response = await async_client.post("/api/v1/leave/substitutions/", json=payload)
    assert response.status_code == 400, response.text
    assert "timetable" in response.json()["detail"]


@pytest.mark.asyncio
async def test_substitution_rejects_a_section_belonging_to_another_class(
    async_client: AsyncClient, db_session: AsyncSession
):
    """class_id is request-only (class is implied by section), but it must be checked."""
    seed = await _seed(db_session)
    other_class = Class(name="TE", year=3, branch="E&TC", academic_year="2030-31", strength=30)
    db_session.add(other_class)
    await db_session.flush()

    mismatch = await async_client.post(
        "/api/v1/leave/substitutions/",
        json=_substitution_payload(seed, class_id=str(other_class.id)),
    )
    assert mismatch.status_code == 400, mismatch.text
    assert "does not belong to class" in mismatch.json()["detail"]


@pytest.mark.asyncio
async def test_substitution_passes_the_class_check_for_its_own_section(
    async_client: AsyncClient, db_session: AsyncSession
):
    """A matching class_id reaches the timetable gate instead of failing earlier.

    Kept separate from the mismatch case: that request rolls the shared test
    session back, which expires ``test_user`` and breaks a second request.
    """
    seed = await _seed(db_session)
    match = await async_client.post(
        "/api/v1/leave/substitutions/",
        json=_substitution_payload(seed, class_id=str(seed["class"].id)),
    )
    assert match.status_code == 400, match.text
    assert "timetable" in match.json()["detail"]


@pytest.mark.asyncio
async def test_substitution_status_cannot_be_spoofed_by_the_service_layer(
    db_session: AsyncSession,
):
    seed = await _seed(db_session)
    service = SubstitutionService(db_session)
    with pytest.raises(ValueError, match="timetable_id"):
        await service.create(
            {
                "original_faculty_id": seed["original"].id,
                "substitute_faculty_id": seed["substitute"].id,
                "subject_id": seed["subject"].id,
                "section_id": seed["section"].id,
                "date": date(2030, 7, 1),
                "time_slot_id": seed["slot"].id,
                "status": "APPROVED",
            }
        )


@pytest.mark.asyncio
async def test_approve_leave_creates_a_usable_substitution(
    async_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """Approval must produce a substitution that can actually be applied.

    Regression guards: the eligible-substitute lookup used a relationship that
    does not exist (AttributeError), the entry's faculty was lazily loaded in
    an async session, and auto-created substitutions carried no timetable_id
    (approval-time failure).
    """
    seed = await _seed(db_session)

    term = AcademicTerm(
        name="Sem I",
        academic_year="2030-31",
        semester=1,
        start_date=date(2030, 6, 1),
        end_date=date(2030, 12, 1),
    )
    resource = Resource(name="R-101", resource_type="CLASSROOM", capacity=60)
    db_session.add_all([term, resource])
    await db_session.flush()

    db_session.add(
        TeachingAssignment(
            faculty_id=seed["substitute"].id,
            academic_term_id=term.id,
            subject_id=seed["subject"].id,
            section_id=seed["section"].id,
            session_type=SessionType.LECTURE,
            hours_per_week=1,
            session_duration=1,
            is_active=True,
        )
    )
    timetable = Timetable(
        name="TT 2030-31",
        template_id=seed["template"].id,
        academic_year="2030-31",
        semester=1,
        status="GENERATED",
    )
    db_session.add(timetable)
    await db_session.flush()

    version = TimetableVersion(
        timetable_id=timetable.id,
        version_number=1,
        status="VALIDATED",
        created_by=test_user.id,
        change_type="FULL_REGENERATION",
    )
    db_session.add(version)
    await db_session.flush()

    db_session.add(
        TimetableEntry(
            version_id=version.id,
            faculty_id=seed["original"].id,
            subject_id=seed["subject"].id,
            section_id=seed["section"].id,
            resource_id=resource.id,
            time_slot_id=seed["slot"].id,
            day_of_week=date(2030, 7, 1).weekday(),
            period_number=1,
            session_type="LECTURE",
            session_duration=1,
        )
    )
    await db_session.flush()

    created = await async_client.post("/api/v1/leave/", json=_leave_payload(seed))
    assert created.status_code == 201, created.text
    leave_id = UUID(created.json()["id"])

    approved = await async_client.post(f"/api/v1/leave/{leave_id}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    subs = (
        (await db_session.execute(select(Substitution).where(Substitution.leave_id == leave_id)))
        .scalars()
        .all()
    )
    assert len(subs) == 1, "one affected entry must yield one substitution"
    assert subs[0].timetable_id == timetable.id, "approval must target a known timetable"
    assert subs[0].substitute_faculty_id == seed["substitute"].id
    assert subs[0].status == "PENDING"

    audit = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "LEAVE",
                    AuditLog.entity_id == leave_id,
                    AuditLog.action == "APPROVE",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) == 1, "approval must be audited"


@pytest.mark.asyncio
async def test_an_approved_leave_cannot_be_edited_out_of_band(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Once decided, the record is frozen: history only moves via audit."""
    seed = await _seed(db_session)
    created = await async_client.post("/api/v1/leave/", json=_leave_payload(seed))
    assert created.status_code == 201, created.text
    leave_id = created.json()["id"]

    approved = await async_client.post(f"/api/v1/leave/{leave_id}/approve")
    assert approved.status_code == 200, approved.text

    edited = await async_client.put(f"/api/v1/leave/{leave_id}", json={"reason": "retconned"})
    assert edited.status_code == 400, edited.text
    assert "Cannot edit leave" in edited.json()["detail"]
