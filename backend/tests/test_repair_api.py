"""HTTP wiring for the hybrid-scheduling endpoints.

Service behavior is covered in test_bounded_repair.py and
test_ai_constraint_service.py; here only the API layer is verified:
authentication, request validation, and status-code contracts.
"""

import uuid

from httpx import AsyncClient


async def test_parse_constraint_without_ai_returns_503(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/ai/parse-constraint",
        json={"requirement": "Alice is off Friday"},
    )

    assert response.status_code == 503


async def test_parse_constraint_rejects_empty_requirement(async_client: AsyncClient):
    response = await async_client.post("/api/v1/ai/parse-constraint", json={"requirement": ""})

    assert response.status_code == 422


async def test_suggest_repair_returns_schema_valid_candidates(async_client: AsyncClient):
    from app.schemas.repair import RepairAdjustment

    response = await async_client.post(
        "/api/v1/ai/suggest-repair",
        json={"diagnostics": ["Coverage mismatch: assignment X scheduled 0h, required 2h"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "deterministic"
    assert body["candidates"]
    for candidate in body["candidates"]:
        RepairAdjustment.model_validate(candidate)
        assert "entries" not in candidate


async def test_suggest_repair_rejects_empty_diagnostics(async_client: AsyncClient):
    response = await async_client.post("/api/v1/ai/suggest-repair", json={"diagnostics": []})

    assert response.status_code == 422


async def test_repair_unknown_timetable_returns_404(async_client: AsyncClient):
    response = await async_client.post(f"/api/v1/timetable/{uuid.uuid4()}/repair", json={})

    assert response.status_code == 404


async def test_repair_rejects_out_of_range_retries(async_client: AsyncClient):
    response = await async_client.post(
        f"/api/v1/timetable/{uuid.uuid4()}/repair",
        json={"max_retries": 99},
    )

    assert response.status_code == 422


async def test_repair_rejects_unknown_body_fields(async_client: AsyncClient):
    response = await async_client.post(
        f"/api/v1/timetable/{uuid.uuid4()}/repair",
        json={"drop_all_constraints": True},
    )

    assert response.status_code == 422
