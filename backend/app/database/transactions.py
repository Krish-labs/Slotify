"""Single transaction-ownership primitive for the whole application.

ARCHITECTURE RULE (see SKILL.md "Transaction ownership"):

    The use-case orchestrator (API handler or worker use-case) owns the
    transaction. It opens it with ``transaction(db)``, performs domain
    operations (services add/update/delete/flush/query only), writes audit and
    notification rows into the SAME transaction, and commits EXACTLY ONCE when
    the use case succeeds. A response is only produced after the commit.

Services and repositories MUST NOT call ``commit()``/``rollback()``. Workers
use the same primitive; their unit of work is one job use case.

Why a context manager instead of committing in ``get_db``: FastAPI dependency
teardown runs *after* the response has been sent, so a dependency-owned commit
would let the client observe a 2xx for state that later fails to commit. The
explicit ``async with transaction(db):`` block commits *before* the handler
returns, which makes success responses truthful by construction.
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def transaction(db: AsyncSession):
    """Own one unit of work: commit once on success, roll back on any failure.

    Usage in a use case (API handler or worker):

        async with transaction(db):
            ...mutations, audit, notifications...
        # only reached after commit; safe to build the response here
        return {...}

    On exception the transaction is rolled back and the exception propagates.
    """
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def end_read_transaction(db: AsyncSession) -> None:
    """Explicitly close the current read-only transaction.

    Used by long-running use cases (e.g. timetable generation) to release the
    database connection/locks before CPU-bound work (CP-SAT solving). The next
    statement on the session transparently begins a fresh transaction, which
    the use case then owns via :func:`transaction`.
    """
    await db.rollback()
