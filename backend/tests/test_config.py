import pytest

from app.core.config import Settings, settings


def test_settings_loading(monkeypatch):
    """Test configuration loads from environment with defaults"""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings()
    assert s.APP_NAME == "SchedulAI"
    assert s.APP_ENV == "development"
    assert s.DEBUG is True
    assert s.SECRET_KEY == "dev-secret-key-change-in-production"
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
    """Production must reject the default dev secret key."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-key-change-in-production")
    with pytest.raises(Exception, match="SECRET_KEY must be set to a secure value"):
        Settings()


def test_production_rejects_unset_secret(monkeypatch):
    """Production must not silently fall back to the default dev key when SECRET_KEY is unset."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(Exception, match="SECRET_KEY must be set to a secure value"):
        Settings(_env_file=None)


def test_development_allows_default_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    assert Settings(_env_file=None).SECRET_KEY == "dev-secret-key-change-in-production"


def test_production_rejects_empty_secret(monkeypatch):
    """Production must reject an empty secret key."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "")
    with pytest.raises(Exception, match="SECRET_KEY must be set to a secure value"):
        Settings()


def test_production_rejects_short_secret(monkeypatch):
    """Production must reject a secret key shorter than 32 characters."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "too-short-key")
    with pytest.raises(Exception, match="SECRET_KEY must be at least 32 characters"):
        Settings()


def test_production_accepts_valid_secret(monkeypatch):
    """Production must accept a secret key of 32+ characters."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-very-secure-production-key-that-is-long-enough-for-use")
    s = Settings()
    assert s.SECRET_KEY == "a-very-secure-production-key-that-is-long-enough-for-use"
    assert s.APP_ENV == "production"
