from unittest.mock import MagicMock

from fastapi import Request

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    SchedulAIException,
    SolverError,
    UnauthorizedError,
    ValidationError,
    schedulai_exception_handler,
)


def test_exception_classes():
    """Test custom exception classes can be instantiated"""
    exc = SchedulAIException("test message", "TEST_CODE")
    assert str(exc) == "test message"
    assert exc.code == "TEST_CODE"

    val_exc = ValidationError("validation failed", {"field": "error"})
    assert val_exc.code == "VALIDATION_ERROR"
    assert val_exc.details == {"field": "error"}

    not_found = NotFoundError("User", "123")
    assert not_found.code == "NOT_FOUND"
    assert "User not found: 123" in str(not_found)


def test_exception_handler_mapping():
    """Test exception handler returns correct status codes"""
    mock_request = MagicMock(spec=Request)

    # Test ValidationError -> 422
    exc = ValidationError("test")
    response = schedulai_exception_handler(mock_request, exc)
    assert response.status_code == 422

    # Test NotFoundError -> 404
    exc = NotFoundError("User", "123")
    response = schedulai_exception_handler(mock_request, exc)
    assert response.status_code == 404

    # Test ConflictError -> 409
    exc = ConflictError("conflict")
    response = schedulai_exception_handler(mock_request, exc)
    assert response.status_code == 409

    # Test UnauthorizedError -> 401
    exc = UnauthorizedError()
    response = schedulai_exception_handler(mock_request, exc)
    assert response.status_code == 401

    # Test ForbiddenError -> 403
    exc = ForbiddenError()
    response = schedulai_exception_handler(mock_request, exc)
    assert response.status_code == 403

    # Test SolverError -> 500
    exc = SolverError("solver failed")
    response = schedulai_exception_handler(mock_request, exc)
    assert response.status_code == 500


def test_exception_handler_response_format():
    """Test exception handler returns consistent response format"""
    mock_request = MagicMock(spec=Request)
    exc = ValidationError("validation failed", {"field": "name", "error": "required"})
    response = schedulai_exception_handler(mock_request, exc)

    assert response.status_code == 422
    import json

    detail = json.loads(response.body)
    assert detail["code"] == "VALIDATION_ERROR"
    assert detail["message"] == "validation failed"
    assert detail["details"]["field"] == "name"
    assert detail["details"]["error"] == "required"
