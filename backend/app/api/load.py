from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.permissions import LOAD_EDIT_ROLES, MANAGEMENT_ROLES
from app.database.transactions import transaction
from app.schemas.load import (
    FacultyLoadCreate,
    FacultyLoadImportPreview,
    FacultyLoadImportResult,
    FacultyLoadListResponse,
    FacultyLoadResponse,
    FacultyLoadUpdate,
    SessionType,
)
from app.services.load_service import LoadService

router = APIRouter(prefix="/load", tags=["load"])


@router.get("", response_model=FacultyLoadListResponse)
async def list_load(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    faculty_id: UUID | None = Query(None),
    academic_term_id: UUID | None = Query(None),
    subject_id: UUID | None = Query(None),
    class_id: UUID | None = Query(None),
    section_id: UUID | None = Query(None),
    session_type: SessionType | None = Query(None),
    is_active: bool | None = Query(None),
    is_approved: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = LoadService(db)
    loads, total = await service.get_all(
        page=page,
        page_size=page_size,
        faculty_id=faculty_id,
        academic_term_id=academic_term_id,
        subject_id=subject_id,
        class_id=class_id,
        section_id=section_id,
        session_type=session_type,
        is_active=is_active,
        is_approved=is_approved,
    )
    return FacultyLoadListResponse(
        items=[FacultyLoadResponse.model_validate(item) for item in loads],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{load_id}", response_model=FacultyLoadResponse)
async def get_load(
    load_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = LoadService(db)
    load = await service.get_by_id(load_id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load record not found")
    return load


@router.post("", response_model=FacultyLoadResponse, status_code=status.HTTP_201_CREATED)
async def create_load(
    data: FacultyLoadCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*LOAD_EDIT_ROLES)),
):
    service = LoadService(db)
    try:
        async with transaction(db):
            load = await service.create(data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return load


@router.put("/{load_id}", response_model=FacultyLoadResponse)
async def update_load(
    load_id: UUID,
    data: FacultyLoadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*LOAD_EDIT_ROLES)),
):
    service = LoadService(db)
    async with transaction(db):
        load = await service.update(load_id, data, user_id=current_user.id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load record not found")
    return load


@router.patch("/{load_id}/approve", response_model=FacultyLoadResponse)
async def approve_load(
    load_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = LoadService(db)
    async with transaction(db):
        load = await service.approve(load_id, approved_by=current_user.id)
    if not load:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load record not found")
    return load


@router.delete("/{load_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_load(
    load_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = LoadService(db)
    async with transaction(db):
        success = await service.delete(load_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Load record not found")


@router.post("/import/preview", response_model=list[FacultyLoadImportPreview])
async def preview_load_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*LOAD_EDIT_ROLES)),
):
    from app.importers.excel_loader import ExcelLoader

    if not (file.filename or "").endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)",
        )

    # Save uploaded file temporarily
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        loader = ExcelLoader()
        df = loader.load_load_distribution(tmp_path)

        service = LoadService(db)
        previews = await service.preview_import(df)
        return previews
    finally:
        os.unlink(tmp_path)


@router.post("/import", response_model=FacultyLoadImportResult)
async def import_load(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*LOAD_EDIT_ROLES)),
):
    if not (file.filename or "").endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)",
        )

    import os
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        service = LoadService(db)
        async with transaction(db):
            result = await service.import_from_excel(tmp_path, user_id=current_user.id)
        return FacultyLoadImportResult(
            preview=result["previews"],
            total_rows=len(result["previews"]),
            valid_rows=len([p for p in result["previews"] if not p.errors]),
            invalid_rows=len([p for p in result["previews"] if p.errors]),
            duplicates=0,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    finally:
        os.unlink(tmp_path)


@router.get("/reports/faculty-summary")
async def get_faculty_load_summary(
    academic_term_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = LoadService(db)
    summary = await service.get_faculty_load_summary(academic_term_id)
    return {"academic_term_id": academic_term_id, "summary": summary}


@router.get("/reports/class-summary")
async def get_class_load_summary(
    academic_term_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = LoadService(db)
    summary = await service.get_class_load_summary(academic_term_id)
    return {"academic_term_id": academic_term_id, "summary": summary}


@router.get("/reports/subject-summary")
async def get_subject_load_summary(
    academic_term_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = LoadService(db)
    summary = await service.get_subject_load_summary(academic_term_id)
    return {"academic_term_id": academic_term_id, "summary": summary}


@router.get("/reports/load-summary")
async def get_load_summary(
    academic_term_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = LoadService(db)
    faculty_summary = await service.get_faculty_load_summary(academic_term_id)
    class_summary = await service.get_class_load_summary(academic_term_id)
    subject_summary = await service.get_subject_load_summary(academic_term_id)

    return {
        "academic_term_id": academic_term_id,
        "faculty_summary": faculty_summary,
        "class_summary": class_summary,
        "subject_summary": subject_summary,
    }


@router.get("/template")
async def get_load_template():
    from io import BytesIO

    import pandas as pd
    from fastapi.responses import StreamingResponse

    # Create template DataFrame
    template_data = {
        "faculty_employee_id": [],
        "faculty_name": [],
        "subject_code": [],
        "subject_name": [],
        "class_name": [],
        "section": [],
        "batch": [],
        "session_type": [],
        "theory_hours": [],
        "practical_hours": [],
        "tutorial_hours": [],
        "project_hours": [],
        "session_duration": [],
        "required_resource_type": [],
        "notes": [],
        "academic_year": [],
        "semester": [],
    }

    df = pd.DataFrame(template_data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Load Distribution Template")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=load_distribution_template.xlsx"},
    )
