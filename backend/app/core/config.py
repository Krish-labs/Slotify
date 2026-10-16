from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_JWT_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})

# Development-only fallback. It is never valid in production: the production
# validator below rejects it explicitly, so a forgotten SECRET_KEY fails
# startup instead of signing tokens with a publicly known key.
_DEV_SECRET_MARKER = "dev-only-local-insecure-do-not-use-in-production"

# Exact development defaults. Production must not silently inherit any of
# these; the production validator rejects them so a missing prod env file
# fails startup instead of booting with development credentials.
_DEV_DATABASE_PASSWORD = "schedulai"
_DEV_CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "SchedulAI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    # No default: development fills in _DEV_SECRET_MARKER, production must
    # provide a real value or startup fails (see validate_production_safety).
    SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DATABASE_URL: str = "postgresql+asyncpg://schedulai:schedulai@localhost:5432/schedulai"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    REDIS_URL: str = "redis://localhost:6379/0"

    API_CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    MAX_UPLOAD_SIZE_MB: int = 50
    UPLOAD_DIR: str = "./uploads"

    SOLVER_TIME_LIMIT_SECONDS: int = 300
    SOLVER_NUM_WORKERS: int = 8

    AI_ENABLED: bool = False
    AI_PROVIDER: str = "openai"
    AI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4"
    AI_API_BASE_URL: str = "https://api.openai.com/v1"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@schedulai.local"

    FRONTEND_URL: str = "http://localhost:5173"

    # Authentication hardening (all configurable without code changes).
    PASSWORD_MIN_LENGTH: int = 12
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    # "auto": Redis when reachable, process-local fallback with a warning.
    # "redis": require shared Redis state (multi-worker production).
    # "memory": process-local state (tests, single-process dev without Redis).
    AUTH_STATE_BACKEND: str = "auto"

    # Local prototype switch. This bypasses token and RBAC checks only in
    # development; persistence still needs an existing active users row.
    LOCAL_AUTH_DISABLED: bool = False
    LOCAL_AUTH_USER_EMAIL: str | None = None

    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        if v not in _ALLOWED_JWT_ALGORITHMS:
            raise ValueError(f"ALGORITHM must be one of {sorted(_ALLOWED_JWT_ALGORITHMS)}")
        return v

    @field_validator("AUTH_STATE_BACKEND")
    @classmethod
    def validate_auth_state_backend(cls, v: str) -> str:
        if v not in ("auto", "redis", "memory"):
            raise ValueError('AUTH_STATE_BACKEND must be one of "auto", "redis", "memory"')
        return v

    @field_validator("API_CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: list[str]) -> list[str]:
        # A wildcard origin combined with credentials lets any site read
        # authenticated responses. Reject it in every environment.
        if "*" in v:
            raise ValueError('API_CORS_ORIGINS must not contain "*" when credentials are enabled')
        return v

    @model_validator(mode="after")
    def validate_environment_safety(self):
        if self.LOCAL_AUTH_DISABLED and self.APP_ENV != "development":
            raise ValueError("LOCAL_AUTH_DISABLED is only allowed in development")

        if self.APP_ENV != "production":
            if not self.SECRET_KEY:
                self.SECRET_KEY = _DEV_SECRET_MARKER
            return self

        # Production: fail startup on missing or insecure secrets. Every
        # check below must pass or the process refuses to boot.
        if not self.SECRET_KEY or self.SECRET_KEY == _DEV_SECRET_MARKER:
            raise ValueError(
                "SECRET_KEY must be set to a secure value in production "
                "(32+ random characters via environment or env file)"
            )
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")

        password = _database_password(self.DATABASE_URL)
        if not password or password == _DEV_DATABASE_PASSWORD:
            raise ValueError(
                "DATABASE_URL must not use the development database password in production"
            )

        if not _redis_url_has_password(self.REDIS_URL):
            raise ValueError(
                "REDIS_URL must include a password in production "
                "(e.g. redis://:PASSWORD@redis:6379/0)"
            )

        if not self.API_CORS_ORIGINS:
            raise ValueError("API_CORS_ORIGINS must list trusted origins in production")
        if self.API_CORS_ORIGINS == _DEV_CORS_ORIGINS:
            raise ValueError(
                "API_CORS_ORIGINS still holds the development defaults; "
                "configure explicit trusted origins for production"
            )

        # Multi-worker production must share revocation/throttle state. "auto"
        # permanently degrades to per-process memory after one Redis blip, so a
        # revoked token stays valid on other workers until restart.
        if self.AUTH_STATE_BACKEND != "redis":
            raise ValueError(
                'AUTH_STATE_BACKEND must be "redis" in production '
                "(shared revocation and throttling across workers)"
            )

        # Fail safe: never serve production with DEBUG, even if the env
        # forgets DEBUG=false. This also silences SQLAlchemy query logging,
        # which follows settings.DEBUG in database/connection.py.
        self.DEBUG = False
        return self


def _database_password(database_url: str) -> str | None:
    try:
        return urlparse(database_url).password
    except Exception:
        return None


def _redis_url_has_password(redis_url: str) -> bool:
    try:
        return bool(urlparse(redis_url).password)
    except Exception:
        return False


settings = Settings()
