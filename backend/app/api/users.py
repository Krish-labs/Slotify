from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import get_current_user
from app.api.dependencies import require_permissions
from app.core.permissions import Permission

router = APIRouter(prefix="/users", tags=["users"])

_manage = require_permissions(Permission.USER_MANAGE)


@router.get("/")
async def list_users(current_user=Depends(_manage)):
    return {"message": "List users - TODO"}


@router.get("/{user_id}")
async def get_user(user_id: str, current_user=Depends(get_current_user)):
    # Owner may read self; all other reads require USER_MANAGE.
    if str(current_user.id) != str(user_id):
        if current_user.is_superuser:
            pass
        else:
            role_names = {r.name for r in current_user.roles} if current_user.roles else set()
            # Reuse canonical permission check without an extra dependency layer.
            from app.core.permissions import ROLE_PERMISSIONS, Role

            allowed = any(
                Permission.USER_MANAGE in set(ROLE_PERMISSIONS.get(role_enum, []))
                for role_enum in Role
                if role_enum.value in role_names
            )
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: insufficient permissions",
                )
    return {"message": f"Get user {user_id} - TODO"}


@router.post("/")
async def create_user(current_user=Depends(_manage)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User creation is not implemented yet",
    )


@router.put("/{user_id}")
async def update_user(user_id: str, current_user=Depends(_manage)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"User {user_id} update is not implemented yet",
    )


@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user=Depends(_manage)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"User {user_id} deletion is not implemented yet",
    )
