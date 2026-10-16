import asyncio

from fastapi.testclient import TestClient

from app.api import health
from app.main import app


def test_app_creation():
    """Test FastAPI application is created successfully"""
    assert app is not None
    assert app.title == "SchedulAI"
    assert app.version == "0.1.0"


def test_health_endpoint():
    """Test /api/v1/health endpoint returns correct response"""
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "SchedulAI"


def test_health_endpoint_structure():
    """Test health endpoint response has correct structure"""
    client = TestClient(app)
    response = client.get("/api/v1/health")
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert isinstance(data["status"], str)
    assert isinstance(data["service"], str)


def test_readiness_passes_when_required_dependencies_are_healthy(monkeypatch):
    async def healthy():
        return None

    monkeypatch.setattr(health, "_check_database", healthy)
    monkeypatch.setattr(health, "_check_redis", healthy)

    response = TestClient(app).get("/api/v1/readyz")

    assert response.status_code == 200
    assert response.json()["checks"] == {"postgres": "ok", "redis": "ok"}


def test_readiness_reports_unavailable_without_internal_error_details(monkeypatch):
    async def unavailable():
        raise RuntimeError("postgresql://user:secret@db.internal/production")

    async def healthy():
        return None

    monkeypatch.setattr(health, "_check_database", unavailable)
    monkeypatch.setattr(health, "_check_redis", healthy)

    response = TestClient(app).get("/api/v1/readyz")

    assert response.status_code == 503
    assert response.json()["checks"] == {"postgres": "unavailable", "redis": "ok"}
    assert "secret" not in response.text
    assert "db.internal" not in response.text


def test_readiness_times_out_and_keeps_liveness_healthy(monkeypatch):
    async def hangs():
        await asyncio.sleep(1)

    monkeypatch.setattr(health, "READINESS_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(health, "_check_database", hangs)
    monkeypatch.setattr(health, "_check_redis", hangs)

    client = TestClient(app)
    ready = client.get("/api/v1/readyz")
    alive = client.get("/api/v1/health")

    assert ready.status_code == 503
    assert ready.json()["checks"] == {"postgres": "timeout", "redis": "timeout"}
    assert alive.status_code == 200
