"""Backwards-compatible revocation helpers over the shared auth-state store.

Prefer app.core.auth_state.get_auth_state() in new code. These wrappers
preserve the historic names; they are async because the shared (Redis)
store is async.
"""

from __future__ import annotations

from app.core.auth_state import get_auth_state


async def revoke_jti(jti: str, ttl_seconds: int = 1800) -> None:
    await get_auth_state().revoke_jti(jti, ttl_seconds)


async def is_revoked(jti: str | None) -> bool:
    if not jti:
        return False
    return await get_auth_state().is_jti_revoked(jti)
