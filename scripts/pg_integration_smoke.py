"""API-level integration smoke against real Postgres (asyncpg).

Runs the real FastAPI app (no test fixtures, no SQLite NullPool) against a
Postgres database whose schema is rebuilt from alembic on every run, then
exercises the leave -> approve -> substitution flow, audit writes, notifications,
permission gates and enum/typed column inserts.

DESTRUCTIVE: the target database's ``public`` schema is dropped and recreated.
It must only ever be pointed at a disposable database. Pass
``--allow-destructive`` to confirm.

Usage:
    DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/disposable_db \
        backend/.venv/bin/python scripts/pg_integration_smoke.py --allow-destructive

Exit codes: 0 = all checks passed, 1 = at least one check failed, 2 = misconfigured.
"""

import asyncio
import os
import subprocess
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from uuid import UUID

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

PG_URL = os.environ.get("DATABASE_URL", "")
if not PG_URL.startswith("postgresql"):
    print("DATABASE_URL must be set to a postgresql+asyncpg:// URL", file=sys.stderr)
    raise SystemExit(2)
if "--allow-destructive" not in sys.argv:
    print(
        "refusing to run: this script drops and recreates the target schema.\n"
        "Re-run with --allow-destructive against a disposable database.",
        file=sys.stderr,
    )
    raise SystemExit(2)

os.environ.setdefault("SECRET_KEY", "pg-smoke-verify-secret")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.main import app

ADMIN_EMAIL, ADMIN_PASSWORD = "admin@verify.local", "Verify!Pass123"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f" | {detail}" if detail else ""), flush=True)


async def reset_schema() -> None:
    """Rebuild the schema from alembic so every run starts identical."""
    from app.database.connection import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text("DROP SCHEMA public CASCADE"))
        await db.execute(text("CREATE SCHEMA public"))
        await db.commit()
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": PG_URL},
    )
    check("alembic upgrade head on fresh PG schema", proc.returncode == 0,
          (proc.stdout + proc.stderr).strip()[-200:])


async def seed_admin() -> str:
    from app.database.connection import AsyncSessionLocal
    from app.database.models.user import User
    from app.database.seed import seed

    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        ).scalar_one_or_none()
        if existing is None:
            await seed(db, admin_email=ADMIN_EMAIL, admin_password=ADMIN_PASSWORD)
            existing = (
                await db.execute(select(User).where(User.email == ADMIN_EMAIL))
            ).scalar_one()
    return str(existing.id)


async def seed_domain_data(admin_id: str) -> dict:
    """Rows the leave-approval flow needs, committed independently of the API.

    Both faculties are linked to the admin's user account so the notification
    path (which requires a linked ``Faculty.user_id``) is actually exercised.
    """
    from app.database.connection import AsyncSessionLocal
    from app.database.models import (
        AcademicTerm,
        Class,
        Faculty,
        Resource,
        Section,
        Subject,
        TeachingAssignment,
        TimeSlot,
        Timetable,
        TimetableEntry,
        TimetableTemplate,
        TimetableVersion,
    )
    from app.database.models.teaching_assignment import SessionType

    async with AsyncSessionLocal() as db:
        template = TimetableTemplate(name="T-pg", academic_year="2030-31")
        cls = Class(name="SE", year=2, branch="E&TC", academic_year="2030-31", strength=40)
        subject = Subject(code="EC1", name="Signals", subject_type="BOTH", semester=1)
        original = Faculty(
            employee_id="F-PG-1", first_name="Ada", last_name="Lovelace",
            email="ada.pg@example.com", department="E&TC", designation="Professor",
            user_id=admin_id,
        )
        from app.core.security import get_password_hash
        from app.database.models.user import User

        sub_user = (
            await db.execute(select(User).where(User.email == "sub.pg@example.com"))
        ).scalar_one_or_none()
        if sub_user is None:
            sub_user = User(
                email="sub.pg@example.com",
                hashed_password=get_password_hash("Sub!Pass123"),
                full_name="Alan Turing",
                is_active=True,
                is_superuser=False,
            )
            db.add(sub_user)
            await db.flush()

        substitute = Faculty(
            employee_id="F-PG-2", first_name="Alan", last_name="Turing",
            email="alan.pg@example.com", department="E&TC", designation="Professor",
            user_id=sub_user.id,
        )
        db.add_all([template, cls, subject, original, substitute])
        await db.flush()

        slot = TimeSlot(
            template_id=template.id, day_of_week=0, period_number=1,
            start_time=time(9, 0), end_time=time(9, 50),
            slot_type="TEACHING", shift="MORNING",
        )
        db.add(slot)
        await db.flush()

        section = Section(class_id=cls.id, name="A", strength=40)
        db.add(section)
        await db.flush()

        term = AcademicTerm(
            name="Sem I", academic_year="2030-31", semester=1,
            start_date=date(2030, 6, 1), end_date=date(2030, 12, 1), is_current=True,
        )
        resource = Resource(name="R-101-PG", resource_type="CLASSROOM", capacity=60)
        db.add_all([term, resource])
        await db.flush()

        db.add(
            TeachingAssignment(
                faculty_id=substitute.id, academic_term_id=term.id,
                subject_id=subject.id, section_id=section.id,
                session_type=SessionType.LECTURE, hours_per_week=1,
                session_duration=1, is_active=True,
            )
        )
        timetable = Timetable(
            name="TT-PG-2030-31", template_id=template.id,
            academic_year="2030-31", semester=1, status="GENERATED",
        )
        db.add(timetable)
        await db.flush()

        version = TimetableVersion(
            timetable_id=timetable.id, version_number=1, status="VALIDATED",
            created_by=admin_id, change_type="FULL_REGENERATION",
        )
        db.add(version)
        await db.flush()

        db.add(
            TimetableEntry(
                version_id=version.id, faculty_id=original.id, subject_id=subject.id,
                section_id=section.id, resource_id=resource.id, time_slot_id=slot.id,
                day_of_week=date(2030, 7, 1).weekday(), period_number=1,
                session_type="LECTURE", session_duration=1,
            )
        )
        await db.commit()

        return {
            "template": template, "class": cls, "subject": subject, "slot": slot,
            "original": original, "substitute": substitute, "section": section,
            "term": term, "timetable": timetable,
        }


async def run_api(seed: dict) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://pgverify") as client:
        r = await client.get("/api/v1/batches")
        check("unauthenticated request -> 401", r.status_code == 401, f"{r.status_code}")

        r = await client.post(
            "/api/v1/auth/login",
            data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        check("login -> token", r.status_code == 200 and "access_token" in r.json(), r.text[:120])
        if r.status_code != 200:
            return
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await client.get("/api/v1/batches", headers=h)
        check("authenticated list -> 200", r.status_code == 200, f"{r.status_code}")

        r = await client.post(
            "/api/v1/academic-terms",
            headers=h,
            json={
                "name": "Sem PG", "academic_year": "2030-31", "semester": 2,
                "start_date": "2030-01-01", "end_date": "2030-05-31", "is_current": False,
            },
        )
        check("create academic term -> 201", r.status_code == 201, r.text[:160])

        r = await client.post(
            "/api/v1/leave/",
            headers=h,
            json={
                "faculty_id": str(seed["original"].id),
                "leave_type": "SICK",
                "start_date": "2030-07-01",
                "end_date": "2030-07-02",
                "reason": "flu",
                "status": "APPROVED",
                "approved_by": "00000000-0000-0000-0000-000000000001",
                "id": "00000000-0000-0000-0000-000000000002",
            },
        )
        check("leave create ignores spoofed lifecycle fields",
              r.status_code == 201 and r.json().get("status") == "PENDING"
              and r.json().get("approved_by") is None, f"{r.status_code} {r.text[:200]}")
        if r.status_code != 201:
            return
        leave_id = r.json()["id"]

        r = await client.post(f"/api/v1/leave/{leave_id}/approve", headers=h)
        check("approve leave -> 200 APPROVED",
              r.status_code == 200 and r.json().get("status") == "APPROVED",
              f"{r.status_code} {r.text[:300]}")

        r = await client.get("/api/v1/leave/substitutions/", headers=h)
        body = r.json() if r.status_code == 200 else {}
        subs_list = body.get("substitutions", []) if isinstance(body, dict) else []
        check("GET /leave/substitutions not shadowed by /{leave_id} -> 200",
              r.status_code == 200, f"{r.status_code} {r.text[:160]}")
        check("exactly one substitution after approve", len(subs_list) == 1,
              f"count={len(subs_list)}")

        r = await client.put(f"/api/v1/leave/{leave_id}", headers=h, json={"reason": "retcon"})
        check("approved leave is frozen -> 400",
              r.status_code == 400 and "Cannot edit leave" in r.text,
              f"{r.status_code} {r.text[:160]}")

        r = await client.post(
            "/api/v1/leave/substitutions/",
            headers=h,
            json={
                "leave_id": leave_id,
                "original_faculty_id": str(seed["original"].id),
                "substitute_faculty_id": str(seed["substitute"].id),
                "subject_id": str(seed["subject"].id),
                "section_id": str(seed["section"].id),
                "date": "2030-07-01",
                "time_slot_id": str(seed["slot"].id),
            },
        )
        check("manual substitution auto-resolves timetable_id -> 201",
              r.status_code == 201 and r.json().get("timetable_id") == str(seed["timetable"].id),
              f"{r.status_code} {r.text[:200]}")

        r = await client.post(
            "/api/v1/load",
            headers=h,
            json={
                "faculty_id": str(seed["original"].id),
                "academic_term_id": str(seed["term"].id),
                "subject_id": str(seed["subject"].id),
                "class_id": str(seed["class"].id),
                "section_id": str(seed["section"].id),
                "session_type": "THEORY",
                "theory_hours": 3,
            },
        )
        check("create faculty load (enum column insert) -> 201",
              r.status_code == 201, f"{r.status_code} {r.text[:200]}")

        r = await client.get(
            "/api/v1/reports/faculty-load",
            headers=h,
            params={"academic_term_id": str(seed["term"].id)},
        )
        check("reports/faculty-load gated by LOAD_READ -> 200",
              r.status_code == 200, f"{r.status_code} {r.text[:160]}")

        r = await client.post("/api/v1/users/", headers=h)
        check("users create stub -> 501", r.status_code == 501, f"{r.status_code}")

        r = await client.get("/api/v1/notifications/", headers=h)
        notes = (r.json() or {}).get("notifications", []) if r.status_code == 200 else []
        check("notifications list -> 200", r.status_code == 200, f"{r.status_code}")
        check("leave approver notified", len(notes) >= 1, f"count={len(notes)}")

    from app.database.connection import AsyncSessionLocal
    from app.database.models import AuditLog, Substitution
    from app.database.models.leave import Leave
    from app.database.models.notification import Notification

    async with AsyncSessionLocal() as db:
        subs = (
            await db.execute(select(Substitution).where(Substitution.leave_id == UUID(leave_id)))
        ).scalars().all()
        check("two substitutions persisted (approve + manual)", len(subs) == 2,
              f"count={len(subs)}")
        check("every substitution carries timetable_id",
              all(s.timetable_id == seed["timetable"].id for s in subs),
              ",".join(str(s.timetable_id) for s in subs))
        check("substitute faculty resolved on approvals",
              any(s.substitute_faculty_id == seed["substitute"].id for s in subs), "")

        audits = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.entity_type == "LEAVE",
                    AuditLog.entity_id == UUID(leave_id),
                    AuditLog.action == "APPROVE",
                )
            )
        ).scalars().all()
        check("APPROVE audit row persisted", len(audits) == 1, f"count={len(audits)}")

        note_rows = (await db.execute(select(Notification))).scalars().all()
        check("notification rows written", len(note_rows) >= 2, f"count={len(note_rows)}")

        leave = (
            await db.execute(select(Leave).where(Leave.id == UUID(leave_id)))
        ).scalar_one_or_none()
        check("approved leave visible in a fresh session",
              leave is not None and leave.status == "APPROVED", getattr(leave, "status", "?"))
        ts = getattr(leave, "updated_at", None)
        aware = isinstance(ts, datetime) and ts.tzinfo is not None and (
            ts.utcoffset() == timezone.utc.utcoffset(None)
        )
        check("updated_at is tz-aware UTC", bool(aware), str(ts))

        rows = (await db.execute(text("SELECT count(*) FROM timetable_entries"))).scalar()
        check("timetable_entries readable via raw SQL", rows == 1, f"rows={rows}")


async def main() -> None:
    await reset_schema()
    admin_id = await seed_admin()
    seed = await seed_domain_data(admin_id)
    await run_api(seed)

    failed = [n for n, ok, _ in RESULTS if not ok]
    print("\n=== PG API SMOKE SUMMARY ===")
    print(f"total={len(RESULTS)} passed={len(RESULTS) - len(failed)} failed={len(failed)}")
    for name in failed:
        print(f"  FAILED: {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
