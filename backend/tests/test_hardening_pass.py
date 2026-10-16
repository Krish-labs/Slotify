"""Hardening-pass regressions: gaps demonstrated during production review."""

from uuid import UUID

import pytest
from fastapi import HTTPException

from app.api.timetable import _parse_uuid_or_404, _temp_export_path
from app.services import ai_constraint_service as ai_service
from app.services.ai_constraint_service import suggest_repair_adjustments


def test_parse_uuid_rejects_malformed_as_404_not_500():
    with pytest.raises(HTTPException) as exc:
        _parse_uuid_or_404("not-a-uuid", "Timetable")
    assert exc.value.status_code == 404

    parsed = _parse_uuid_or_404("12345678-1234-5678-1234-567812345678", "Timetable")
    assert isinstance(parsed, UUID)


def test_temp_export_paths_are_unique_and_suffixed():
    timetable_id = UUID("12345678-1234-5678-1234-567812345678")
    first = _temp_export_path("export_class", timetable_id)
    second = _temp_export_path("export_class", timetable_id)
    assert first != second
    assert first.endswith(".xlsx")
    assert "export_class_" in first


@pytest.mark.asyncio
async def test_suggest_repair_falls_back_on_non_dict_llm_json(monkeypatch):
    """LLM returning a JSON list/str must not raise AttributeError (500)."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")

    async def _fake_list(user_content: str, system_prompt: str):
        return ["not", "a", "dict"]  # type: ignore[return-value]

    monkeypatch.setattr(ai_service, "_call_json", _fake_list)
    result = await suggest_repair_adjustments(["Faculty conflict"])
    assert result["source"] == "deterministic"
    assert result["candidates"]
