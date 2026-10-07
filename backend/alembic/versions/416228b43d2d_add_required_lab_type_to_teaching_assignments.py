"""Add required_lab_type to teaching_assignments

Revision ID: 416228b43d2d
Revises: d4e5f6a7b8c9
Create Date: 2026-10-06

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '416228b43d2d'
down_revision: str | Sequence[str] | None = 'd4e5f6a7b8c9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'teaching_assignments',
        sa.Column('required_lab_type', sa.String(length=30), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('teaching_assignments', 'required_lab_type')
