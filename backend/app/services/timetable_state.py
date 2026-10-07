"""Authoritative state machine for timetables and timetable versions.

Single source of truth for every status transition. Routers and workers must
go through :func:`apply_version_transition` / :func:`apply_timetable_transition`
instead of assigning ``status`` directly, so guards, validation, audit and
notifications can never drift apart.

Lifecycles (derived from the requirements in docs/requirements/approval-workflow.md
and now actually enforced — before this module the post-VALIDATED transitions
existed only in memory and were rolled back):

TimetableVersion:
    VALIDATED -> UNDER_REVIEW -> APPROVED -> PUBLISHED -> ARCHIVED
        VALIDATED|UNDER_REVIEW|APPROVED -> REJECTED
Timetable (mirror):
    DRAFT -> VALIDATED -> UNDER_REVIEW -> APPROVED -> PUBLISHED -> ARCHIVED

Everything happens inside the caller's transaction (the use case commits once);
audit rows and notifications are written by this module into that same
transaction, so business mutation + audit + notification are atomic.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog
from app.database.models.timetable import Timetable
from app.database.models.timetable_version import TimetableVersion

VERSION_TRANSITIONS: dict[str, set[str]] = {
    "VALIDATED": {"UNDER_REVIEW", "APPROVED", "REJECTED", "ARCHIVED"},
    "UNDER_REVIEW": {"APPROVED", "REJECTED"},
    "APPROVED": {"PUBLISHED", "REJECTED"},
    "PUBLISHED": {"ARCHIVED"},
    "REJECTED": set(),
    "ARCHIVED": set(),
    "PENDING": set(),
    "FAILED": set(),
}

TIMETABLE_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"VALIDATED"},
    "VALIDATED": {"UNDER_REVIEW", "APPROVED", "REJECTED", "ARCHIVED"},
    "UNDER_REVIEW": {"APPROVED", "REJECTED"},
    "APPROVED": {"PUBLISHED"},
    "PUBLISHED": {"ARCHIVED"},
    "REJECTED": {"VALIDATED"},
    "ARCHIVED": set(),
}


class InvalidTransition(ValueError):
    """Raised when a state transition is not allowed."""


class PermissionRequired(PermissionError):
    """Raised when the caller's permissions do not allow the transition."""


def _now() -> datetime:
    return datetime.now(UTC)


async def _audit(
    db: AsyncSession,
    actor_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    old_values: dict | None,
    new_values: dict,
) -> None:
    db.add(
        AuditLog(
            user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
        )
    )


async def _notify(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    message: str,
    notif_type: str,
    reference_type: str,
    reference_id: UUID,
) -> None:
    from app.services.notification_service import NotificationService

    await NotificationService(db).send_notification(
        user_id=str(user_id),
        title=title,
        message=message,
        type=notif_type,
        reference_type=reference_type,
        reference_id=reference_id,
    )


def can_transition(current: str, target: str, timetable: bool = False) -> bool:
    transitions = TIMETABLE_TRANSITIONS if timetable else VERSION_TRANSITIONS
    return target in transitions.get(current, set())


async def apply_version_transition(
    db: AsyncSession,
    version: TimetableVersion,
    target: str,
    actor_id: UUID,
    *,
    require_validation: bool = False,
    validation_errors: list[str] | None = None,
) -> TimetableVersion:
    """Move a version to ``target`` inside the caller's transaction.

    - Guards the transition deterministically (409 for callers).
    - Optionally requires a non-empty validation result (approve/publish).
    - Writes the audit row and the actor notification into the same transaction.
    """
    previous = version.status
    if not can_transition(previous, target):
        raise InvalidTransition(
            f"Version {version.version_number} cannot move from {previous} to {target}"
        )
    if require_validation and validation_errors:
        raise InvalidTransition(
            f"Cannot move version {version.version_number} to {target}: "
            f"validation failed with {len(validation_errors)} error(s)"
        )

    version.status = target
    old = {"status": previous}
    new = {"status": target, "version_number": version.version_number}
    await _audit(db, actor_id, target, "TIMETABLE_VERSION", version.id, old, new)

    message = f"Timetable version {version.version_number} is now {target}."
    await _notify(
        db,
        actor_id,
        f"Version {target}",
        message,
        "SUCCESS" if target in ("APPROVED", "PUBLISHED") else "INFO",
        "TIMETABLE_VERSION",
        version.id,
    )
    return version


async def apply_timetable_transition(
    db: AsyncSession,
    timetable: Timetable,
    target: str,
    actor_id: UUID,
) -> Timetable:
    """Mirror the version transition onto the parent timetable (same transaction)."""
    previous = timetable.status
    if not can_transition(previous, target, timetable=True):
        raise InvalidTransition(
            f"Timetable {timetable.name} cannot move from {previous} to {target}"
        )
    timetable.status = target
    if target == "PUBLISHED":
        timetable.approved_by = actor_id
        timetable.approved_at = _now()
    await _audit(
        db,
        actor_id,
        target,
        "TIMETABLE",
        timetable.id,
        {"status": previous},
        {"status": target},
    )
    return timetable


_TIMETABLE_PROGRESS = {
    "DRAFT": 0,
    "VALIDATED": 1,
    "UNDER_REVIEW": 2,
    "APPROVED": 3,
    "PUBLISHED": 4,
    "ARCHIVED": 5,
    "REJECTED": 1,
}


async def mirror_timetable_status(
    db: AsyncSession,
    timetable: Timetable,
    target: str,
    actor_id: UUID,
) -> bool:
    """Best-effort mirror of a version transition onto the parent timetable.

    Rules:
    - apply the mirror when it is a valid transition;
    - skip silently (return False) when the timetable is already at or beyond
      the target state (e.g. approving a newer version after the timetable was
      already APPROVED from an older one) — the version transition itself is
      still authoritative and audited;
    - REJECTED versions never move the timetable (another VALIDATED version
      remains the live state).
    """
    if target == "REJECTED":
        return False
    current = timetable.status
    if current == target:
        return False
    if can_transition(current, target, timetable=True):
        await apply_timetable_transition(db, timetable, target, actor_id)
        return True
    if _TIMETABLE_PROGRESS.get(current, -1) >= _TIMETABLE_PROGRESS.get(target, -1):
        return False
    raise InvalidTransition(f"Timetable {timetable.name} cannot move from {current} to {target}")


async def latest_version_for_timetable(
    db: AsyncSession, timetable_id: UUID
) -> TimetableVersion | None:
    result = await db.execute(
        select(TimetableVersion)
        .where(TimetableVersion.timetable_id == timetable_id)
        .order_by(TimetableVersion.version_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
