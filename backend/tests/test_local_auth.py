import pytest
from fastapi import HTTPException

from app.api.auth import get_current_user
from app.api.dependencies import require_permissions, require_roles
from app.core.config import settings
from app.core.permissions import Permission, Role
from app.database.models.user import User
from app.main import app


@pytest.mark.asyncio
async def test_local_auth_uses_existing_user_without_token(db_session, monkeypatch):
    user = User(
        email="local@example.com",
        hashed_password="unused",
        full_name="Local Prototype",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()

    monkeypatch.setattr(settings, "LOCAL_AUTH_DISABLED", True)
    resolved = await get_current_user(None, None, db_session)

    assert resolved.id == user.id
    assert resolved.email == "local@example.com"


@pytest.mark.asyncio
async def test_local_auth_does_not_fabricate_a_user(db_session, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_AUTH_DISABLED", True)

    with pytest.raises(HTTPException) as error:
        await get_current_user(None, None, db_session)

    assert error.value.status_code == 503
    assert "no record was created" in str(error.value.detail)


@pytest.mark.asyncio
async def test_local_auth_bypasses_role_and_permission_checks(db_session, monkeypatch):
    user = User(
        email="local-no-role@example.com",
        hashed_password="unused",
        full_name="Local Prototype",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    monkeypatch.setattr(settings, "LOCAL_AUTH_DISABLED", True)

    assert await require_roles(Role.ADMIN)(user) is user
    assert await require_permissions(Permission.TIMETABLE_GENERATE)(user) is user


@pytest.mark.asyncio
async def test_local_auth_allows_an_http_request_without_a_token(async_client, monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_AUTH_DISABLED", True)
    app.dependency_overrides.pop(get_current_user, None)

    response = await async_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"].endswith("@example.com")
