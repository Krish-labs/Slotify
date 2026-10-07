"""Add session_duration to teaching_assignments

Carries FacultyLoad.session_duration (consecutive periods per session) through to the
scheduler. Existing rows default to 1, i.e. unchanged behaviour.

Revision ID: c4a9e2d7f1b3
Revises: b7d41c0a95e2
Create Date: 2026-10-03 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4a9e2d7f1b3"
down_revision: str | Sequence[str] | None = "b7d41c0a95e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "teaching_assignments",
        sa.Column("session_duration", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "ck_assignment_duration_positive", "teaching_assignments", "session_duration >= 1"
    )
    op.create_check_constraint(
        "ck_assignment_duration_divides_hours",
        "teaching_assignments",
        "hours_per_week % session_duration = 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_assignment_duration_divides_hours", "teaching_assignments", type_="check")
    op.drop_constraint("ck_assignment_duration_positive", "teaching_assignments", type_="check")
    op.drop_column("teaching_assignments", "session_duration")
