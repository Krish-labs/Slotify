"""Rehydrate the exact information the TimetableValidator needs for a
*persisted* version, so approval/publish-time validation can never become
weaker than generation-time validation.

Generation validates entries that carry ``session_duration``,
``section_strength``/``batch_strength`` and ``resource_capacity``, against
``required_hours`` for every assignment. This module rebuilds the same inputs
from the database:

- per-entry ``session_duration`` / strengths are persisted columns on
  ``TimetableEntry`` (see migration b8d2f6a1c7e4);
- ``resource_capacity`` is joined from ``resources``;
- ``required_hours`` is read from the *current* teaching assignments.

If an assignment referenced by an entry no longer exists, it is pinned at 0
required hours so the coverage check fails loudly instead of silently passing.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.resource import Resource
from app.database.models.teaching_assignment import TeachingAssignment
from app.database.models.timetable_entry import TimetableEntry


async def build_version_validation_context(
    db: AsyncSession, version_id: UUID
) -> tuple[list[dict], dict[str, int]]:
    """Return ``(entries_dict, required_hours)`` for :class:`TimetableValidator`."""
    entries = (
        (await db.execute(select(TimetableEntry).where(TimetableEntry.version_id == version_id)))
        .scalars()
        .all()
    )

    resource_ids = {e.resource_id for e in entries}
    capacities: dict[UUID, int] = {}
    if resource_ids:
        rows = (
            (await db.execute(select(Resource).where(Resource.id.in_(resource_ids))))
            .scalars()
            .all()
        )
        capacities = {r.id: (r.capacity or 0) for r in rows}

    assignment_ids = {e.assignment_id for e in entries if e.assignment_id}
    required: dict[str, int] = {}
    if assignment_ids:
        hours_rows = (
            await db.execute(
                select(TeachingAssignment.id, TeachingAssignment.hours_per_week).where(
                    TeachingAssignment.id.in_(assignment_ids)
                )
            )
        ).all()
        required = {str(aid): hours for aid, hours in hours_rows}
        # An entry whose assignment disappeared must fail coverage, never pass.
        for aid in assignment_ids:
            required.setdefault(str(aid), 0)

    entries_dict = []
    for e in entries:
        entries_dict.append(
            {
                "id": e.id,
                "assignment_id": str(e.assignment_id) if e.assignment_id else None,
                "faculty_id": str(e.faculty_id) if e.faculty_id else None,
                "subject_id": str(e.subject_id) if e.subject_id else None,
                "section_id": str(e.section_id) if e.section_id else None,
                "batch_id": str(e.batch_id) if e.batch_id else None,
                "resource_id": str(e.resource_id) if e.resource_id else None,
                "time_slot_id": str(e.time_slot_id) if e.time_slot_id else None,
                "day_of_week": e.day_of_week,
                "period_number": e.period_number,
                "session_type": e.session_type,
                "session_duration": e.session_duration or 1,
                "section_strength": e.section_strength,
                "batch_strength": e.batch_strength,
                "resource_capacity": capacities.get(e.resource_id),
            }
        )

    return entries_dict, required


def validate_version_entries(entries_dict: list[dict], required_hours: dict[str, int]):
    """Run the independent validator over a persisted version."""
    from app.validators.timetable_validator import TimetableValidator

    return TimetableValidator().validate(entries_dict, required_hours=required_hours or None)


def coverage_by_assignment(entries_dict: list[dict]) -> dict[str, int]:
    counts: defaultdict[str, int] = defaultdict(int)
    for e in entries_dict:
        if e.get("assignment_id"):
            counts[e["assignment_id"]] += 1
    return dict(counts)
