"""Align audit_logs column types with the ORM model.

Revision ID: c9d4e7a2b5f1
Revises: f7c1a9e2d4b6
Create Date: 2026-10-07

The phase-2 migration declared ``audit_logs.ip_address`` as ``INET`` and
``old_values``/``new_values`` as ``JSONB``, while ``AuditLog`` declares
``String(45)`` and ``JSON``. On a schema built purely from alembic every audit
write then failed on Postgres with

    column "ip_address" is of type inet but expression is of type character varying

which rolled back the surrounding transaction (audits are written in the same
transaction as their mutation, by design), so any audited API mutation 500'd.
SQLite never materialised the difference, so the test suite could not see it.

The JSON columns are converted for model/schema agreement: ``json -> jsonb``
assignment casts work either way at runtime, so this is a consistency fix, not
a behaviour change.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d4e7a2b5f1"
down_revision: str | Sequence[str] | None = "f7c1a9e2d4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _retarget(column: str, regtype: str, ddl_type: str, using: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'audit_logs'
                  AND a.attname = '{column}'
                  AND NOT a.attisdropped
                  AND a.atttypid <> '{regtype}'::regtype
            ) THEN
                ALTER TABLE audit_logs
                    ALTER COLUMN {column} TYPE {ddl_type}
                    USING ({using});
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    """Match the model: ip_address -> varchar(45), values -> json."""
    _retarget(
        "ip_address", "varchar", "character varying(45)", "NULLIF(ip_address::text, '')"
    )
    _retarget("old_values", "json", "json", "old_values::text::json")
    _retarget("new_values", "json", "json", "new_values::text::json")


def downgrade() -> None:
    """Restore the phase-2 declarations: ip_address -> inet, values -> jsonb."""
    _retarget(
        "ip_address", "inet", "inet", "NULLIF(ip_address::text, '')::inet"
    )
    _retarget("old_values", "jsonb", "jsonb", "old_values::text::jsonb")
    _retarget("new_values", "jsonb", "jsonb", "new_values::text::jsonb")
