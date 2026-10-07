# SchedulAI Project Skill

## Purpose

This skill defines how an AI coding agent should understand, modify, test, and review the **SchedulAI** codebase.

SchedulAI is a production-oriented academic timetable management platform for the **E&TC department**. Its primary business input is **Faculty Load Distribution**. From approved teaching-load data, the system derives teaching assignments and later generates:

1. Class/Section timetable
2. Faculty timetable
3. Master timetable

The project must remain deterministic, auditable, safe, and maintainable. AI is an optional assistance/explanation layer. **AI must not generate or directly decide the timetable. OR-Tools CP-SAT is the scheduling engine.**

---

## 1. Core Engineering Principles

### 1.1 Single source of truth

The canonical scheduling record is `TimetableEntry`.

Class, Faculty, and Master timetables are projections/views of the canonical timetable data.

Do not create separate independent timetable truths that can drift apart.

### 1.2 Deterministic scheduling

Scheduling decisions belong to the solver/business-rule layer.

- Use **Google OR-Tools CP-SAT** for scheduling.
- Use explicit hard and soft constraints.
- Use deterministic validation before publication.
- AI may parse natural language into structured constraints or explain results.
- Never allow an LLM to directly invent a timetable.

### 1.3 Explicit infeasibility

Never silently drop required teaching sessions.

When required constraints cannot be satisfied, return an explicit infeasible result with useful diagnostics.

### 1.4 Auditability

Important mutations must be auditable, including create/update/archive, load approval, assignment derivation, timetable generation/publication, and later leave/substitution actions.

Do not mutate historical records in ways that destroy traceability.

### 1.5 Minimal-disruption changes

When timetable data changes:

- Preserve unaffected entries where possible.
- Pin unaffected entries.
- Re-optimize only the affected scope.
- Record the resulting timetable version/diff.

### 1.6 Production database discipline

Production schema changes must go through **Alembic migrations**.

Never add `Base.metadata.create_all()` to production application startup as a shortcut.

Test fixtures may create isolated schemas/tables when appropriate, but production startup must remain migration-driven.

---

## 2. Locked Scheduling Rules

These rules are authoritative project requirements.

### Working days

Monday–Saturday.

### Shifts

Morning shift: `8:00 AM–3:00 PM`

Late shift: `10:00 AM–5:15 PM`

The final period `4:15 PM–5:15 PM` is valid and must not be rejected merely because it is the final hour.

### Practical batches

Typical practical batch size: `20–24 students`.

Practical sessions may run in parallel in separate labs.

Use source batches such as `A1, B1, C1` when represented in the source data.

### Project / PBL

Project/PBL sessions are **section-level** unless a later approved requirement explicitly changes this.

### Faculty availability

Faculty are assumed available during valid college periods unless leave or explicit availability data says otherwise.

### Resources

Normal lecture classrooms: `3`

Emergency lecture classrooms: `2`

Normal software labs: `4`

Emergency software lab: `1`

Normal hardware labs: `4`

Emergency hardware lab: `1`

Lecture capacity: `60`

Lab capacity: `20`

Actual batch size is stored separately and must not be confused with nominal lab capacity.

### Resource types

The required resource classes are:

- `CLASSROOM`
- `SOFTWARE_LAB`
- `HARDWARE_LAB`

Do not silently replace these with unrelated categories.

---

## 3. Project Architecture

### Repository

```text
SchedulAI/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── docker-compose.yml
├── Makefile
├── docs/
│   ├── requirements/
│   ├── architecture/
│   ├── api/
│   └── decisions/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── templates/
│   └── sample/
├── backend/
├── frontend/
├── ai/
├── scripts/
├── tests/
├── outputs/
└── .github/
```

### Backend

```text
backend/
├── pyproject.toml
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── Dockerfile
└── app/
    ├── main.py
    ├── core/
    ├── database/
    │   └── models/
    ├── api/
    ├── schemas/
    ├── services/
    ├── scheduler/
    ├── validators/
    ├── importers/
    ├── processors/
    ├── exporters/
    └── workers/
```

### Main stack

Backend: FastAPI, Python, PostgreSQL, SQLAlchemy 2.x, Alembic, Pydantic v2/pydantic-settings, Redis/background jobs, openpyxl, OR-Tools CP-SAT.

Frontend: React 18, TypeScript, Vite, TanStack Query, Zustand.

AI: separate module for natural-language-to-structured-constraints and explanations only.

---

## 4. Domain Model

The intended data model includes:

- Department
- AcademicTerm
- Faculty
- FacultyLoad
- TeachingAssignment
- Class
- Section
- Batch
- Subject
- Resource
- ResourceAvailability
- FacultyAvailability
- TimetableTemplate
- TimeSlot
- Timetable
- TimetableEntry
- TimetableVersion
- Leave
- Substitution
- Permission
- AuditLog

Important rules:

- Faculty belongs to an academic context/department.
- Loads belong to faculty and academic terms.
- TeachingAssignment is derived from approved FacultyLoad.
- Class/section/batch/subject references must come from persisted domain data.
- Resource and faculty availability must be represented explicitly.
- Timetable versions are immutable/auditable.
- Historical records should be preserved through archive/soft-delete semantics where required.

Never hard-code mappings such as `faculty A -> subject X -> section Y` when the database can resolve those relationships.

---

## 5. Source Excel Data

Important source files include:

```text
data/raw/Load Distribution.xlsx
data/raw/TT Faculty_16_8_2026(1).xlsx
```

The raw files are authoritative inputs for development/testing where explicitly requested.

### Data safety rule

**Never modify source Excel files.**

Excel workflow:

`Upload → validate → preview → commit`

Preview must not persist unapproved changes.

Invalid/ambiguous data must be reported explicitly.

Expected validation includes required columns, data types, duplicate rows, invalid references, invalid session type, semester validity, negative/invalid hours, practical requiring a batch, and ambiguous faculty/class/subject/section/batch references.

---

## 6. Faculty Load Management

Faculty Load Distribution is the primary scheduling demand.

The system should support:

- Faculty CRUD
- Faculty archive/restore
- FacultyLoad CRUD
- AcademicTerm management
- Load validation
- System-calculated total load
- Excel import preview
- Excel import commit
- duplicate detection
- reference resolution
- TeachingAssignment derivation
- faculty/class/subject load reports
- audit/history
- server-side authorization

### Total load

`total_hours` must be calculated by the system from structured load data.

Do not trust user-supplied totals when the system can derive them.

Ensure calculated values are correctly exposed in API responses using proper Pydantic v2 serialization when necessary.

### TeachingAssignment

Teaching assignments must be derived from approved FacultyLoad data:

`Approved FacultyLoad → TeachingAssignment`

No hard-coded faculty/class/subject mapping is allowed.

---

## 7. API Design Rules

Use versioned APIs:

`/api/v1/...`

Principles:

- validate request bodies with Pydantic
- return correct HTTP status codes
- keep domain logic in services rather than routers
- use reusable dependencies
- enforce authorization server-side
- return structured errors
- avoid leaking internal exceptions
- keep endpoints thin

Authentication and authorization are different:

- Authentication answers: “Who is this user?”
- Authorization answers: “What may this user do?”

JWT authentication alone is not sufficient for protected business operations.

At minimum use basic roles such as:

- SUPER_ADMIN
- ADMIN
- HOD
- EDITOR
- FACULTY
- VIEWER

(Always reference them through the `Role` enum in `app/core/permissions.py`.)

Use reusable role/permission dependencies rather than duplicating authorization logic in each endpoint.

---

## 8. Audit Rules

Audit important mutations and approvals.

When values contain dates, datetimes, enums, UUIDs, or other non-JSON-native objects, serialize them through a centralized audit serialization mechanism.

Do not place raw `date` objects or other unsupported values directly into JSON columns.

Provide an audit-history query API when the phase requires retrieval, for example:

`GET /api/v1/audit-logs`

with useful filters supported by the current model.

---

## 9. SQLAlchemy Rules

Use SQLAlchemy 2.x consistently.

When defining relationships:

- configure foreign keys explicitly where multiple FK paths exist
- do not delete a relationship merely to make a mapper error disappear
- verify the actual domain relationship
- resolve ambiguous foreign keys with explicit `foreign_keys`
- use cascades deliberately

After changing models, run mapper/import tests early.

---

## 10. Pydantic Rules

Use Pydantic v2 conventions.

Prefer `ConfigDict` over legacy inner `Config` classes.

Computed API fields should use the appropriate Pydantic v2 mechanism such as `@computed_field` when a derived property must be serialized.

---

## 11. Time and Date Handling

Use timezone-aware UTC timestamps.

Prefer:

```python
datetime.now(timezone.utc)
```

over deprecated `datetime.utcnow()`.

Dates/datetimes must be normalized consistently before persistence and audit serialization.

---

## 12. Testing Philosophy

Tests must be real and finite.

Do not create test loops where the agent endlessly adds tests because a prompt says “comprehensive.”

Use a defined acceptance suite.

### Minimum Phase 2 test categories

Faculty:

- create
- duplicate employee ID rejection
- update
- get/list
- archive
- restore

FacultyLoad:

- create
- update/delete as allowed
- reference validation
- invalid values
- practical/batch rules
- duplicate/conflict detection
- calculated total hours

Excel:

- valid preview
- invalid rows
- duplicate rows
- ambiguous references
- preview does not commit
- commit persists validated data
- failed commit rolls back

TeachingAssignment:

- approved load derives correctly
- unapproved load is excluded
- duplicate assignment protection
- no hard-coded mapping

Reports:

- faculty totals
- class totals
- subject totals
- reconciliation with stored FacultyLoad data

Authorization:

- unauthenticated request rejected
- authorized role succeeds
- unauthorized role rejected

Audit:

- important mutation creates audit record
- audit record is queryable where API exists

Database:

- migration correctness
- real DB integration when available
- test isolation

### Testing execution discipline

When fixing failures:

1. Run the failing test/module.
2. Fix the actual defect.
3. Rerun the targeted test.
4. Add only missing acceptance coverage.
5. Run the full suite once.
6. Run lint/typecheck once after functional stabilization.

Do not repeatedly rerun the whole repository after every tiny change.

Do not weaken tests simply to make them pass.

---

## 13. Code Quality

Backend formatting/linting:

```bash
cd backend
make format
make lint
```

Type checking:

```bash
make typecheck
```

Testing:

```bash
make test
```

Frontend:

```bash
cd frontend
npm run typecheck
```

Run frontend tests with the repository's configured Vitest command.

### Ruff

Do not perform a blind global `ruff --fix` across future modules.

Fix errors deliberately, especially unused imports, import ordering, whitespace, line length, incorrect typing, and dead code.

Formatting must not hide functional defects.

---

## 14. Phase Discipline

### Phase 1

Infrastructure foundation: FastAPI, health endpoint, config, SQLAlchemy, PostgreSQL integration, Alembic, logging, exception handling, basic security foundation, tests, Ruff, Docker/dev configuration.

No Excel ingestion or timetable generation.

### Phase 2

Faculty & Teaching Load Management:

- Faculty
- AcademicTerm
- FacultyLoad
- load validation
- Excel preview/commit
- TeachingAssignment derivation
- load reports
- audit/history
- RBAC

### Phase 3

Only begin after Phase 2 acceptance is complete.

Do not automatically start Phase 3 because Phase 2 tests pass partially.

### Later scheduling work

Later features may include TimetableTemplate, TimeSlot, hard/soft constraints, OR-Tools CP-SAT timetable generation, timetable validation, resource/faculty/student/class/batch clash prevention, reoptimization, timetable versioning, HOD approval, and publish workflow.

---

## 15. Strict Scope Rules

### MUST

- inspect the current codebase before changing it
- preserve existing working behavior
- fix root causes
- verify changes with real tests
- use migrations for production schema changes
- keep APIs versioned
- keep authorization server-side
- preserve auditability
- preserve source Excel files
- clearly distinguish PASS / FAIL / NOT VERIFIED

### MUST NOT

- start the next phase automatically
- invent business rules when requirements are unresolved
- silently drop sessions
- use LLM output as the timetable solver
- hard-code database mappings
- bypass authorization
- add fake tests
- claim a test passed without running it
- claim PostgreSQL/Docker/Alembic verification when infrastructure was unavailable
- replace a real domain relationship with deletion just to suppress a SQLAlchemy error
- modify raw source Excel files
- introduce unrelated refactors during a scoped phase

---

## 16. Handling Ambiguity

The project follows a strict **“do not guess”** policy for unresolved requirements.

When behavior is undefined:

1. inspect project documentation
2. inspect existing models/services/tests
3. inspect original requirements/source material if available
4. preserve current behavior when safe
5. ask for clarification when the missing decision materially changes design

Do not silently invent rules.

---

## 17. Safe Change Propagation

When changing a core entity:

1. inspect its model
2. inspect schemas
3. inspect services
4. inspect API dependencies
5. inspect migrations
6. inspect tests
7. inspect downstream projections/relationships

Prefer small, reviewable changes.

A fix that breaks historical data, auditability, or another phase is not acceptable.

---

## 18. Review Reporting

Every formal phase review must report only verified status.

Use:

- `PASS`
- `FAIL`
- `NOT VERIFIED`

Do not mark unavailable infrastructure as PASS.

Final report format:

```text
Phase Status: COMPLETE / NOT COMPLETE

Verification:
- Requirement: PASS / FAIL / NOT VERIFIED

Tests:
- Targeted tests: X passed / Y failed
- Full suite: X passed / Y failed

Lint:
- PASS / FAIL

Typecheck:
- PASS / FAIL / NOT VERIFIED

Database/Migrations:
- PASS / FAIL / NOT VERIFIED

Critical Findings:
...

Remaining Issues:
...

Next Phase Readiness:
READY / NOT READY
```

---

## 19. Preferred Agent Workflow

When asked to implement or fix a feature:

### Step 1 — Understand

Read the relevant requirements, models, services, API/router, tests, and migrations.

### Step 2 — Verify current behavior

Run the smallest relevant test/check.

### Step 3 — Implement

Make the smallest production-safe change that satisfies the requirement.

### Step 4 — Regression check

Run related tests.

### Step 5 — Quality check

Run lint/typecheck where relevant.

### Step 6 — Final verification

Run the defined acceptance suite and then stop.

Never keep coding merely because optional improvements are available.

---

## 20. Known Failure Patterns From Previous Reviews

The codebase has previously encountered issues including:

- auth dependency override mismatches in tests
- SQLAlchemy ambiguous foreign-key relationship configuration
- incorrect SQLAlchemy relationship joins
- practical-without-batch validation placed inside an unreachable branch
- hard-delete behavior where historical preservation is expected
- enum-vs-string comparison bugs in TeachingAssignment derivation
- date serialization failures in audit logging
- missing audit-log retrieval API
- RBAC tests failing because dependency wiring was inconsistent
- legacy Pydantic `Config`
- deprecated `datetime.utcnow()`
- frontend TypeScript errors
- high Ruff error counts
- frontend Vitest timeout
- migration files being absent/empty in some repository states

Treat these as failure patterns to check for, not assumptions that the current repository still has every issue.

Always inspect the current state first.

---

## 21. Golden Rule

**Make SchedulAI deterministic, auditable, database-safe, testable, and phase-disciplined.**

When in doubt:

> Preserve the source of truth, preserve historical data, validate explicitly, fix the root cause, verify with real tests, and do not move to the next phase until the current phase is actually complete.
