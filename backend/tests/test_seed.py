"""Seed script against in-memory SQLite."""

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool

from app.core.permissions import ROLE_PERMISSIONS
from app.core.permissions import Permission as PermissionEnum
from app.core.permissions import Role as RoleEnum
from app.core.security import verify_password
from app.database.connection import Base
from app.database.models import Permission, Role, User
from app.database.models.role import role_permissions
from app.database.models.user import user_roles
from app.database.seed import seed


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    tables = [Base.metadata.tables[n] for n in ("users", "roles", "permissions")]
    tables += [user_roles, role_permissions]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def _count(db, model):
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_creates_all_roles_and_permissions(db):
    summary = await seed(db)

    assert summary == {
        "permissions": len(PermissionEnum),
        "roles": len(RoleEnum),
        "admin": None,
    }
    assert await _count(db, User) == 0  # no admin without explicit credentials


async def test_role_permissions_match_canonical_mapping(db):
    await seed(db)

    roles = (await db.execute(select(Role).options(selectinload(Role.permissions)))).scalars().all()
    by_name = {r.name: {p.name for p in r.permissions} for r in roles}
    for role_enum, perms in ROLE_PERMISSIONS.items():
        assert by_name[role_enum.value] == {p.value for p in perms}


async def test_seed_is_idempotent(db):
    await seed(db, "admin@example.com", "pw-123456")
    await seed(db, "admin@example.com", "pw-123456")

    assert await _count(db, Permission) == len(PermissionEnum)
    assert await _count(db, Role) == len(RoleEnum)
    assert await _count(db, User) == 1


async def test_admin_user_gets_admin_role_and_hashed_password(db):
    await seed(db, "admin@example.com", "pw-123456")

    user = (await db.execute(select(User).options(selectinload(User.roles)))).scalar_one()
    assert [r.name for r in user.roles] == ["ADMIN"]
    assert user.hashed_password != "pw-123456"
    assert verify_password("pw-123456", user.hashed_password)


async def test_admin_requires_both_email_and_password(db):
    summary = await seed(db, admin_email="admin@example.com", admin_password=None)

    assert summary["admin"] is None
    assert await _count(db, User) == 0
