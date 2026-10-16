"""P0 auth hardening: shared revocation/throttling state, password policy,
audit-log redaction, and multi-worker behavior simulation."""

import logging

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.auth_state import (
    MemoryAuthStateStore,
    RedisAuthStateStore,
    configure_auth_state,
    get_auth_state,
)
from app.core.exceptions import ValidationError
from app.core.security import create_access_token, get_password_hash
from app.database.connection import Base, get_db
from app.database.models import Permission, Role, User
from app.database.models.role import role_permissions
from app.database.models.user import user_roles
from app.main import app
from app.services.auth_service import AuthService

PASSWORD = "correct-horse-battery-9"


@pytest.fixture
def isolated_auth_state():
    """Each test gets a fresh process store; global override always reset."""
    configure_auth_state(MemoryAuthStateStore())
    yield
    configure_auth_state(None)


@pytest_asyncio.fixture
async def client(isolated_auth_state):
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
        db.add(User(email="active@example.com", hashed_password=get_password_hash(PASSWORD)))
        await db.commit()

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


# --- Shared-state behavior (multi-worker simulation) -------------------------


async def test_revocation_visible_across_workers_sharing_state():
    """Two workers backed by one shared dict observe each other's revocations."""
    shared: dict = {}
    worker_a = MemoryAuthStateStore(backing=shared)
    worker_b = MemoryAuthStateStore(backing=shared)
    await worker_a.revoke_jti("jti-1", 300)
    assert await worker_b.is_jti_revoked("jti-1") is True
    assert await worker_a.is_jti_revoked("jti-1") is True


async def test_throttle_counts_shared_across_workers():
    shared: dict = {}
    worker_a = MemoryAuthStateStore(backing=shared, max_attempts=2, window_seconds=60)
    worker_b = MemoryAuthStateStore(backing=shared, max_attempts=2, window_seconds=60)
    assert await worker_a.check_login_allowed("ip|user") is True
    assert await worker_b.check_login_allowed("ip|user") is True
    # Third attempt anywhere is throttled: the count is shared, not per-worker.
    assert await worker_a.check_login_allowed("ip|user") is False
    await worker_b.clear_login("ip|user")
    assert await worker_a.check_login_allowed("ip|user") is True


async def test_memory_store_window_expiry():
    store = MemoryAuthStateStore(max_attempts=1, window_seconds=0.01)
    assert await store.check_login_allowed("k") is True
    assert await store.check_login_allowed("k") is False
    import asyncio

    await asyncio.sleep(0.02)
    assert await store.check_login_allowed("k") is True


# --- Redis store logic against a fake client ---------------------------------


class _FakePipeline:
    def __init__(self, client):
        self._client = client
        self._ops = []

    def zremrangebyscore(self, key, low, high):
        self._ops.append(("zrem", key, low, high))
        return self

    def zadd(self, key, mapping):
        self._ops.append(("zadd", key, mapping))
        return self

    def zcard(self, key):
        self._ops.append(("zcard", key))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    async def execute(self):
        results = []
        for op in self._ops:
            if op[0] == "zrem":
                _, key, low, high = op
                members = self._client._zsets.get(key, {})
                kept = {m: s for m, s in members.items() if not (low <= s <= high)}
                self._client._zsets[key] = kept
                results.append(0)
            elif op[0] == "zadd":
                _, key, mapping = op
                self._client._zsets.setdefault(key, {}).update(mapping)
                results.append(len(mapping))
            elif op[0] == "zcard":
                results.append(len(self._client._zsets.get(op[1], {})))
            elif op[0] == "expire":
                results.append(True)
        return results


class _FakeRedis:
    """Minimal async Redis double supporting only what the store uses."""

    def __init__(self):
        self._kv = {}
        self._zsets = {}

    async def set(self, key, value, ex=None):
        self._kv[key] = value
        return True

    async def exists(self, key):
        return 1 if key in self._kv else 0

    async def delete(self, *keys):
        removed = 0
        for key in keys:
            removed += self._kv.pop(key, None) is not None
            removed += self._zsets.pop(key, None) is not None
        return removed

    def pipeline(self):
        return _FakePipeline(self)


class _FailingRedis(_FakeRedis):
    async def set(self, key, value, ex=None):
        raise ConnectionError("redis down")

    async def exists(self, key):
        raise ConnectionError("redis down")

    def pipeline(self):
        raise ConnectionError("redis down")


async def test_redis_store_revocation_roundtrip():
    store = RedisAuthStateStore(_FakeRedis())
    assert await store.is_jti_revoked("abc") is False
    await store.revoke_jti("abc", 300)
    assert await store.is_jti_revoked("abc") is True


async def test_redis_store_throttle_counts():
    store = RedisAuthStateStore(_FakeRedis(), max_attempts=2, window_seconds=60)
    assert await store.check_login_allowed("k") is True
    assert await store.check_login_allowed("k") is True
    assert await store.check_login_allowed("k") is False
    await store.clear_login("k")
    assert await store.check_login_allowed("k") is True


async def test_redis_store_strict_propagates_failures():
    store = RedisAuthStateStore(_FailingRedis(), strict=True)
    with pytest.raises(ConnectionError):
        await store.is_jti_revoked("abc")


async def test_redis_store_auto_degrades_once_with_warning(caplog):
    store = RedisAuthStateStore(_FailingRedis(), strict=False)
    with caplog.at_level(logging.WARNING, logger="app.core.auth_state"):
        assert await store.is_jti_revoked("abc") is False
    assert "degraded to process-local" in caplog.text
    # Degraded: memory semantics from here on, no further Redis attempts.
    await store.revoke_jti("abc", 300)
    assert await store.is_jti_revoked("abc") is True


# --- Endpoint integration -----------------------------------------------------


async def test_logout_revokes_token_for_subsequent_requests(client):
    login = await client.post(
        "/api/v1/auth/login", data={"username": "active@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200
    assert (
        await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 204
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 401


async def test_refresh_token_rotation_single_use(client):
    login = await client.post(
        "/api/v1/auth/login", data={"username": "active@example.com", "password": PASSWORD}
    )
    refresh = login.json()["refresh_token"]
    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert first.status_code == 200
    # Replaying the rotated refresh token is rejected.
    second = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert second.status_code == 401


async def test_refresh_prefers_cookie_over_stale_access_bearer(client):
    login = await client.post(
        "/api/v1/auth/login", data={"username": "active@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200

    response = await client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_throttled_after_max_attempts(client):
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login", data={"username": "active@example.com", "password": "wrong"}
        )
        assert resp.status_code == 401
    throttled = await client.post(
        "/api/v1/auth/login", data={"username": "active@example.com", "password": "wrong"}
    )
    assert throttled.status_code == 429


async def test_throttle_key_uses_proxy_forwarded_ip(client):
    """Behind Nginx (private peer), the last XFF entry identifies the client."""
    from fastapi import Request

    def _request(peer: str, xff: str | None):
        scope = {
            "type": "http",
            "headers": [(b"x-forwarded-for", xff.encode())] if xff else [],
            "client": (peer, 1234),
        }
        return Request(scope)

    from app.api.auth import _client_ip

    assert _client_ip(_request("172.18.0.3", "203.0.113.9, 172.18.0.3")) == "172.18.0.3"
    # Public peer: spoofed XFF is ignored so identities cannot be rotated.
    assert _client_ip(_request("8.8.8.8", "10.9.9.9")) == "8.8.8.8"
    # No forwarding header: peer address is used as-is.
    assert _client_ip(_request("127.0.0.1", None)) == "127.0.0.1"


async def test_audit_log_never_contains_secrets(client, caplog):
    secret_password = "Sup3rSecret-Password-9999"
    with caplog.at_level(logging.INFO, logger="schedulai.audit"):
        await client.post(
            "/api/v1/auth/login",
            data={"username": "active@example.com", "password": secret_password},
        )
        login = await client.post(
            "/api/v1/auth/login", data={"username": "active@example.com", "password": PASSWORD}
        )
    assert secret_password not in caplog.text
    assert "Sup3rSecret" not in caplog.text

    token = login.json()["access_token"]
    assert token not in caplog.text


# --- Password policy -----------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(
                c,
                tables=[
                    User.__table__,
                    Role.__table__,
                    Permission.__table__,
                    user_roles,
                    role_permissions,
                ],
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_create_user_rejects_short_password(db_session):
    service = AuthService(db_session)
    with pytest.raises(ValidationError, match="at least 12 characters"):
        await service.create_user("new@example.com", "short")


async def test_create_user_accepts_policy_password(db_session):
    service = AuthService(db_session)
    user = await service.create_user("new@example.com", "long-enough-password-1")
    assert user.email == "new@example.com"


async def test_get_auth_state_memory_backend_selection(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "AUTH_STATE_BACKEND", "memory")
    configure_auth_state(None)
    try:
        assert isinstance(get_auth_state(), MemoryAuthStateStore)
    finally:
        configure_auth_state(MemoryAuthStateStore())


async def test_revoked_access_token_rejected_even_if_signature_valid(client):
    token = create_access_token({"sub": "00000000-0000-0000-0000-000000000001"})
    # No such user AND revoked jti must both yield 401, never 500.
    from app.core.security import decode_access_token
    from app.core.token_blocklist import revoke_jti

    payload = decode_access_token(token)
    await revoke_jti(payload["jti"], 300)
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
