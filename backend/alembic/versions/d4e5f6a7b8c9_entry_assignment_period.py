"""Add assignment_id and period_number to timetable_entries

The scheduler, validator, reoptimizer, and API serializers all key entries to
their teaching assignment (coverage, LOAD_CHANGE impact, pinned constraints)
and use the denormalized period_number (mirroring day_of_week). Persist both on
the entry so TimetableEntry stays the single source of truth.

Both columns are nullable so the upgrade is safe on populated databases;
new solver/worker writes always populate them.

Revision ID: d4e5f6a7b8c9
Revises: c4a9e2d7f1b3
Create Date: 2026-10-04 12:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c4a9e2d7f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "timetable_entries",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_timetable_entries_assignment_id",
        "timetable_entries",
        "teaching_assignments",
        ["assignment_id"],
        ["id"],
    )
    op.create_index(
        "ix_timetable_entries_assignment_id", "timetable_entries", ["assignment_id"]
    )
    op.add_column(
        "timetable_entries",
        sa.Column("period_number", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("timetable_entries", "period_number")
    op.drop_index("ix_timetable_entries_assignment_id", table_name="timetable_entries")
    op.drop_constraint(
        "fk_timetable_entries_assignment_id", "timetable_entries", type_="foreignkey"
    )
    op.drop_column("timetable_entries", "assignment_id")
