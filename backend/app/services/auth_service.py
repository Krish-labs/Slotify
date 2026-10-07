from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.security import create_access_token, get_password_hash, verify_password
from app.database.models.role import Role
from app.database.models.user import User


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, email: str, password: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not user.is_active or not verify_password(password, user.hashed_password):
            return None
        return user

    async def create_user(self, email: str, password: str, full_name: str | None = None) -> User:
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ValidationError("Email already registered")

        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def assign_role(self, user_id: str, role_name: str) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValidationError("User not found")

        role_result = await self.db.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one_or_none()
        if not role:
            raise ValidationError(f"Role {role_name} not found")

        if role not in user.roles:
            user.roles.append(role)
        return user

    def create_token(self, user_id: str) -> str:
        return create_access_token(data={"sub": user_id})
