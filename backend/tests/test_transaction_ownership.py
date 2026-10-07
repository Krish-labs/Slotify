"""Rule 15: prove mutations are actually committed.

The shared API fixture hands the client and the assertions one session, so an
uncommitted row looks persisted there. Everything below deliberately uses two
independent sessions (two connections to one file) so "flushed into an open
transaction" and "committed" cannot be confused.
"""

from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies import get_current_user, get_db
from app.database.connection import Base
from app.database.models.academic_term import AcademicTerm
from app.database.models.user import User
from app.database.transactions import transaction
from app.main import app


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    """Two calls yield two sessions with two real connections."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/persist.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _term(**overrides) -> AcademicTerm:
    values = {
        "name": "2030-31 Sem I",
        "academic_year": "2030-31",
        "semester": 1,
        "start_date": date(2030, 6, 1),
        "end_date": date(2030, 10, 31),
        "is_active": True,
        "is_current": False,
    }
    values.update(overrides)
    return AcademicTerm(**values)


@pytest.mark.asyncio
async def test_transaction_commits_for_a_second_session(session_factory):
    async with session_factory() as writer, transaction(writer):
        writer.add(_term(academic_year="commit-me"))

    async with session_factory() as reader:
        rows = (
            (
                await reader.execute(
                    select(AcademicTerm).where(AcademicTerm.academic_year == "commit-me")
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1, "transaction() must commit, not merely flush"


@pytest.mark.asyncio
async def test_transaction_rolls_back_when_the_use_case_fails(session_factory):
    with pytest.raises(RuntimeError, match="use case exploded"):
        async with session_factory() as writer, transaction(writer):
            writer.add(_term(academic_year="rollback-me"))
            raise RuntimeError("use case exploded")

    async with session_factory() as reader:
        rows = (
            (
                await reader.execute(
                    select(AcademicTerm).where(AcademicTerm.academic_year == "rollback-me")
                )
            )
            .scalars()
            .all()
        )
    assert rows == [], "a failed use case must leave nothing behind"


@pytest.mark.asyncio
async def test_get_db_does_not_commit_on_its_own(session_factory, monkeypatch):
    """Regression guard: get_db must never become the owner of the commit."""
    import app.database.connection as connection

    # Point the dependency at a file-backed database so two sessions really do
    # have two connections (the suite default is a per-connection memory DB).
    monkeypatch.setattr(connection, "AsyncSessionLocal", session_factory)

    marker = f"get-db-{uuid4().hex[:8]}"
    dependency = connection.get_db()
    session = await anext(dependency)
    session.add(_term(academic_year=marker))
    await session.flush()
    await dependency.aclose()

    async with session_factory() as fresh:
        rows = (
            (await fresh.execute(select(AcademicTerm).where(AcademicTerm.academic_year == marker)))
            .scalars()
            .all()
        )
        assert rows == [], "get_db committed without a use case owning the transaction"


@pytest.mark.asyncio
async def test_api_create_is_visible_to_an_independent_session(session_factory):
    """End to end: one request per session, read back over another connection."""

    user = User(
        id=uuid4(),
        email="persist@localhost",
        hashed_password="not-a-real-hash",
        full_name="Persist Tester",
        is_active=True,
        is_superuser=True,
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_get_current_user():
        return user

    saved = {
        get_db: app.dependency_overrides.get(get_db),
        get_current_user: app.dependency_overrides.get(get_current_user),
    }
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    marker = f"api-{uuid4().hex[:8]}"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/academic-terms",
                json={
                    "name": "Persisted Term",
                    "academic_year": marker,
                    "semester": 1,
                    "start_date": "2031-06-01",
                    "end_date": "2031-10-31",
                    "is_active": True,
                    "is_current": False,
                },
            )
        assert response.status_code == 201, response.text

        async with session_factory() as reader:
            rows = (
                (
                    await reader.execute(
                        select(AcademicTerm).where(AcademicTerm.academic_year == marker)
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1, "the API left its row inside an open transaction"
        assert str(rows[0].id) == response.json()["id"]
    finally:
        for key, previous in saved.items():
            if previous is None:
                app.dependency_overrides.pop(key, None)
            else:
                app.dependency_overrides[key] = previous


@pytest.mark.asyncio
async def test_api_validation_failure_writes_nothing(session_factory):
    user = User(
        id=uuid4(),
        email="rollback@localhost",
        hashed_password="not-a-real-hash",
        full_name="Rollback Tester",
        is_active=True,
        is_superuser=True,
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_get_current_user():
        return user

    saved = {
        get_db: app.dependency_overrides.get(get_db),
        get_current_user: app.dependency_overrides.get(get_current_user),
    }
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    marker = f"api-dup-{uuid4().hex[:8]}"
    payload = {
        "name": "Duplicate Term",
        "academic_year": marker,
        "semester": 1,
        "start_date": "2031-06-01",
        "end_date": "2031-10-31",
        "is_active": True,
        "is_current": False,
    }
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post("/api/v1/academic-terms", json=payload)
            second = await client.post("/api/v1/academic-terms", json=payload)
        assert first.status_code == 201, first.text
        assert second.status_code == 400, second.text

        async with session_factory() as reader:
            rows = (
                (
                    await reader.execute(
                        select(AcademicTerm).where(AcademicTerm.academic_year == marker)
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1, "the rejected request must not leave a duplicate row"
    finally:
        for key, previous in saved.items():
            if previous is None:
                app.dependency_overrides.pop(key, None)
            else:
                app.dependency_overrides[key] = previous
