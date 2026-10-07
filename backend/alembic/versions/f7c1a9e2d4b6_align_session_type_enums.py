"""Align session_type enum types with the ORM models.

Revision ID: f7c1a9e2d4b6
Revises: b8d2f6a1c7e4
Create Date: 2026-10-07

The phase-2 migration created a single Postgres enum ``sessiontype`` (labels
THEORY, PRACTICAL, TUTORIAL, PROJECT) and reused it for both
``faculty_loads.session_type`` and ``teaching_assignments.session_type``, while
the models declare ``faculty_load_session_type`` and ``teaching_session_type``.
On a schema built purely from alembic, any INSERT into either table therefore
failed with ``type "..." does not exist`` (SQLite, which the test suite uses,
never materialises the types, so the breakage was invisible there).

This migration creates the two model-declared types, retargets both columns,
and drops the shared artifact type when nothing references it. It is a no-op on
schemas where the types already exist (e.g. built via ``metadata.create_all``).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7c1a9e2d4b6"
down_revision: str | Sequence[str] | None = "b8d2f6a1c7e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FACULTY_LOAD_LABELS = "'THEORY', 'PRACTICAL', 'TUTORIAL', 'PROJECT'"
_TEACHING_LABELS = "'LECTURE', 'PRACTICAL', 'TUTORIAL', 'PROJECT'"


def _ensure_type(name: str, labels: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
                CREATE TYPE {name} AS ENUM ({labels});
            END IF;
        END
        $$;
        """
    )


def _retarget(table: str, type_name: str, value_expr: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = '{table}'
                  AND a.attname = 'session_type'
                  AND NOT a.attisdropped
                  AND a.atttypid <> '{type_name}'::regtype
            ) THEN
                ALTER TABLE {table}
                    ALTER COLUMN session_type TYPE {type_name}
                    USING ({value_expr}::{type_name});
            END IF;
        END
        $$;
        """
    )


def _drop_type_if_unused(name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}')
               AND NOT EXISTS (
                    SELECT 1
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    WHERE c.relname IN ('faculty_loads', 'teaching_assignments')
                      AND a.attname = 'session_type'
                      AND NOT a.attisdropped
                      AND a.atttypid = '{name}'::regtype
               ) THEN
                DROP TYPE {name};
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    """Create the model-declared enum types and retarget both columns."""
    _ensure_type("faculty_load_session_type", _FACULTY_LOAD_LABELS)
    _ensure_type("teaching_session_type", _TEACHING_LABELS)

    _retarget(
        "faculty_loads",
        "faculty_load_session_type",
        "session_type::text",
    )
    # THEORY never exists on teaching_assignments in practice; map it anyway so
    # the conversion cannot fail on a legacy row.
    _retarget(
        "teaching_assignments",
        "teaching_session_type",
        "CASE WHEN session_type::text = 'THEORY' THEN 'LECTURE' ELSE session_type::text END",
    )

    _drop_type_if_unused("sessiontype")


def downgrade() -> None:
    """Restore the shared ``sessiontype`` enum (LECTURE maps back to THEORY)."""
    _ensure_type("sessiontype", _FACULTY_LOAD_LABELS)

    _retarget("faculty_loads", "sessiontype", "session_type::text")
    _retarget(
        "teaching_assignments",
        "sessiontype",
        "CASE WHEN session_type::text = 'LECTURE' THEN 'THEORY' ELSE session_type::text END",
    )

    _drop_type_if_unused("faculty_load_session_type")
    _drop_type_if_unused("teaching_session_type")
