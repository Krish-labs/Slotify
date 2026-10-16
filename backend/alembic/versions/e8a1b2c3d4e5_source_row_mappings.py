"""Add authoritative mapping and approval state to source load rows."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "d7f8e9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("load_distribution_source_rows", sa.Column("faculty_id", sa.UUID(), nullable=True))
    op.add_column("load_distribution_source_rows", sa.Column("subject_id", sa.UUID(), nullable=True))
    op.add_column("load_distribution_source_rows", sa.Column("class_id", sa.UUID(), nullable=True))
    op.add_column("load_distribution_source_rows", sa.Column("section_id", sa.UUID(), nullable=True))
    op.add_column("load_distribution_source_rows", sa.Column("batch_id", sa.UUID(), nullable=True))
    op.add_column("load_distribution_source_rows", sa.Column("academic_term_id", sa.UUID(), nullable=True))
    op.add_column(
        "load_distribution_source_rows",
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("load_distribution_source_rows", sa.Column("approved_by", sa.UUID(), nullable=True))
    op.add_column(
        "load_distribution_source_rows",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("load_distribution_source_rows", sa.Column("faculty_load_id", sa.UUID(), nullable=True))
    for column, target in (
        ("faculty_id", "faculty.id"),
        ("subject_id", "subjects.id"),
        ("class_id", "classes.id"),
        ("section_id", "sections.id"),
        ("batch_id", "batches.id"),
        ("academic_term_id", "academic_terms.id"),
        ("approved_by", "users.id"),
        ("faculty_load_id", "faculty_loads.id"),
    ):
        op.create_foreign_key(
            f"fk_load_source_{column}",
            "load_distribution_source_rows",
            target.split(".")[0],
            [column],
            [target.split(".")[1]],
        )
    op.create_unique_constraint(
        "uq_load_source_faculty_load_id", "load_distribution_source_rows", ["faculty_load_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_load_source_faculty_load_id", "load_distribution_source_rows", type_="unique")
    for column in (
        "faculty_load_id",
        "approved_at",
        "approved_by",
        "is_approved",
        "academic_term_id",
        "batch_id",
        "section_id",
        "class_id",
        "subject_id",
        "faculty_id",
    ):
        op.drop_column("load_distribution_source_rows", column)
