from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/")
async def list_users(current_user=Depends(get_current_user)):
    return {"message": "List users - TODO"}


@router.get("/{user_id}")
async def get_user(user_id: str, current_user=Depends(get_current_user)):
    return {"message": f"Get user {user_id} - TODO"}


@router.post("/")
async def create_user(current_user=Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="User creation is not implemented yet",
    )


@router.put("/{user_id}")
async def update_user(user_id: str, current_user=Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"User {user_id} update is not implemented yet",
    )


@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user=Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"User {user_id} deletion is not implemented yet",
    )
