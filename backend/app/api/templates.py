from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/")
async def list_templates(current_user=Depends(get_current_user)):
    return {"message": "List timetable templates - TODO"}


@router.get("/{template_id}")
async def get_template(template_id: str, current_user=Depends(get_current_user)):
    return {"message": f"Get template {template_id} - TODO"}


@router.post("/")
async def create_template(current_user=Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Template creation is not implemented yet",
    )


@router.put("/{template_id}")
async def update_template(template_id: str, current_user=Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Template {template_id} update is not implemented yet",
    )


@router.delete("/{template_id}")
async def delete_template(template_id: str, current_user=Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Template {template_id} deletion is not implemented yet",
    )


@router.get("/{template_id}/time-slots")
async def get_template_time_slots(template_id: str, current_user=Depends(get_current_user)):
    return {"message": f"Get time slots for template {template_id} - TODO"}


@router.post("/{template_id}/time-slots")
async def create_time_slot(template_id: str, current_user=Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Template {template_id} time slots are not implemented yet",
    )
