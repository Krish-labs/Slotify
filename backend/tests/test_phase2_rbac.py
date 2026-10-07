import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.core.exceptions import UnauthorizedError
from app.core.permissions import Role as RoleEnum
from app.database.models.role import Role
from app.database.models.user import User
from app.main import app

TERM_PAYLOAD = {
    "name": "2026-27 Sem I",
    "academic_year": "2026-27",
    "semester": 1,
    "start_date": "2026-07-01",
    "end_date": "2026-12-31",
    "is_active": True,
    "is_current": True,
}


@pytest.fixture
async def create_user_with_role(db_session: AsyncSession):
    async def _create(role_name: str | None, is_superuser: bool = False):
        user = User(
            email=f"{role_name or 'norole'}_{is_superuser}@example.com",
            hashed_password="hashed_pass",
            full_name=f"User {role_name}",
            is_active=True,
            is_superuser=is_superuser,
        )
        if role_name:
            role = Role(name=role_name)
            db_session.add(role)
            await db_session.flush()
            user.roles.append(role)

        db_session.add(user)
        await db_session.commit()

        # Eagerly load roles to avoid lazy-loading issues in dependency overrides
        result = await db_session.execute(
            select(User).options(selectinload(User.roles)).where(User.id == user.id)
        )
        user = result.scalar_one()
        return user

    return _create


async def _post_term_as(async_client: AsyncClient, user: User):
    async def override_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        return await async_client.post("/api/v1/academic-terms", json=TERM_PAYLOAD)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [RoleEnum.ADMIN, RoleEnum.HOD, RoleEnum.SUPER_ADMIN])
async def test_rbac_authorized_role(async_client: AsyncClient, create_user_with_role, role):
    """Management roles can perform protected operations"""
    user = await create_user_with_role(role.value)
    response = await _post_term_as(async_client, user)
    assert response.status_code == 201


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [RoleEnum.EDITOR, RoleEnum.FACULTY, RoleEnum.VIEWER])
async def test_rbac_unauthorized_role(async_client: AsyncClient, create_user_with_role, role):
    """Non-management roles receive 403 Forbidden"""
    user = await create_user_with_role(role.value)
    response = await _post_term_as(async_client, user)
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_name", ["Admin", "Manager", "Faculty"])
async def test_rbac_legacy_role_names_grant_nothing(
    async_client: AsyncClient, create_user_with_role, legacy_name
):
    """Only canonical (uppercase enum) role names carry privileges."""
    user = await create_user_with_role(legacy_name)
    response = await _post_term_as(async_client, user)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rbac_unauthenticated(async_client: AsyncClient):
    """Test unauthenticated request receives 401 Unauthorized"""

    async def override_unauth():
        raise UnauthorizedError()

    app.dependency_overrides[get_current_user] = override_unauth

    try:
        response = await async_client.post(
            "/api/v1/academic-terms",
            json={
                "name": "Test",
                "academic_year": "2026-27",
                "semester": 1,
                "start_date": "2026-07-01",
                "end_date": "2026-12-31",
            },
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_current_user, None)
