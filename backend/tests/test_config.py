import pytest

from app.core.config import _DEV_SECRET_MARKER, Settings, settings

VALID_PROD_ENV = {
    "APP_ENV": "production",
    "SECRET_KEY": "a-very-secure-production-key-that-is-long-enough-for-use",
    "DATABASE_URL": "postgresql+asyncpg://produser:prodpass123@postgres:5432/schedulai",
    "REDIS_URL": "redis://:prodredispass@redis:6379/0",
    "API_CORS_ORIGINS": '["https://timetable.example.edu"]',
    "AUTH_STATE_BACKEND": "redis",
}


def _apply_prod_env(monkeypatch, **overrides):
    env = dict(VALID_PROD_ENV)
    env.update(overrides)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_settings_loading(monkeypatch):
    """Test configuration loads from environment with defaults"""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings()
    assert s.APP_NAME == "SchedulAI"
    assert s.APP_ENV == "development"
    assert s.DEBUG is True
    assert s.SECRET_KEY == _DEV_SECRET_MARKER
    assert s.DATABASE_URL == "postgresql+asyncpg://schedulai:schedulai@localhost:5432/schedulai"
    assert s.API_CORS_ORIGINS == ["http://localhost:5173", "http://localhost:3000"]


def test_settings_override_from_env(monkeypatch):
    """Test configuration can be overridden by environment variables"""
    monkeypatch.setenv("APP_NAME", "TestApp")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

    s = Settings()
    assert s.APP_NAME == "TestApp"
    assert s.DEBUG is False
    assert s.SECRET_KEY == "test-secret"
    assert s.DATABASE_URL == "postgresql+asyncpg://test:test@localhost:5432/test"


def test_global_settings_instance():
    """Test global settings instance is accessible"""
    assert settings is not None
    assert settings.APP_NAME == "SchedulAI"


def test_production_rejects_default_secret(monkeypatch):
    """Production must reject the development secret marker."""
    _apply_prod_env(monkeypatch, SECRET_KEY=_DEV_SECRET_MARKER)
    with pytest.raises(Exception, match="SECRET_KEY must be set to a secure value"):
        Settings()


def test_production_rejects_unset_secret(monkeypatch):
    """Production must not silently fall back to a dev key when SECRET_KEY is unset."""
    _apply_prod_env(monkeypatch)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(Exception, match="SECRET_KEY must be set to a secure value"):
        Settings(_env_file=None)


def test_development_fills_marker_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    assert Settings(_env_file=None).SECRET_KEY == _DEV_SECRET_MARKER


def test_production_rejects_empty_secret(monkeypatch):
    """Production must reject an empty secret key."""
    _apply_prod_env(monkeypatch, SECRET_KEY="")
    with pytest.raises(Exception, match="SECRET_KEY must be set to a secure value"):
        Settings()


def test_production_rejects_short_secret(monkeypatch):
    """Production must reject a secret key shorter than 32 characters."""
    _apply_prod_env(monkeypatch, SECRET_KEY="too-short-key")
    with pytest.raises(Exception, match="SECRET_KEY must be at least 32 characters"):
        Settings()


def test_production_accepts_valid_secret(monkeypatch):
    """Production must accept a secret key of 32+ characters."""
    _apply_prod_env(monkeypatch)
    s = Settings()
    assert s.SECRET_KEY == "a-very-secure-production-key-that-is-long-enough-for-use"
    assert s.APP_ENV == "production"


def test_production_forces_debug_off(monkeypatch):
    """Production coerces DEBUG to False so SQL logging stays off."""
    _apply_prod_env(monkeypatch, DEBUG="true")
    assert Settings().DEBUG is False


def test_production_rejects_auto_auth_state_backend(monkeypatch):
    """Production must share revocation/throttle state via Redis."""
    _apply_prod_env(monkeypatch, AUTH_STATE_BACKEND="auto")
    with pytest.raises(Exception, match='AUTH_STATE_BACKEND must be "redis"'):
        Settings()


def test_production_accepts_redis_auth_state_backend(monkeypatch):
    _apply_prod_env(monkeypatch, AUTH_STATE_BACKEND="redis")
    assert Settings().AUTH_STATE_BACKEND == "redis"


def test_production_rejects_local_auth_disabled(monkeypatch):
    _apply_prod_env(monkeypatch, LOCAL_AUTH_DISABLED="true")
    with pytest.raises(Exception, match="LOCAL_AUTH_DISABLED is only allowed in development"):
        Settings()
