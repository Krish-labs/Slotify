from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "SchedulAI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-in-production"
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

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@schedulai.local"

    FRONTEND_URL: str = "http://localhost:5173"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        # In production, SECRET_KEY must be set and not use the development default
        if info.data.get("APP_ENV") == "production":
            if not v or v == "dev-secret-key-change-in-production":
                raise ValueError("SECRET_KEY must be set to a secure value in production")
            if len(v) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production")
        return v


settings = Settings()
