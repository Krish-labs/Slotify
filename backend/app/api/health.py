import asyncio
from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter()
READINESS_TIMEOUT_SECONDS = 2.0


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}


async def _check_database() -> None:
    from sqlalchemy import text

    from app.database.connection import engine

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _check_redis() -> None:
    from redis.asyncio import Redis

    client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=READINESS_TIMEOUT_SECONDS,
        socket_timeout=READINESS_TIMEOUT_SECONDS,
    )
    try:
        await client.ping()
    finally:
        await client.close()


async def _probe_result(probe: Callable[[], Awaitable[None]]) -> str:
    try:
        await asyncio.wait_for(probe(), timeout=READINESS_TIMEOUT_SECONDS)
        return "ok"
    except TimeoutError:
        return "timeout"
    except Exception:
        # Do not return exception text, which can contain hosts or URLs.
        return "unavailable"


@router.get("/readyz")
async def readiness_check():
    """Check the API's required stateful dependencies within a fixed bound."""
    postgres, redis = await asyncio.gather(
        _probe_result(_check_database),
        _probe_result(_check_redis),
    )
    checks = {"postgres": postgres, "redis": redis}

    ready = all(result == "ok" for result in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "service": settings.APP_NAME,
            "checks": checks,
        },
    )
