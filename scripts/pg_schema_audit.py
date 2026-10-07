"""Compare every ORM column type and nullability against the live Postgres schema.

Read-only. Reports columns where the model's compiled type, nullability or
column set differs from the live schema, plus model tables missing from (or
extra in) the database.

Usage:
    DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db PYTHONPATH=backend \
        backend/.venv/bin/python scripts/pg_schema_audit.py

Exit codes: 0 = model and schema agree, 1 = mismatches found, 2 = misconfigured.
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

url = os.environ.get("DATABASE_URL")
if not url or not url.startswith("postgresql"):
    print("DATABASE_URL must be set to a postgresql+asyncpg:// URL", file=sys.stderr)
    raise SystemExit(2)

import asyncpg
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateColumn

import app.database.models  # noqa: F401  (registers every model on Base.metadata)
from app.database.base import Base

DIALECT = postgresql.dialect()


def expected_udt(column) -> str:
    ddl = str(CreateColumn(column).compile(dialect=DIALECT))
    # "col TYPE ..." -> take everything after the column name
    after_name = ddl.split(column.name, 1)[1].strip()
    after_name = after_name.split(" DEFAULT")[0].split(" NOT NULL")[0].split(" PRIMARY KEY")[0]
    after_name = after_name.strip().rstrip(",")
    # unwrap parentheses-free simple forms
    base = after_name.split("(")[0].strip().lower()
    mapping = {
        "character varying": "varchar",
        "character": "bpchar",
        "timestamp with time zone": "timestamptz",
        "timestamp without time zone": "timestamp",
        "double precision": "float8",
        "integer": "int4",
        "bigint": "int8",
        "smallint": "int2",
        "boolean": "bool",
        "json": "json",
        "jsonb": "jsonb",
        "uuid": "uuid",
        "date": "date",
        "numeric": "numeric",
        "inet": "inet",
        "text": "text",
        "time without time zone": "time",
    }
    return mapping.get(base, base)


async def main() -> int:
    sync_url = url.replace("+asyncpg", "")
    conn = await asyncpg.connect(sync_url)
    try:
        rows = await conn.fetch(
            """
            SELECT table_name, column_name, udt_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """
        )
    finally:
        await conn.close()

    live = {
        (r["table_name"], r["column_name"]): (r["udt_name"], r["data_type"], r["is_nullable"])
        for r in rows
    }

    model_tables = {t.name for t in Base.metadata.sorted_tables}
    if not model_tables & {t for t, _ in live}:
        print(
            "no model tables found in the target database - build the schema "
            "first (`alembic upgrade head`, or `make verify-pg`, which does it "
            "for you) and re-run",
            file=sys.stderr,
        )
        return 2

    problems: list[str] = []
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            key = (table.name, col.name)
            if key not in live:
                problems.append(f"MISSING COLUMN {table.name}.{col.name}")
                continue
            udt, data_type, is_nullable = live[key]
            exp = expected_udt(col)
            if udt != exp:
                problems.append(
                    f"TYPE MISMATCH {table.name}.{col.name}: model={exp} db={udt} ({data_type})"
                )
            db_nullable = is_nullable == "YES"
            if db_nullable != bool(col.nullable):
                problems.append(
                    f"NULLABILITY MISMATCH {table.name}.{col.name}: "
                    f"model={bool(col.nullable)} db={db_nullable}"
                )
        live_cols = {c for (t, c) in live if t == table.name}
        for extra in sorted(live_cols - {c.name for c in table.columns}):
            problems.append(f"EXTRA COLUMN {table.name}.{extra} (in DB, not in model)")

    live_tables = {t for t, _ in live} - {"alembic_version"}  # alembic's own table
    for name in sorted(model_tables - live_tables):
        problems.append(f"MISSING TABLE {name}")
    for name in sorted(live_tables - model_tables):
        problems.append(f"EXTRA TABLE {name} (in DB, not in model)")

    checked_cols = sum(len(t.columns) for t in Base.metadata.sorted_tables)
    print(f"checked {len(model_tables)} model tables / {checked_cols} columns against live PG schema")
    if problems:
        print(f"--- {len(problems)} PROBLEM(S) ---")
        for p in problems:
            print(p)
    else:
        print("no schema/model type or nullability mismatches")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
