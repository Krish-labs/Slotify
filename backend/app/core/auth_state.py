"""Shared authentication state for multi-worker deployments.

Token revocation and login throttling must be visible to every backend
worker. The Redis store provides that; the memory store is a single-process
fallback for tests and for development without Redis.

Backend selection comes from settings.AUTH_STATE_BACKEND:
- "redis": require shared Redis state; Redis errors fail loudly.
- "memory": always process-local (tests, single-process use).
- "auto": Redis when reachable, permanent process-local fallback with a
  warning on first Redis failure (never silent, never flapping).

The memory fallback is never silent: selection and every fallback are
logged so operators can tell shared state is not in effect.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)


class AuthStateStore(Protocol):
    async def revoke_jti(self, jti: str, ttl_seconds: int) -> None: ...
    async def is_jti_revoked(self, jti: str) -> bool: ...
    async def check_login_allowed(self, key: str) -> bool:
        """Record an attempt; True when under the limit, False when throttled."""
        ...

    async def clear_login(self, key: str) -> None: ...


class MemoryAuthStateStore:
    """Process-local store. Shared only when instances share one backing dict."""

    def __init__(
        self,
        backing: dict | None = None,
        max_attempts: int = 5,
        window_seconds: float = 60.0,
    ) -> None:
        self._state: dict[str, Any] = backing if backing is not None else {}
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds

    def _revoked(self) -> set[str]:
        return cast(set[str], self._state.setdefault("revoked", set()))

    def _attempts(self) -> dict[str, list[float]]:
        return cast(dict[str, list[float]], self._state.setdefault("attempts", {}))

    async def revoke_jti(self, jti: str, ttl_seconds: int) -> None:
        if jti:
            self._revoked().add(jti)

    async def is_jti_revoked(self, jti: str) -> bool:
        return bool(jti) and jti in self._revoked()

    async def check_login_allowed(self, key: str) -> bool:
        now = time.monotonic()
        attempts = self._attempts()
        recent = [t for t in attempts.get(key, []) if now - t < self._window_seconds]
        if len(recent) >= self._max_attempts:
            attempts[key] = recent
            return False
        recent.append(now)
        attempts[key] = recent
        return True

    async def clear_login(self, key: str) -> None:
        self._attempts().pop(key, None)


class RedisAuthStateStore:
    """Shared store. Revocations expire with the token; throttle windows
    are Redis sorted sets so every worker observes the same counts.

    With strict=False ("auto"), the first Redis failure permanently
    degrades this instance to its internal memory store after logging a
    warning. With strict=True ("redis"), Redis errors propagate.
    """

    def __init__(
        self,
        redis_client,
        max_attempts: int = 5,
        window_seconds: float = 60.0,
        strict: bool = True,
    ) -> None:
        self._redis = redis_client
        self._strict = strict
        self._fallback = MemoryAuthStateStore(
            max_attempts=max_attempts, window_seconds=window_seconds
        )
        self._degraded = False

    @staticmethod
    def _revoke_key(jti: str) -> str:
        return f"auth:revoked:{jti}"

    @staticmethod
    def _throttle_key(key: str) -> str:
        return f"auth:throttle:{key}"

    async def _run(self, method: str, *args):
        if self._degraded:
            return await getattr(self._fallback, method)(*args)
        try:
            return await getattr(self, f"_redis_{method}")(*args)
        except Exception as exc:
            if self._strict:
                raise
            self._degraded = True
            logger.warning(
                "auth-state: Redis unavailable (%s); degraded to process-local "
                "memory store — revocation and throttling are NOT shared "
                "between workers until restart",
                exc,
            )
            return await getattr(self._fallback, method)(*args)

    async def _redis_revoke_jti(self, jti: str, ttl_seconds: int) -> None:
        if not jti:
            return
        await self._redis.set(self._revoke_key(jti), "1", ex=max(1, int(ttl_seconds)))

    async def _redis_is_jti_revoked(self, jti: str) -> bool:
        if not jti:
            return False
        return bool(await self._redis.exists(self._revoke_key(jti)))

    async def _redis_check_login_allowed(self, key: str) -> bool:
        now = time.monotonic()
        rkey = self._throttle_key(key)
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(rkey, 0, now - self._fallback._window_seconds)
        pipe.zadd(rkey, {repr((now, id(self))): now})
        pipe.zcard(rkey)
        pipe.expire(rkey, int(self._fallback._window_seconds) + 1)
        _, _, count, _ = await pipe.execute()
        return int(count) <= self._fallback._max_attempts

    async def _redis_clear_login(self, key: str) -> None:
        await self._redis.delete(self._throttle_key(key))

    async def revoke_jti(self, jti: str, ttl_seconds: int) -> None:
        await self._run("revoke_jti", jti, ttl_seconds)

    async def is_jti_revoked(self, jti: str) -> bool:
        return bool(await self._run("is_jti_revoked", jti))

    async def check_login_allowed(self, key: str) -> bool:
        return bool(await self._run("check_login_allowed", key))

    async def clear_login(self, key: str) -> None:
        await self._run("clear_login", key)


_configured_store: AuthStateStore | None = None


def configure_auth_state(store: AuthStateStore | None) -> None:
    """Override the process store (tests). Pass None to reset to settings."""
    global _configured_store
    _configured_store = store


def get_auth_state() -> AuthStateStore:
    """Process store honoring AUTH_STATE_BACKEND; lazily built on first use."""
    global _configured_store
    if _configured_store is not None:
        return _configured_store

    from app.core.config import settings

    backend = settings.AUTH_STATE_BACKEND
    max_attempts: int = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
    window_seconds = float(settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    if backend == "memory":
        logger.info("auth-state: using process-local memory store (AUTH_STATE_BACKEND=memory)")
        _configured_store = MemoryAuthStateStore(
            max_attempts=max_attempts, window_seconds=window_seconds
        )
        return _configured_store

    from redis.asyncio import Redis

    client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    if backend == "redis":
        logger.info("auth-state: using shared Redis store (AUTH_STATE_BACKEND=redis)")
        _configured_store = RedisAuthStateStore(
            client, max_attempts=max_attempts, window_seconds=window_seconds, strict=True
        )
    else:
        logger.info("auth-state: trying shared Redis store (AUTH_STATE_BACKEND=auto)")
        _configured_store = RedisAuthStateStore(
            client, max_attempts=max_attempts, window_seconds=window_seconds, strict=False
        )
    return _configured_store
