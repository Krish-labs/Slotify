"""Model ↔ migration alignment guards.

A schema built only from ``alembic upgrade head`` must declare every type the
ORM models bind to. SQLite (what the suite runs on) never materialises Postgres
enum/inet types, so a mismatch there is invisible until a real Postgres install
is attempted - which is how ``teaching_assignments.session_type`` and
``audit_logs.ip_address`` reached a state where every write failed on Postgres.
"""

from pathlib import Path

from sqlalchemy import Enum as SQLEnum

import app.database.models  # noqa: F401  (registers every model on Base.metadata)
from app.database.base import Base

VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _model_enum_type_names() -> set[str]:
    names: set[str] = set()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, SQLEnum) and column.type.name:
                names.add(column.type.name)
    return names


def test_every_model_enum_type_is_created_by_a_migration() -> None:
    blob = "\n".join(path.read_text() for path in VERSIONS_DIR.glob("*.py"))
    declared = _model_enum_type_names()
    assert declared, "expected at least one model enum column"
    missing = sorted(name for name in declared if name not in blob)
    assert not missing, (
        "model enum type(s) never mentioned by any migration - a fresh "
        f"`alembic upgrade head` will not create them: {missing}"
    )
