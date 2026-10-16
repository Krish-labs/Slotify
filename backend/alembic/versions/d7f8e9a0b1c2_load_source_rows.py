"""Store editable source load-distribution rows."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7f8e9a0b1c2"
down_revision: str | Sequence[str] | None = "c9d4e7a2b5f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "load_distribution_source_rows",
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column("source_sheet", sa.String(length=100), nullable=False),
        sa.Column("source_semester", sa.String(length=50), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("serial_number", sa.String(length=30), nullable=True),
        sa.Column("faculty_name", sa.String(length=255), nullable=True),
        sa.Column("designation", sa.String(length=255), nullable=True),
        sa.Column("class_name", sa.String(length=255), nullable=True),
        sa.Column("subject_name", sa.String(length=255), nullable=True),
        sa.Column("theory", sa.String(length=30), nullable=True),
        sa.Column("practical", sa.String(length=30), nullable=True),
        sa.Column("tutorial", sa.String(length=30), nullable=True),
        sa.Column("project_stage", sa.String(length=30), nullable=True),
        sa.Column("total_load", sa.String(length=30), nullable=True),
        sa.Column("sign", sa.String(length=255), nullable=True),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_file",
            "source_sheet",
            "source_row_number",
            name="uq_load_source_row_location",
        ),
    )


def downgrade() -> None:
    op.drop_table("load_distribution_source_rows")
