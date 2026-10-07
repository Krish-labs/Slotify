from fastapi import Request, status
from fastapi.responses import JSONResponse


class SchedulAIException(Exception):
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(SchedulAIException):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, "VALIDATION_ERROR")
        self.details = details or {}


class NotFoundError(SchedulAIException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(f"{resource} not found: {identifier}", "NOT_FOUND")
        self.resource = resource
        self.identifier = identifier


class ConflictError(SchedulAIException):
    def __init__(self, message: str):
        super().__init__(message, "CONFLICT")


class UnauthorizedError(SchedulAIException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, "UNAUTHORIZED")


class ForbiddenError(SchedulAIException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, "FORBIDDEN")


class SolverError(SchedulAIException):
    def __init__(self, message: str):
        super().__init__(message, "SOLVER_ERROR")


def schedulai_exception_handler(request: Request, exc: SchedulAIException) -> JSONResponse:
    status_code = {
        "VALIDATION_ERROR": status.HTTP_422_UNPROCESSABLE_CONTENT,
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "CONFLICT": status.HTTP_409_CONFLICT,
        "UNAUTHORIZED": status.HTTP_401_UNAUTHORIZED,
        "FORBIDDEN": status.HTTP_403_FORBIDDEN,
        "SOLVER_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    content = {
        "code": exc.code,
        "message": exc.message,
    }
    if hasattr(exc, "details") and exc.details:
        content["details"] = exc.details

    return JSONResponse(status_code=status_code, content=content)
