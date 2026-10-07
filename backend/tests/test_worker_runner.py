"""Queue runner tests with an in-memory stand-in for Redis."""

import asyncio
import json
import uuid

from redis.exceptions import TimeoutError as RedisTimeoutError

from app.workers import runner


class FakeRedis:
    def __init__(self):
        self.lists: dict[str, list[str]] = {}
        self.kv: dict[str, str] = {}

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def blpop(self, keys, timeout=0):
        for key in keys:
            if self.lists.get(key):
                return key, self.lists[key].pop(0)
        await asyncio.sleep(0)
        return None

    async def set(self, key, value, ex=None):
        self.kv[key] = value

    async def get(self, key):
        return self.kv.get(key)


class FakeWorker:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.calls = result or {"success": True}, exc, []

    async def generate_timetable(self, timetable_id, requested_by=None):
        self.calls.append((timetable_id, requested_by))
        if self.exc:
            raise self.exc
        return self.result

    async def reoptimize_timetable(self, timetable_id, change_data):
        return {"error": "Reoptimization not yet implemented"}


async def _drain(redis, worker):
    """Run the loop until the queue is empty."""
    stop = asyncio.Event()
    task = asyncio.create_task(runner.run_forever(redis, worker, stop))
    while redis.lists.get(runner.QUEUE_KEY):
        await asyncio.sleep(0)
    await asyncio.sleep(0.01)
    stop.set()
    await task


async def test_enqueue_marks_job_queued_and_pushes_payload():
    redis = FakeRedis()
    tt, user = uuid.uuid4(), uuid.uuid4()

    job_id = await runner.enqueue_generate(redis, tt, user)

    assert await runner.get_result(redis, job_id) == {"status": "queued"}
    payload = json.loads(redis.lists[runner.QUEUE_KEY][0])
    assert payload["timetable_id"] == str(tt)
    assert payload["requested_by"] == str(user)


async def test_job_runs_and_result_is_stored():
    redis, worker = FakeRedis(), FakeWorker({"success": True, "entries_count": 7})
    tt = uuid.uuid4()
    job_id = await runner.enqueue_generate(redis, tt)

    await _drain(redis, worker)

    assert worker.calls == [(tt, None)]
    assert await runner.get_result(redis, job_id) == {
        "status": "done",
        "result": {"success": True, "entries_count": 7},
    }


async def test_worker_error_result_marks_job_failed():
    redis, worker = FakeRedis(), FakeWorker({"error": "Solver found no timetable"})
    job_id = await runner.enqueue_generate(redis, uuid.uuid4())

    await _drain(redis, worker)

    result = await runner.get_result(redis, job_id)
    assert result["status"] == "failed"
    assert "Solver" in result["result"]["error"]


async def test_crashing_job_does_not_kill_the_loop():
    redis, worker = FakeRedis(), FakeWorker(exc=RuntimeError("boom"))
    first = await runner.enqueue_generate(redis, uuid.uuid4())
    second = await runner.enqueue_generate(redis, uuid.uuid4())

    await _drain(redis, worker)

    assert len(worker.calls) == 2
    for job_id in (first, second):
        assert (await runner.get_result(redis, job_id))["status"] == "failed"


async def test_blpop_timeout_does_not_kill_the_loop():
    """A BLPOP poll timeout (redis-py raises TimeoutError) must not stop polling."""

    class FlakyRedis(FakeRedis):
        def __init__(self):
            super().__init__()
            self.timeouts = 0

        async def blpop(self, keys, timeout=0):
            if self.timeouts < 2:
                self.timeouts += 1
                raise RedisTimeoutError("Timeout reading from redis")
            return await super().blpop(keys, timeout)

    redis, worker = FlakyRedis(), FakeWorker({"success": True})
    job_id = await runner.enqueue_generate(redis, uuid.uuid4())

    await _drain(redis, worker)

    assert redis.timeouts == 2
    assert len(worker.calls) == 1
    assert (await runner.get_result(redis, job_id))["status"] == "done"


async def test_malformed_and_unknown_jobs_are_handled():
    redis, worker = FakeRedis(), FakeWorker()
    await redis.rpush(runner.QUEUE_KEY, "not json")
    await redis.rpush(runner.QUEUE_KEY, json.dumps({"job_id": "j1", "type": "mystery"}))

    await _drain(redis, worker)

    assert worker.calls == []
    result = await runner.get_result(redis, "j1")
    assert result["status"] == "failed"
    assert "Unknown job type" in result["result"]["error"]
