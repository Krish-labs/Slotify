from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.audit_log import AuditLog
from app.database.models.faculty_load import FacultyLoad
from app.database.models.faculty_load import ResourceType as FacultyLoadResourceType
from app.database.models.faculty_load import SessionType as FacultyLoadSessionType
from app.database.models.teaching_assignment import (
    SessionType as TeachingAssignmentSessionType,
)
from app.database.models.teaching_assignment import (
    TeachingAssignment,
)


class AssignmentDerivationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _map_resource_type(load_resource_type: FacultyLoadResourceType) -> str | None:
        """Map FacultyLoad ResourceType to required_lab_type string."""
        # Map by enum value to avoid attribute access issues at module load time
        mapping = {
            "CLASSROOM": None,
            "LAB": "HARDWARE_LAB",
            "COMPUTER_LAB": "SOFTWARE_LAB",
            "SEMINAR_HALL": None,
            "WORKSHOP": "HARDWARE_LAB",
            "NONE": None,
        }
        return mapping.get(load_resource_type.value)

    async def derive_assignments(
        self, academic_term_id: UUID, user_id: UUID, force: bool = False
    ) -> dict:
        """Derive TeachingAssignment records from approved FacultyLoad records"""

        # Get approved loads for the academic term
        query = (
            select(FacultyLoad)
            .options(
                selectinload(FacultyLoad.faculty),
                selectinload(FacultyLoad.subject),
                selectinload(FacultyLoad.class_),
                selectinload(FacultyLoad.section),
                selectinload(FacultyLoad.batch),
            )
            .where(
                FacultyLoad.academic_term_id == academic_term_id,
                FacultyLoad.is_approved == True,
                FacultyLoad.is_active == True,
            )
        )

        result = await self.db.execute(query)
        loads = result.scalars().all()

        if not loads:
            return {
                "derived": 0,
                "skipped": 0,
                "errors": ["No approved loads found for this academic term"],
            }

        derived_count = 0
        skipped_count = 0
        errors = []

        for load in loads:
            try:
                # Check if assignment already exists
                existing = await self._check_existing_assignment(load)
                if existing and not force:
                    skipped_count += 1
                    continue

                # Derive assignments from load
                assignments_created = await self._derive_from_load(load, user_id)
                derived_count += assignments_created

            except Exception as e:
                errors.append(f"Load {load.id}: {str(e)}")
        return {
            "derived": derived_count,
            "skipped": skipped_count,
            "errors": errors,
        }

    async def _check_existing_assignment(self, load: FacultyLoad) -> TeachingAssignment | None:
        target_session_type = self._map_session_type(load.session_type)  # type: ignore[arg-type]
        expected_batch_id = (
            None if target_session_type == TeachingAssignmentSessionType.LECTURE else load.batch_id
        )

        query = select(TeachingAssignment).where(
            TeachingAssignment.faculty_id == load.faculty_id,
            TeachingAssignment.academic_term_id == load.academic_term_id,
            TeachingAssignment.subject_id == load.subject_id,
            TeachingAssignment.section_id == load.section_id,
            TeachingAssignment.session_type == target_session_type,
        )
        if expected_batch_id is None:
            query = query.where(TeachingAssignment.batch_id.is_(None))
        else:
            query = query.where(TeachingAssignment.batch_id == expected_batch_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _derive_from_load(self, load: FacultyLoad, user_id: UUID) -> int:
        """Create TeachingAssignment records from a FacultyLoad"""

        assignments_created = 0

        # Validate before adding anything, so a bad load never leaves a partial derivation.
        if load.practical_hours > 0:
            if not load.batch_id:
                # Cannot create practical without batch - flag as ambiguous
                raise ValueError(
                    f"Load {load.id} has practical hours ({load.practical_hours}) "
                    "but no batch assigned. Practical sessions require batch-level assignment."
                )
            duration = load.session_duration or 1
            if load.practical_hours % duration != 0:
                raise ValueError(
                    f"Load {load.id} has {load.practical_hours} practical hours that cannot be "
                    f"split into sessions of {duration} consecutive periods."
                )

        # Map required resource type for practical sessions
        required_lab_type = self._map_resource_type(load.required_resource_type)  # type: ignore[arg-type]

        # Create assignments based on session types and hours
        if load.theory_hours > 0:
            assignment = TeachingAssignment(
                faculty_id=load.faculty_id,
                academic_term_id=load.academic_term_id,
                subject_id=load.subject_id,
                section_id=load.section_id,
                batch_id=None,  # Theory is typically section-level
                session_type=TeachingAssignmentSessionType.LECTURE,
                hours_per_week=load.theory_hours,
                required_lab_type=None,
                preferred_days=[],
                preferred_shifts=[],
            )
            self.db.add(assignment)
            assignments_created += 1

        if load.practical_hours > 0:
            assignment = TeachingAssignment(
                faculty_id=load.faculty_id,
                academic_term_id=load.academic_term_id,
                subject_id=load.subject_id,
                section_id=load.section_id,
                batch_id=load.batch_id,
                session_type=TeachingAssignmentSessionType.PRACTICAL,
                hours_per_week=load.practical_hours,
                # session_duration applies to practicals (multi-period lab blocks);
                # lectures, tutorials and projects are single-period sessions.
                session_duration=load.session_duration or 1,
                required_lab_type=required_lab_type,
                preferred_days=[],
                preferred_shifts=[],
            )
            self.db.add(assignment)
            assignments_created += 1

        if load.tutorial_hours > 0:
            assignment = TeachingAssignment(
                faculty_id=load.faculty_id,
                academic_term_id=load.academic_term_id,
                subject_id=load.subject_id,
                section_id=load.section_id,
                batch_id=load.batch_id,  # Tutorials can be batch or section level
                session_type=TeachingAssignmentSessionType.TUTORIAL,
                hours_per_week=load.tutorial_hours,
                required_lab_type=None,
                preferred_days=[],
                preferred_shifts=[],
            )
            self.db.add(assignment)
            assignments_created += 1

        if load.project_hours > 0:
            assignment = TeachingAssignment(
                faculty_id=load.faculty_id,
                academic_term_id=load.academic_term_id,
                subject_id=load.subject_id,
                section_id=load.section_id,
                batch_id=load.batch_id,
                session_type=TeachingAssignmentSessionType.PROJECT,
                hours_per_week=load.project_hours,
                required_lab_type=None,
                preferred_days=[],
                preferred_shifts=[],
            )
            self.db.add(assignment)
            assignments_created += 1

        if assignments_created > 0:
            # Audit log
            audit = AuditLog(
                user_id=user_id,
                action="DERIVE",
                entity_type="TEACHING_ASSIGNMENT",
                entity_id=load.id,
                new_values={
                    "source_load_id": str(load.id),
                    "assignments_created": assignments_created,
                    "theory_hours": load.theory_hours,
                    "practical_hours": load.practical_hours,
                    "tutorial_hours": load.tutorial_hours,
                    "project_hours": load.project_hours,
                },
            )
            self.db.add(audit)

        return assignments_created

    def _map_session_type(
        self, load_session_type: FacultyLoadSessionType
    ) -> TeachingAssignmentSessionType:
        """Map FacultyLoad session type to TeachingAssignment session type"""
        mapping = {
            FacultyLoadSessionType.THEORY: TeachingAssignmentSessionType.LECTURE,
            FacultyLoadSessionType.PRACTICAL: TeachingAssignmentSessionType.PRACTICAL,
            FacultyLoadSessionType.TUTORIAL: TeachingAssignmentSessionType.TUTORIAL,
            FacultyLoadSessionType.PROJECT: TeachingAssignmentSessionType.PROJECT,
        }
        return mapping.get(load_session_type, TeachingAssignmentSessionType.LECTURE)

    async def get_derivation_preview(self, academic_term_id: UUID) -> dict:
        """Preview what assignments would be derived without creating them"""

        query = (
            select(FacultyLoad)
            .options(
                selectinload(FacultyLoad.faculty),
                selectinload(FacultyLoad.subject),
                selectinload(FacultyLoad.class_),
                selectinload(FacultyLoad.section),
                selectinload(FacultyLoad.batch),
            )
            .where(
                FacultyLoad.academic_term_id == academic_term_id,
                FacultyLoad.is_approved == True,
                FacultyLoad.is_active == True,
            )
        )

        result = await self.db.execute(query)
        loads = result.scalars().all()

        preview = []
        for load in loads:
            existing = await self._check_existing_assignment(load)

            assignments_to_create = []
            if load.theory_hours > 0:
                assignments_to_create.append(
                    {
                        "session_type": TeachingAssignmentSessionType.LECTURE.value,
                        "hours_per_week": load.theory_hours,
                        "batch_id": None,
                    }
                )
            if load.practical_hours > 0:
                assignments_to_create.append(
                    {
                        "session_type": TeachingAssignmentSessionType.PRACTICAL.value,
                        "hours_per_week": load.practical_hours,
                        "session_duration": load.session_duration or 1,  # type: ignore[dict-item]
                        "batch_id": str(load.batch_id) if load.batch_id else None,
                        "requires_batch": True,  # type: ignore[dict-item]
                    }  # type: ignore[dict-item]
                )
            if load.tutorial_hours > 0:
                assignments_to_create.append(
                    {
                        "session_type": TeachingAssignmentSessionType.TUTORIAL.value,
                        "hours_per_week": load.tutorial_hours,
                        "batch_id": str(load.batch_id) if load.batch_id else None,
                    }  # type: ignore[dict-item]
                )
            if load.project_hours > 0:
                assignments_to_create.append(
                    {
                        "session_type": TeachingAssignmentSessionType.PROJECT.value,
                        "hours_per_week": load.project_hours,
                        "batch_id": str(load.batch_id) if load.batch_id else None,
                    }  # type: ignore[dict-item]
                )

            has_ambiguity = any(
                a.get("requires_batch")
                and (
                    not a["batch_id"]
                    or (
                        a["session_duration"]
                        and isinstance(a["hours_per_week"], int)
                        and isinstance(a["session_duration"], int)
                        and a["hours_per_week"] % a["session_duration"] != 0
                    )
                )
                for a in assignments_to_create
            )

            preview.append(
                {
                    "load_id": str(load.id),
                    "faculty": (
                        f"{load.faculty.first_name} {load.faculty.last_name}"
                        if load.faculty
                        else "Unknown"
                    ),
                    "subject": load.subject.code if load.subject else "Unknown",
                    "class_section": (
                        f"{load.class_.name}-{load.section.name}"
                        if (hasattr(load, "class_") and load.class_ and load.section)
                        else (load.section.name if load.section else "Unknown")
                    ),
                    "batch": load.batch.name if load.batch else None,
                    "assignments_to_create": assignments_to_create,
                    "already_exists": existing is not None,
                    "has_ambiguity": has_ambiguity,
                }
            )

        return {
            "academic_term_id": str(academic_term_id),
            "total_loads": len(loads),
            "preview": preview,
        }
