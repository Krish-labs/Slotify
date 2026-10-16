"""Timetable templates and their teaching time slots.

Time slots are a mandatory CP-SAT solver input (TimetableWorker selects active
TEACHING slots for the timetable's template), so this API must be real: without
it there is no way to configure the period grid a timetable is generated into.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.permissions import MANAGEMENT_ROLES
from app.database.models.time_slot import TimeSlot
from app.database.models.timetable_template import TimetableTemplate
from app.database.transactions import transaction
from app.schemas.timetable import (
    TemplateCreate,
    TemplateResponse,
    TimeSlotBulkCreate,
    TimeSlotCreate,
    TimeSlotResponse,
)

router = APIRouter(prefix="/templates", tags=["templates"])


async def _get_template_or_404(db: AsyncSession, template_id: UUID) -> TimetableTemplate:
    template = await db.get(TimetableTemplate, template_id)
    if not template or not template.is_active:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    templates = (
        (await db.execute(select(TimetableTemplate).where(TimetableTemplate.is_active.is_(True))))
        .scalars()
        .all()
    )
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    async with transaction(db):
        template = TimetableTemplate(
            name=data.name,
            description=data.description,
            academic_year=data.academic_year,
            is_default=data.is_default,
            is_active=True,
        )
        db.add(template)
        await db.flush()
    return TemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    template = await _get_template_or_404(db, template_id)
    return TemplateResponse.model_validate(template)


@router.get("/{template_id}/time-slots", response_model=list[TimeSlotResponse])
async def list_time_slots(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await _get_template_or_404(db, template_id)
    slots = (
        (
            await db.execute(
                select(TimeSlot)
                .where(TimeSlot.template_id == template_id)
                .order_by(TimeSlot.day_of_week, TimeSlot.period_number)
            )
        )
        .scalars()
        .all()
    )
    return [TimeSlotResponse.model_validate(s) for s in slots]


@router.post(
    "/{template_id}/time-slots",
    response_model=list[TimeSlotResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_time_slots(
    template_id: UUID,
    slots: list[TimeSlotCreate],
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    """Create teaching time slots for a template (user-provided period grid)."""
    await _get_template_or_404(db, template_id)
    created: list[TimeSlot] = []
    async with transaction(db):
        for slot in slots:
            if not 0 <= slot.day_of_week <= 5:
                raise HTTPException(
                    status_code=422,
                    detail=f"day_of_week must be 0-5 (Mon-Sat), got {slot.day_of_week}",
                )
            if slot.start_time >= slot.end_time:
                raise HTTPException(
                    status_code=422,
                    detail=f"Period {slot.period_number}: start_time must be before end_time",
                )
            exists = (
                await db.execute(
                    select(TimeSlot).where(
                        TimeSlot.template_id == template_id,
                        TimeSlot.day_of_week == slot.day_of_week,
                        TimeSlot.period_number == slot.period_number,
                    )
                )
            ).scalar_one_or_none()
            if exists:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Slot day {slot.day_of_week} period {slot.period_number} already "
                        "exists for this template"
                    ),
                )
            row = TimeSlot(
                template_id=template_id,
                day_of_week=slot.day_of_week,
                period_number=slot.period_number,
                start_time=slot.start_time,
                end_time=slot.end_time,
                slot_type=slot.slot_type,
                shift=slot.shift,
                is_active=True,
            )
            db.add(row)
            created.append(row)
        await db.flush()
    return [TimeSlotResponse.model_validate(s) for s in created]


@router.post(
    "/{template_id}/time-slots/bulk",
    response_model=list[TimeSlotResponse],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_create_time_slots(
    template_id: UUID,
    data: TimeSlotBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    """Create the same period grid on every selected day (no dummy data: the
    times come from the caller's real institutional period schedule)."""
    await _get_template_or_404(db, template_id)
    if not data.days:
        raise HTTPException(status_code=422, detail="At least one day is required")
    if not data.periods:
        raise HTTPException(status_code=422, detail="At least one period is required")

    payloads = [
        TimeSlotCreate(
            day_of_week=day,
            period_number=p.period_number,
            start_time=p.start_time,
            end_time=p.end_time,
            slot_type=p.slot_type,
            shift=p.shift,
        )
        for day in data.days
        for p in data.periods
    ]
    return await create_time_slots(template_id, payloads, db=db, current_user=current_user)


@router.delete("/{template_id}/time-slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_time_slot(
    template_id: UUID,
    slot_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    async with transaction(db):
        slot = await db.get(TimeSlot, slot_id)
        if not slot or slot.template_id != template_id:
            raise HTTPException(status_code=404, detail="Time slot not found")
        slot.is_active = False
