"""Background job runner: consumes timetable jobs from a Redis list.

Run with ``python -m app.workers.runner``. API code enqueues work with
``enqueue_generate`` and can poll ``get_result`` for the outcome.

Delivery is at-most-once: a job is removed from the queue when picked up, so a hard
crash mid-solve loses it (the caller sees no result and can re-enqueue).
"""

import asyncio
import json
import logging
import signal
import uuid
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import settings
from app.workers.timetable_worker import TimetableWorker

logger = logging.getLogger(__name__)

QUEUE_KEY = "schedulai:queue:timetable"
RESULT_KEY = "schedulai:result:{job_id}"
RESULT_TTL_SECONDS = 24 * 60 * 60
POLL_TIMEOUT_SECONDS = 5


async def enqueue_generate(
    redis: Redis, timetable_id: UUID, requested_by: UUID | None = None
) -> str:
    """Queue a full timetable generation; returns the job id."""
    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "type": "generate",
        "timetable_id": str(timetable_id),
        "requested_by": str(requested_by) if requested_by else None,
    }
    await redis.set(
        RESULT_KEY.format(job_id=job_id),
        json.dumps({"status": "queued"}),
        ex=RESULT_TTL_SECONDS,
    )
    await redis.rpush(QUEUE_KEY, json.dumps(payload))
    return job_id


async def enqueue_reoptimize(
    redis: Redis,
    timetable_id: UUID,
    change_data: dict,
    requested_by: UUID | None = None,
    job_id: str | None = None,
) -> str:
    """Queue exactly ONE reoptimization message for the durable job row.

    ``job_id`` must be the id of the already-committed ``timetable_jobs`` row so
    the worker claims that row. Callers must NOT push a second message for the
    same job: duplicate delivery would run the solve twice.
    """
    job_id = job_id or str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "type": "reoptimize",
        "timetable_id": str(timetable_id),
        "change_data": change_data,
        "requested_by": str(requested_by) if requested_by else None,
    }
    await redis.set(
        RESULT_KEY.format(job_id=job_id),
        json.dumps({"status": "queued"}),
        ex=RESULT_TTL_SECONDS,
    )
    await redis.rpush(QUEUE_KEY, json.dumps(payload))
    return job_id


def get_redis() -> Redis:
    """Single construction site for the queue connection."""
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_result(redis: Redis, job_id: str) -> dict | None:
    raw = await redis.get(RESULT_KEY.format(job_id=job_id))
    return json.loads(raw) if raw else None


async def process_job(payload: dict[str, Any], worker: TimetableWorker) -> dict:
    """Run one job and return its outcome. Never raises."""
    try:
        job_type = payload.get("type")
        if job_type == "generate":
            requested_by = payload.get("requested_by")
            result = await worker.generate_timetable(
                UUID(payload["timetable_id"]),
                requested_by=UUID(requested_by) if requested_by else None,
            )
        elif job_type == "reoptimize":
            result = await worker.reoptimize_timetable(
                UUID(payload["timetable_id"]),
                payload.get("change_data", {}),
                job_id=payload.get("job_id"),
            )
        else:
            result = {"error": f"Unknown job type: {job_type!r}"}
    except Exception as exc:
        logger.exception("Job %s crashed", payload.get("job_id"))
        result = {"error": f"Job crashed: {exc}"}

    return {"status": "failed" if "error" in result else "done", "result": result}


async def run_forever(
    redis: Redis, worker: TimetableWorker, stop: asyncio.Event | None = None
) -> None:
    stop = stop or asyncio.Event()
    logger.info("Worker listening on %s", QUEUE_KEY)

    while not stop.is_set():
        try:
            item = await redis.blpop([QUEUE_KEY], timeout=POLL_TIMEOUT_SECONDS)
        except RedisTimeoutError:
            # redis-py raises TimeoutError when a BLPOP poll expires instead
            # of returning None. That is normal idle behavior, not a
            # connection failure (those raise ConnectionError), so keep polling.
            logger.debug("Queue poll timed out, continuing to poll")
            continue
        if item is None:
            continue

        _, raw = item
        try:
            payload = json.loads(raw)
            job_id = payload["job_id"]
        except (ValueError, KeyError, TypeError):
            logger.error("Dropping malformed job: %r", raw)
            continue

        logger.info("Starting job %s (%s)", job_id, payload.get("type"))
        await redis.set(
            RESULT_KEY.format(job_id=job_id),
            json.dumps({"status": "running"}),
            ex=RESULT_TTL_SECONDS,
        )
        outcome = await process_job(payload, worker)
        await redis.set(
            RESULT_KEY.format(job_id=job_id),
            json.dumps(outcome, default=str),
            ex=RESULT_TTL_SECONDS,
        )
        logger.info("Finished job %s: %s", job_id, outcome["status"])

    logger.info("Worker stopped")


async def _main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    # Reconcile jobs abandoned by a previous worker crash before consuming.
    from app.database.connection import AsyncSessionLocal
    from app.workers.timetable_worker import reconcile_stale_jobs

    reaped = await reconcile_stale_jobs(AsyncSessionLocal)
    if reaped:
        logger.info("Reconciled %d stale RUNNING job(s) to FAILED", reaped)

    redis = None
    try:
        redis = get_redis()
        await run_forever(redis, TimetableWorker(), stop)
    finally:
        if redis is not None:
            close = getattr(redis, "aclose", None) or getattr(redis, "close", None)
            if close is not None:
                await close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(_main())


if __name__ == "__main__":
    main()
