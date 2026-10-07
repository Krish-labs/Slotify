"""Restrict section/slot uniqueness on timetable_entries to lectures

Parallel batch practicals of one section share (version, section, slot), which the
old unconditional unique constraint rejected.

Revision ID: b7d41c0a95e2
Revises: e862e2d16796
Create Date: 2026-10-03 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7d41c0a95e2"
down_revision: str | Sequence[str] | None = "e862e2d16796"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_entry_section_slot", "timetable_entries", type_="unique")
    op.create_index(
        "uq_entry_section_lecture_slot",
        "timetable_entries",
        ["version_id", "section_id", "time_slot_id"],
        unique=True,
        postgresql_where=sa.text("session_type = 'LECTURE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_entry_section_lecture_slot", table_name="timetable_entries")
    op.create_unique_constraint(
        "uq_entry_section_slot",
        "timetable_entries",
        ["version_id", "section_id", "time_slot_id"],
    )
