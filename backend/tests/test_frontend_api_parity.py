"""Every endpoint the frontend calls must exist on the backend.

A method mismatch (frontend ``PATCH`` vs backend ``POST``) surfaces only at
runtime as 405, which no backend-only test can see. This parses
``frontend/src/api/endpoints.ts`` and checks each call against the FastAPI
route table, so the failure shows up in CI instead of in the browser.
"""

import re
from pathlib import Path

import pytest

import app.main  # noqa: F401  (registers every router)

FRONTEND_ENDPOINTS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "endpoints.ts"
)

_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
_CALL_RE = re.compile(
    r"""apiClient\.(get|post|put|patch|delete)(?:<[^>]*>)?\s*\(\s*(`[^`]+`|'[^']+'|"[^"]+")"""
)


def _normalise(path: str) -> str:
    path = path.split("?")[0]
    path = re.sub(r"\$\{[^}]+\}", "{x}", path)
    path = re.sub(r"\{[^}]+\}", "{x}", path)
    if not path.startswith("/"):
        path = "/" + path
    if not path.startswith("/api/"):
        path = "/api/v1" + path
    # the trailing slash is significant: "/timetable" against a POST-only route
    # answers 405 at runtime, which rstripping the slash would hide here.
    return path


def _backend_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for path, operations in app.main.app.openapi()["paths"].items():
        for method in operations:
            if method.upper() in _METHODS:
                routes.add((method.upper(), _normalise(path)))
    return routes


def _frontend_calls() -> list[tuple[str, str]]:
    if not FRONTEND_ENDPOINTS.is_file():
        pytest.skip(f"frontend API layer not present at {FRONTEND_ENDPOINTS}")
    text = FRONTEND_ENDPOINTS.read_text()
    return [
        (match.group(1).upper(), _normalise(match.group(2)[1:-1]))
        for match in _CALL_RE.finditer(text)
    ]


def test_every_frontend_api_call_has_a_matching_backend_route() -> None:
    calls = _frontend_calls()
    assert calls, "expected to find apiClient calls in the frontend API layer"

    routes = _backend_routes()
    broken: list[str] = []
    for method, path in calls:
        if (method, path) in routes:
            continue
        alternatives = sorted(m for m, p in routes if p == path)
        broken.append(
            f"{method} {path}"
            + (f" (backend exposes: {', '.join(alternatives)})" if alternatives else "")
        )

    assert not broken, "frontend calls endpoints the backend does not expose:\n" + "\n".join(
        f"  {entry}" for entry in broken
    )
