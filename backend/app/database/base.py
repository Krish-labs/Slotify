import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declared_attr

from app.database.connection import Base


def _utc_now() -> datetime:
    """Project-wide timestamp policy: timezone-aware UTC, never naive."""
    return datetime.now(UTC)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # ``onupdate`` MUST be a Python-side callable. A SQL expression
    # (``func.now()``) leaves the value unknown to the client, so SQLAlchemy
    # expires ``updated_at`` on flush; any later sync-context access (FastAPI
    # response serialization, plain attribute reads) then raises
    # MissingGreenlet instead of returning the timestamp. A callable writes the
    # value into the instance, so it stays loaded and is identical on
    # PostgreSQL and SQLite.
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=_utc_now,
        nullable=False,
    )


class UUIDMixin:
    @declared_attr
    def id(cls):
        return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class BaseModel(Base, UUIDMixin, TimestampMixin):
    __abstract__ = True
