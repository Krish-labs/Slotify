"""Role standardisation: every guard uses the canonical Role enum. No database needed."""

import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.api.dependencies import require_permissions, require_roles
from app.core.permissions import (
    LOAD_EDIT_ROLES,
    MANAGEMENT_ROLES,
    Permission,
    Role,
)


def _user(*role_names, is_superuser=False):
    return SimpleNamespace(
        id=uuid4(),
        is_superuser=is_superuser,
        roles=[SimpleNamespace(name=n) for n in role_names],
    )


async def _passes(checker, user) -> bool:
    try:
        await checker(current_user=user)
    except HTTPException as exc:
        assert exc.status_code == 403
        return False
    return True


# ---------------------------------------------------------------- canonical names


@pytest.mark.parametrize("legacy", ["Manager", "Admin", "manager", "Editor", "Faculty", "Nope"])
def test_non_canonical_role_names_are_rejected_at_definition_time(legacy):
    with pytest.raises(ValueError):
        require_roles(legacy)


def test_role_enum_members_and_canonical_strings_are_accepted():
    assert callable(require_roles(Role.ADMIN, "HOD", *MANAGEMENT_ROLES))


def test_management_roles_are_canonical():
    assert set(MANAGEMENT_ROLES) == {Role.SUPER_ADMIN, Role.ADMIN, Role.HOD}
    assert set(LOAD_EDIT_ROLES) == set(MANAGEMENT_ROLES) | {Role.EDITOR}


def test_no_endpoint_uses_string_literal_role_names():
    """Guards must use Role/role-group constants, never free-form strings."""
    api_dir = Path(__file__).parent.parent / "app" / "api"
    offenders = []
    for path in api_dir.glob("*.py"):
        for match in re.finditer(r"require_roles\(([^)]*)\)", path.read_text()):
            if re.search(r"""["']""", match.group(1)):
                offenders.append(f"{path.name}: {match.group(0)}")
    assert not offenders, offenders


# ---------------------------------------------------------------- require_roles behaviour


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (Role.SUPER_ADMIN, True),
        (Role.ADMIN, True),
        (Role.HOD, True),
        (Role.EDITOR, False),
        (Role.FACULTY, False),
        (Role.VIEWER, False),
    ],
)
async def test_management_guard_matrix(role, allowed):
    checker = require_roles(*MANAGEMENT_ROLES)
    assert await _passes(checker, _user(role.value)) is allowed


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (Role.ADMIN, True),
        (Role.HOD, True),
        (Role.EDITOR, True),
        (Role.FACULTY, False),
        (Role.VIEWER, False),
    ],
)
async def test_load_edit_guard_matrix(role, allowed):
    checker = require_roles(*LOAD_EDIT_ROLES)
    assert await _passes(checker, _user(role.value)) is allowed


async def test_stored_role_names_must_match_exactly():
    # A legacy "Admin" row is not the canonical ADMIN role and grants nothing.
    assert not await _passes(require_roles(Role.ADMIN), _user("Admin"))
    assert not await _passes(require_roles(Role.ADMIN), _user("Manager"))


async def test_user_with_no_roles_is_forbidden():
    assert not await _passes(require_roles(*MANAGEMENT_ROLES), _user())


async def test_any_one_matching_role_is_enough():
    assert await _passes(require_roles(*MANAGEMENT_ROLES), _user("VIEWER", "HOD"))


async def test_superuser_flag_bypasses_role_check():
    assert await _passes(require_roles(Role.ADMIN), _user(is_superuser=True))


# ---------------------------------------------------------------- require_permissions


async def test_permission_guard_uses_canonical_mapping():
    approve = require_permissions(Permission.TIMETABLE_APPROVE)
    assert await _passes(approve, _user("HOD"))
    assert not await _passes(approve, _user("EDITOR"))
    assert not await _passes(approve, _user("Hod"))  # exact names only


# ---------------------------------------------------------------- HTTP wiring (SQLite)


@pytest_asyncio.fixture
async def http():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.dialects.postgresql import INET
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.pool import StaticPool

    from app.api.auth import get_current_user
    from app.database.connection import Base, get_db
    from app.database.models import AcademicTerm, AuditLog
    from app.main import app

    @compiles(INET, "sqlite")
    def _inet_as_text(type_, compiler, **kw):  # audit_logs.ip_address is Postgres-only
        return "VARCHAR(45)"

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(
                c, tables=[AcademicTerm.__table__, AuditLog.__table__]
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        async def as_user(user, method, url, **kwargs):
            app.dependency_overrides[get_current_user] = lambda: user
            return await client.request(method, url, **kwargs)

        yield as_user

    app.dependency_overrides.clear()
    await engine.dispose()


def _term(n):
    return {
        "name": f"Term {n}",
        "academic_year": f"20{n}-{n + 1}",
        "semester": 1,
        "start_date": "2026-07-01",
        "end_date": "2026-12-31",
    }


@pytest.mark.parametrize(
    ("role", "status"),
    [("ADMIN", 201), ("HOD", 201), ("SUPER_ADMIN", 201), ("EDITOR", 403), ("FACULTY", 403)],
)
async def test_academic_term_create_requires_management_role(http, role, status):
    resp = await http(_user(role), "POST", "/api/v1/academic-terms", json=_term(26))
    assert resp.status_code == status, resp.text


async def test_legacy_role_names_cannot_use_management_endpoints(http):
    for legacy in ("Admin", "Manager"):
        resp = await http(_user(legacy), "POST", "/api/v1/academic-terms", json=_term(27))
        assert resp.status_code == 403


async def test_editor_can_reach_load_import_but_not_load_approval(http):
    editor = _user("EDITOR")
    # Guard passes for EDITOR, so the request proceeds to validation (422: no file sent).
    resp = await http(editor, "POST", "/api/v1/load/import/preview", files={})
    assert resp.status_code != 403

    approve = await http(editor, "PATCH", f"/api/v1/load/{uuid4()}/approve")
    assert approve.status_code == 403

    delete = await http(editor, "DELETE", f"/api/v1/load/{uuid4()}")
    assert delete.status_code == 403
