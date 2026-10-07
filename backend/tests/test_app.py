from fastapi.testclient import TestClient

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
