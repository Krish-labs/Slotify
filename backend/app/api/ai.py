from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_current_user
from app.services.ai_constraint_service import (
    ConstraintInterpretation,
    ConstraintProviderUnavailable,
    explain_validation_failure,
    parse_requirement,
    suggest_repair_adjustments,
)

router = APIRouter(prefix="/ai", tags=["ai"])


class ConstraintParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement: str = Field(min_length=1, description="Natural-language scheduling requirement")
    context: dict[str, str] | None = Field(default=None, max_length=50)


class ConstraintParseResponse(BaseModel):
    source: str
    model: str | None = None
    constraint: ConstraintInterpretation | None = None
    message: str | None = None


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnostics: list[str] = Field(min_length=1, max_length=50)


class SuggestRepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnostics: list[str] = Field(min_length=1, max_length=50)
    context: dict[str, str] | None = Field(default=None, max_length=50)


@router.post("/parse-constraint", response_model=ConstraintParseResponse)
async def parse_constraint(
    data: ConstraintParseRequest,
    current_user=Depends(get_current_user),
):
    """Natural-language requirement -> structured constraint (interpretation only).

    The LLM NEVER generates timetable entries: its validated output is a
    constraint/preference object that feeds CP-SAT solver input through the
    normal Load Distribution / TeachingAssignment workflow.
    """
    try:
        result = await parse_requirement(data.requirement, data.context)
    except ConstraintProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ConstraintParseResponse(**result)


@router.post("/explain-validation")
async def explain_validation(data: ExplainRequest, current_user=Depends(get_current_user)):
    return await explain_validation_failure(data.diagnostics)


@router.post("/suggest-repair")
async def suggest_repair(data: SuggestRepairRequest, current_user=Depends(get_current_user)):
    """Suggest candidate repair adjustments for structured diagnostics.

    Returns closed-schema adjustment candidates only — never timetable
    entries. Availability overrides still require explicit approval in the
    repair endpoint, and every candidate is re-validated before use.
    """
    try:
        return await suggest_repair_adjustments(data.diagnostics, data.context)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
