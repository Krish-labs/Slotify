from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.config import settings
from app.core.permissions import LOAD_EDIT_ROLES, MANAGEMENT_ROLES
from app.core.workbook_paths import timing_reference_path
from app.database.models.faculty_load import FacultyLoad
from app.database.transactions import transaction
from app.schemas.load import (
    FacultyLoadCreate,
    FacultyLoadImportPreview,
    FacultyLoadImportResult,
    FacultyLoadListResponse,
    FacultyLoadResponse,
    FacultyLoadUpdate,
    LoadSourceApprovalResponse,
    LoadSourceImportResult,
    LoadSourceListResponse,
    LoadSourceRowCreate,
    LoadSourceRowResponse,
    LoadSourceRowUpdate,
    SessionType,
)
from app.services.assignment_derivation_service import AssignmentDerivationService
from app.services.load_service import LoadService
from app.services.load_source_service import LoadSourceService

router = APIRouter(prefix="/load", tags=["load"])


def _faculty_workbook_path() -> str:
    """Resolve the timing-reference workbook in Docker or local execution."""
    return str(timing_reference_path())


def _source_response(row):
    return LoadSourceRowResponse.model_validate(row)


_ALLOWED_EXCEL_EXTENSIONS = (".xlsx", ".xls")
_XLSX_MAGIC = b"PK\x03\x04"
_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _sanitize_upload_filename(filename: str | None) -> str:
    # Strip directories, control chars; cap length. Prevents stored
    # filename XSS / header injection when echoed back via API.
    base = Path(filename or "").name.strip().replace("\x00", "")
    base = "".join(ch for ch in base if ord(ch) >= 32)
    return (base or "upload.xlsx")[:128]


async def _read_upload_with_limits(file: UploadFile) -> tuple[bytes, str]:
    """Validate extension + size + magic bytes. Returns (content, safe_filename)."""
    safe_name = _sanitize_upload_filename(file.filename)
    if not safe_name.lower().endswith(_ALLOWED_EXCEL_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)",
        )
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    # .xls may also arrive as zip-based content; accept either magic.
    if not (content.startswith(_XLSX_MAGIC) or content.startswith(_XLS_MAGIC)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match its Excel extension",
        )
    return content, safe_name


@router.get("/source", response_model=LoadSourceListResponse)
async def list_source_load(
    semester: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = await LoadSourceService(db).list_rows(semester)
    return LoadSourceListResponse(
        items=[_source_response(row) for row in rows],
        semesters=sorted({row.source_semester for row in rows}),
        total=len(rows),
    )


@router.post("/source", response_model=LoadSourceRowResponse, status_code=status.HTTP_201_CREATED)
async def create_source_load(
    data: LoadSourceRowCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*LOAD_EDIT_ROLES)),
):
    async with transaction(db):
        row = await LoadSourceService(db).create(data.model_dump(), current_user.id)
    return _source_response(row)


@router.put("/source/{row_id}", response_model=LoadSourceRowResponse)
async def update_source_load(
    row_id: UUID,
    data: LoadSourceRowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*LOAD_EDIT_ROLES)),
):
    async with transaction(db):
        row = await LoadSourceService(db).update(
            row_id, data.model_dump(exclude_unset=True), current_user.id
        )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source row not found")
    return _source_response(row)


@router.delete("/source/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source_load(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*LOAD_EDIT_ROLES)),
):
    async with transaction(db):
        deleted = await LoadSourceService(db).delete(row_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source row not found")


@router.post("/source/{row_id}/approve", response_model=LoadSourceApprovalResponse)
async def approve_source_load(
    row_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    try:
        async with transaction(db):
            row = await LoadSourceService(db).approve(row_id, current_user.id)
            if row.academic_term_id is None:
                raise ValueError("Academic term mapping is required before approval")
            # Derive only this row's load: a full-term derivation per approval
            # re-derives every sibling load and historically duplicated
            # practical/tutorial/project assignments on repeat approvals.
            load = await db.get(FacultyLoad, row.faculty_load_id)
            if load is None:
                raise ValueError("Approved load record is missing for this source row")
            derivation = await AssignmentDerivationService(db).derive_load(load, current_user.id)
            if derivation["errors"]:
                raise ValueError("; ".join(derivation["errors"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return LoadSourceApprovalResponse(
        **_source_response(row).model_dump(), assignments_created=derivation["derived"]
    )


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


@router.get("/template")
async def get_load_template(current_user=Depends(get_current_user)):
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
        if load:
            derivation = await AssignmentDerivationService(db).derive_assignments(
                load.academic_term_id,
                current_user.id,
            )
            if derivation["errors"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": "Load approval blocked because assignments could not be derived",
                        "errors": derivation["errors"],
                    },
                )
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

    content, _safe_name = await _read_upload_with_limits(file)

    # Save uploaded file temporarily
    import contextlib
    import os
    import tempfile

    suffix = ".xlsx" if _safe_name.lower().endswith(".xlsx") else ".xls"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        loader = ExcelLoader()
        df = loader.load_load_distribution(tmp_path)

        service = LoadService(db)
        previews = await service.preview_import(df)
        return previews
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)


@router.post("/import", response_model=None)
async def import_load(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*LOAD_EDIT_ROLES)),
):
    content, safe_name = await _read_upload_with_limits(file)

    import contextlib
    import os
    import tempfile

    suffix = ".xlsx" if safe_name.lower().endswith(".xlsx") else ".xls"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        service = LoadService(db)
        async with transaction(db):
            from app.importers.excel_loader import ExcelLoader

            loader = ExcelLoader()
            if loader.is_source_load_distribution(tmp_path):
                source_result = await LoadSourceService(db).import_workbook(
                    tmp_path,
                    user_id=current_user.id,
                    faculty_workbook=_faculty_workbook_path(),
                    source_file=safe_name,
                )
                return LoadSourceImportResult(**source_result)
            normalized_result = await service.import_from_excel(tmp_path, user_id=current_user.id)
        return FacultyLoadImportResult(
            preview=normalized_result["previews"],
            total_rows=len(normalized_result["previews"]),
            valid_rows=len([p for p in normalized_result["previews"] if not p.errors]),
            invalid_rows=len([p for p in normalized_result["previews"] if p.errors]),
            duplicates=0,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    finally:
        with contextlib.suppress(OSError):
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
