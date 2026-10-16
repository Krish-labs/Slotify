"""P0 production guards: database, Redis, and CORS fail-closed behavior."""

import pytest

from app.core.config import Settings
from tests.test_config import _apply_prod_env


def test_production_rejects_development_database_password(monkeypatch):
    _apply_prod_env(
        monkeypatch,
        DATABASE_URL="postgresql+asyncpg://schedulai:schedulai@postgres:5432/schedulai",
    )
    with pytest.raises(Exception, match="must not use the development database password"):
        Settings()


def test_production_accepts_distinct_database_password(monkeypatch):
    _apply_prod_env(monkeypatch)
    assert "schedulai:schedulai" not in Settings().DATABASE_URL


def test_production_rejects_redis_without_password(monkeypatch):
    _apply_prod_env(monkeypatch, REDIS_URL="redis://redis:6379/0")
    with pytest.raises(Exception, match="REDIS_URL must include a password"):
        Settings()


def test_production_accepts_redis_with_password(monkeypatch):
    _apply_prod_env(monkeypatch)
    assert Settings().REDIS_URL == "redis://:prodredispass@redis:6379/0"


def test_production_rejects_development_cors_origins(monkeypatch):
    _apply_prod_env(
        monkeypatch, API_CORS_ORIGINS='["http://localhost:5173","http://localhost:3000"]'
    )
    with pytest.raises(Exception, match="development defaults"):
        Settings()


def test_production_rejects_empty_cors_origins(monkeypatch):
    _apply_prod_env(monkeypatch, API_CORS_ORIGINS="[]")
    with pytest.raises(Exception, match="must list trusted origins"):
        Settings()


def test_wildcard_cors_origin_rejected_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_CORS_ORIGINS", '["https://example.edu","*"]')
    with pytest.raises(Exception, match='must not contain "\\*"'):
        Settings(_env_file=None)


def test_explicit_cors_origins_accepted_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("API_CORS_ORIGINS", '["https://timetable.example.edu"]')
    assert Settings(_env_file=None).API_CORS_ORIGINS == ["https://timetable.example.edu"]
