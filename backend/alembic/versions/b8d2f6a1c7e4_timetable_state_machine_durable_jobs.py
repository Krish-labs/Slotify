"""Timetable state machine + durable jobs + validation metadata

- timetable_jobs: durable background-job records (Redis only transports work)
- timetable_entries.session_duration/section_strength/batch_strength: so
  approval-time validation is as strong as generation-time validation
- substitutions.timetable_id: substitution approval must target a specific
  timetable, never the globally-latest version

Revision ID: b8d2f6a1c7e4
Revises: 416228b43d2d
Create Date: 2026-10-06

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b8d2f6a1c7e4"
down_revision: str | Sequence[str] | None = "416228b43d2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timetable_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timetable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="QUEUED"),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("change_data", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["timetable_id"], ["timetables.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["parent_version_id"], ["timetable_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_job_idempotency_key"),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_job_status",
        ),
    )
    op.create_index("ix_timetable_jobs_timetable_id", "timetable_jobs", ["timetable_id"])
    op.create_index("idx_job_status", "timetable_jobs", ["status"])
    op.create_index("idx_job_timetable", "timetable_jobs", ["timetable_id", "created_at"])

    op.add_column(
        "timetable_entries",
        sa.Column("session_duration", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "timetable_entries", sa.Column("section_strength", sa.Integer(), nullable=True)
    )
    op.add_column(
        "timetable_entries", sa.Column("batch_strength", sa.Integer(), nullable=True)
    )

    op.add_column(
        "substitutions",
        sa.Column("timetable_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_substitutions_timetable_id", "substitutions", "timetables", ["timetable_id"], ["id"]
    )
    op.create_index("ix_substitutions_timetable_id", "substitutions", ["timetable_id"])


def downgrade() -> None:
    op.drop_index("ix_substitutions_timetable_id", table_name="substitutions")
    op.drop_constraint("fk_substitutions_timetable_id", "substitutions", type_="foreignkey")
    op.drop_column("substitutions", "timetable_id")

    op.drop_column("timetable_entries", "batch_strength")
    op.drop_column("timetable_entries", "section_strength")
    op.drop_column("timetable_entries", "session_duration")

    op.drop_index("idx_job_timetable", table_name="timetable_jobs")
    op.drop_index("idx_job_status", table_name="timetable_jobs")
    op.drop_index("ix_timetable_jobs_timetable_id", table_name="timetable_jobs")
    op.drop_table("timetable_jobs")
