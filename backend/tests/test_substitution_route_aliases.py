"""Substitution URLs are served by one router under two prefixes.

The UI calls ``/api/v1/leave/substitutions`` without a trailing slash. The
original router only registered ``/substitutions/``, so the collection URL was
swallowed by ``/leave/{leave_id}``: listing returned 422 and creating returned
405, i.e. the substitution list and create flow were dead in the UI. These
tests pin both prefixes, both slash spellings, and the fact that there is only
one implementation behind them.
"""

import uuid

import pytest
from fastapi.routing import APIRoute

from app.api import leave as leave_module
from app.api import substitutions as substitutions_module
from app.main import app

COLLECTION_PATHS = (
    "/api/v1/leave/substitutions",
    "/api/v1/leave/substitutions/",
    "/api/v1/substitutions",
    "/api/v1/substitutions/",
)


def _all_api_routes():
    routes = []
    for outer in app.routes:
        router = getattr(outer, "original_router", None)
        if router is None:
            continue
        for route in getattr(router, "routes", ()):
            if isinstance(route, APIRoute):
                routes.append(route)
    return routes


def test_substitution_handlers_exist_only_once():
    """A copy pasted back into leave.py would drift from the shared router."""
    routes = _all_api_routes()
    substitution_routes = [
        r for r in routes if "substitution" in r.path or "substitution" in r.name
    ]
    assert substitution_routes, "no substitution routes registered"
    assert all(r.endpoint.__module__ == substitutions_module.__name__ for r in substitution_routes)
    assert not [
        r
        for r in routes
        if r.endpoint.__module__ == leave_module.__name__ and "substitution" in r.name
    ]


def test_both_prefixes_and_spellings_are_documented():
    paths = app.openapi()["paths"]
    for path in COLLECTION_PATHS:
        assert "get" in paths[path], path
    assert "post" in paths["/api/v1/leave/substitutions"]
    assert "post" in paths["/api/v1/substitutions"]


@pytest.mark.asyncio
async def test_substitution_list_is_reachable_on_every_spelling(async_client):
    for path in COLLECTION_PATHS:
        response = await async_client.get(path)
        assert response.status_code == 200, f"{path}: {response.text}"
        assert response.json() == {"substitutions": []}


@pytest.mark.asyncio
async def test_substitution_create_reaches_the_handler_without_a_trailing_slash(async_client):
    """No trailing slash used to mean 405; the handler must run instead."""
    for path in ("/api/v1/leave/substitutions", "/api/v1/substitutions"):
        response = await async_client.post(path, json={})
        assert response.status_code == 422, f"{path}: {response.text}"
        detail = response.json()["detail"]
        assert detail[0]["loc"][0] == "body", f"{path}: {detail}"


@pytest.mark.asyncio
async def test_leave_routes_still_win_for_uuid_paths(async_client):
    response = await async_client.get(f"/api/v1/leave/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Leave not found"

    response = await async_client.get("/api/v1/leave/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "leave_id"]

    response = await async_client.post(f"/api/v1/leave/{uuid.uuid4()}/approve")
    assert response.status_code == 404
    assert response.json()["detail"] == "Leave not found"


@pytest.mark.asyncio
async def test_substitution_detail_still_resolves_to_substitutions(async_client):
    response = await async_client.get(f"/api/v1/leave/substitutions/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Substitution not found"
