"""Seed reference data: roles, permissions, and (optionally) an initial admin user.

Idempotent: safe to run on every deploy.

    python -m app.database.seed

The admin user is only created when SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD are set;
there is deliberately no default password.
"""

import asyncio
import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import ROLE_PERMISSIONS
from app.core.permissions import Permission as PermissionEnum
from app.core.permissions import Role as RoleEnum
from app.core.security import get_password_hash, validate_password_strength
from app.database.models.permission import Permission
from app.database.models.role import Role
from app.database.models.user import User

logger = logging.getLogger(__name__)


async def seed_permissions(db: AsyncSession) -> dict[str, Permission]:
    existing = {p.name: p for p in (await db.execute(select(Permission))).scalars().all()}
    for perm in PermissionEnum:
        if perm.value not in existing:
            resource, action = perm.value.split(":", 1)
            row = Permission(name=perm.value, resource=resource, action=action)
            db.add(row)
            existing[perm.value] = row
    await db.flush()
    return existing


async def seed_roles(db: AsyncSession, permissions: dict[str, Permission]) -> dict[str, Role]:
    existing = {
        r.name: r
        for r in (await db.execute(select(Role).options(selectinload(Role.permissions))))
        .scalars()
        .all()
    }
    for role_enum in RoleEnum:
        role = existing.get(role_enum.value)
        if role is None:
            role = Role(name=role_enum.value, description=f"{role_enum.value} role")
            role.permissions = []
            db.add(role)
            existing[role_enum.value] = role

        have = {p.name for p in role.permissions}
        for perm in ROLE_PERMISSIONS.get(role_enum, []):
            if perm.value not in have:
                role.permissions.append(permissions[perm.value])
    await db.flush()
    return existing


async def seed_admin(
    db: AsyncSession, roles: dict[str, Role], email: str, password: str
) -> User | None:
    try:
        validate_password_strength(password)
    except ValueError as e:
        raise ValueError(f"SEED_ADMIN_PASSWORD rejected by password policy: {e}") from e
    user = (
        await db.execute(select(User).options(selectinload(User.roles)).where(User.email == email))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Administrator",
        )
        user.roles = []
        db.add(user)
    admin_role = roles[RoleEnum.ADMIN.value]
    if admin_role not in user.roles:
        user.roles.append(admin_role)
    await db.flush()
    return user


async def seed(
    db: AsyncSession, admin_email: str | None = None, admin_password: str | None = None
) -> dict:
    permissions = await seed_permissions(db)
    roles = await seed_roles(db, permissions)

    admin_created = False
    if admin_email and admin_password:
        await seed_admin(db, roles, admin_email, admin_password)
        admin_created = True
    elif admin_email or admin_password:
        logger.warning("Set both SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD to create an admin")

    await db.commit()
    return {
        "permissions": len(permissions),
        "roles": len(roles),
        "admin": admin_email if admin_created else None,
    }


async def main() -> None:
    from app.database.connection import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        summary = await seed(
            db,
            admin_email=os.environ.get("SEED_ADMIN_EMAIL"),
            admin_password=os.environ.get("SEED_ADMIN_PASSWORD"),
        )
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info(
        "Seeded %d permissions, %d roles%s",
        summary["permissions"],
        summary["roles"],
        f", admin user {summary['admin']}" if summary["admin"] else " (no admin user)",
    )


if __name__ == "__main__":
    asyncio.run(main())
