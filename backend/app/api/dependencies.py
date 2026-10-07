from fastapi import Depends, HTTPException, status

from app.api.auth import get_current_user
from app.core.permissions import ROLE_PERMISSIONS, Permission, Role
from app.database.connection import get_db
from app.database.models.user import User


def _user_role_names(user: User) -> set[str]:
    """Canonical role names held by the user (exact match; roles are stored uppercase)."""
    return {r.name for r in user.roles} if user.roles else set()


def require_roles(*allowed_roles: Role | str):
    """
    Dependency factory for server-side Role-Based Access Control (RBAC).

    Roles must be members of the canonical ``Role`` enum (ADMIN, HOD, EDITOR, ...). Passing
    an unknown name raises ``ValueError`` when the route is defined, not at request time.
    Superusers bypass the check. Raises 403 for users without any allowed role.
    """
    allowed = {Role(r).value for r in allowed_roles}

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user

        if not (_user_role_names(current_user) & allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: operation not permitted for this role",
            )
        return current_user

    return role_checker


def require_permissions(*required_permissions: Permission):
    """
    Dependency factory that checks permissions via the canonical ROLE_PERMISSIONS mapping.
    Superusers bypass the check. Any matching role that grants all required permissions suffices.
    Raises 403 HTTP Exception for insufficient permissions.
    """

    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user

        user_role_names = _user_role_names(current_user)

        for role_enum in Role:
            if role_enum.value not in user_role_names:
                continue
            role_perms = set(ROLE_PERMISSIONS.get(role_enum, []))
            if all(p in role_perms for p in required_permissions):
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: insufficient permissions",
        )

    return permission_checker


__all__ = ["get_db", "get_current_user", "require_roles", "require_permissions"]
