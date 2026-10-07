"""Login/token flow against in-memory SQLite (no Postgres needed)."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import get_password_hash
from app.database.connection import Base, get_db
from app.database.models import Permission, Role, User
from app.database.models.role import role_permissions
from app.database.models.user import user_roles
from app.main import app

PASSWORD = "correct-horse-battery"


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    tables = [
        Base.metadata.tables[t.name] for t in (User.__table__, Role.__table__, Permission.__table__)
    ]
    tables += [user_roles, role_permissions]
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add_all(
            [
                User(email="active@example.com", hashed_password=get_password_hash(PASSWORD)),
                User(
                    email="disabled@example.com",
                    hashed_password=get_password_hash(PASSWORD),
                    is_active=False,
                ),
            ]
        )
        await db.commit()

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


def _login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", data={"username": email, "password": password})


async def test_login_success_returns_usable_token(client):
    resp = await _login(client, "active@example.com")
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "active@example.com"


async def test_token_with_malformed_subject_is_401_not_500(client):
    from app.core.security import create_access_token

    token = create_access_token({"sub": "not-a-uuid"})
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_token_without_subject_is_401(client):
    from app.core.security import create_access_token

    token = create_access_token({})
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_login_wrong_password_is_401(client):
    assert (await _login(client, "active@example.com", "nope")).status_code == 401


async def test_login_unknown_user_is_401(client):
    assert (await _login(client, "ghost@example.com")).status_code == 401


async def test_login_disabled_account_is_rejected(client):
    resp = await _login(client, "disabled@example.com")
    assert resp.status_code == 403
    assert "access_token" not in resp.json()


async def test_disabled_account_with_wrong_password_is_not_revealed(client):
    # Wrong password must stay indistinguishable from an unknown user.
    assert (await _login(client, "disabled@example.com", "nope")).status_code == 401


async def test_swagger_token_url_matches_login_route():
    schema = app.openapi()
    flows = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]
    assert flows["password"]["tokenUrl"] == "/api/v1/auth/login"
    assert "/api/v1/auth/login" in schema["paths"]
