# Slotify production-readiness report

**Assessment date:** 2026-10-15  
**Decision:** **BLOCKED — do not deploy or represent this revision as production ready.**

This is a source-and-test evidence assessment, not a production sign-off. It
does not replace acceptance testing against an approved production-like
environment.

## Executive summary

The project has several positive hardening changes: the production Compose
overlay removes the backend host port, uses a readiness probe, and exposes the
frontend Nginx listener; the backend contains separate `/health` and `/readyz`
routes; and the workbook parser now makes zero-load rows visible rather than
silently ignoring them. Those controls are not sufficient evidence of a safe
release.

Production readiness is blocked by five material gaps:

1. There is no clean, reviewed, publishable source baseline. The current tree
   contains widespread tracked and untracked work, and the only local commit
   contains generated diagnostic files with a workstation path.
2. The real workbook has unresolved in-scope source rows and no authoritative
   mappings or successful full-workload acceptance run.
3. PostgreSQL and Redis behavior has not been verified in a dedicated,
   disposable PostgreSQL environment. The available focused tests use SQLite.
4. The production deployment, public HTTPS edge, TLS redirect behavior, HSTS,
   container runtime, and live reverse-proxy behavior have not been verified.
5. Backup-and-restore, tenant/isolation behavior, and end-to-end authorization
   acceptance have not been demonstrated in the intended environment.

## Release gates

| Gate | Status | Evidence and blocking reason |
| --- | --- | --- |
| Clean release baseline | BLOCKED | `master` is at `d6677a2` and the working tree has extensive modified and untracked content. The initial commit includes `backend/pyright_output.txt`, `backend/pyright_output2.txt`, and `pyright_output3.txt`, which contain local filesystem paths. A follow-up deletion would not remove them from history. |
| Source-workbook reconciliation | BLOCKED | Focused parser tests show 93 Semester-I source rows, 121 demands, and 424 source hours. Rows 53, 54, 55, and 98 are `zero_load_review_required`; they intentionally block readiness/completeness until an authorized reviewer decides whether each is bookkeeping or incomplete data. |
| Authoritative mappings | BLOCKED | Faculty, subject, class/section, academic-term, batch, and resource identity mappings are not supplied or independently approved. The resolver fails closed on missing or ambiguous matches, but that is not evidence that the real institution data maps correctly. |
| Real-workload timetable acceptance | BLOCKED | No successful generation, independent constraint validation, or accepted complete timetable was run for the real workbook against authoritative PostgreSQL master data. |
| PostgreSQL and Redis | BLOCKED | `make test-backend-pg` and `make verify-pg` require a disposable PostgreSQL URL. They were not run because no approved disposable PostgreSQL target was available. Redis dependency behavior was not exercised against Redis. |
| Database migrations | BLOCKED | New untracked migrations exist, but an Alembic upgrade/downgrade and PostgreSQL schema audit were not performed against a disposable database. |
| Production container and networking | NOT RUN | Production Compose defines an internal-only backend and frontend port 8080, but no production image build, container startup, effective Compose validation, or runtime binding inspection was completed in an approved environment. |
| HTTPS and edge security | BLOCKED | Nginx deliberately does not send HSTS because TLS is documented as terminating outside the container. No trusted HTTPS endpoint, certificate configuration, redirect behavior, or edge headers were inspected. |
| Security headers | PARTIALLY VERIFIED | The Nginx configuration sets CSP, `X-Content-Type-Options`, framing, and referrer controls with `always`; live responses, redirects, static files, error paths, and browser compatibility were not checked. |
| Authentication, authorization, and tenant isolation | PARTIALLY VERIFIED | Unit/API tests exist in the tree, but no complete authorization matrix, cross-tenant test, or production identity-provider/session acceptance test was performed. |
| Backup and restore | BLOCKED | No documented, authorized backup was restored to an isolated database and checked for schema, timetable versions, entries, and audit records. |
| Frontend production acceptance | NOT RUN | Frontend typecheck, lint, tests, production build, browser smoke tests, and real API error handling were not run for this assessment. |

## Verified, limited behavior

The following checks passed locally, but they do not establish production
readiness:

```text
cd backend && .venv/bin/python -m pytest -q \
  tests/scheduler/test_workbook_demand.py \
  tests/test_faculty_match.py \
  tests/test_generation_readiness.py
# 33 passed, 18 Pydantic deprecation warnings

cd backend && .venv/bin/ruff check \
  app/scheduler/workbook_demand.py \
  app/services/workbook_schedule_service.py \
  app/services/load_source_service.py \
  app/api/timetable.py \
  tests/scheduler/test_workbook_demand.py \
  tests/test_faculty_match.py \
  tests/test_generation_readiness.py
# passed

git diff --check
git diff --cached --check
# passed
```

The focused tests exercise parser dispositions, conservative faculty matching,
and workbook-readiness diagnostics in the project test setup. They do not
prove PostgreSQL transaction semantics, Redis behavior, production networking,
browser behavior, or institutional source-data correctness.

Black did not pass for the reviewed files: it would reformat
`backend/app/scheduler/workbook_demand.py`,
`backend/tests/test_generation_readiness.py`, and
`backend/tests/scheduler/test_workbook_demand.py`. The direct `black`
executable also has a stale virtual-environment shebang; invoking it as
`python -m black` reached the formatter successfully and reported those three
files.

## Source-workbook risk

The parser's current safety property is preferable to silent omission: a valid
faculty/class/subject row with no positive workload is retained as
`zero_load_review_required`. The current source workbook therefore cannot
report readiness or a complete plan while rows 53, 54, 55, and 98 are pending
review. This is intentionally a release blocker, not a scheduler failure.

The `faculty_workbook` import argument currently points at the timing-reference
workbook. Its implemented contract reads timing intervals; it is not an
authoritative faculty, subject, class, resource, or academic-term source.
Automated cross-workbook identity matching must not be enabled until an
authoritative data contract and review workflow exist.

## Configuration and operational risk

The code contains promising but unverified hardening work:

- `docker-compose.prod.yml` clears the backend's public port mapping and
  configures a readiness healthcheck.
- `frontend/nginx.conf` proxies API traffic to `backend:8000` and defines
  security headers.
- `backend/app/api/health.py` separates liveness (`/health`) from dependency
  readiness (`/readyz`).

These are configuration claims only until all of the following are run in an
approved non-production environment: `docker compose config`, production image
build, startup as the configured non-root user, reverse-proxy request checks,
dependency-failure readiness checks, and header inspection on successful,
redirect, static, not-found, and API-error responses.

## Publication hygiene

The current `.gitignore` excludes real environment files, virtual
environments, databases, raw workbooks, common build outputs, and several
runtime directories. It does not exclude `outputs/workload-acceptance-20261015/`
or all visible local agent configuration (`.agents/`, `.claude/`, `.mcp.json`,
and `opencode.json`). These must remain excluded from a release unless each
file is intentionally reviewed as project documentation/configuration.

The configured remote is `https://github.com/Krish-labs/Slotify.git`. Remote
enumeration was not possible during the assessment because DNS could not
resolve `github.com`. No commit or push was performed.

## Minimum path to a production decision

1. Create a clean publication baseline in a separate checkout from an explicit
   allowlist. Do not rewrite or reset this active working tree. Ensure generated
   diagnostics and local runtime state never enter history.
2. Obtain authorized faculty, subject, class/section, term, batch, resource,
   capacity, and availability mappings. Explicitly resolve or exclude every
   zero-load and otherwise unresolved source row.
3. Run the full real workbook against a disposable PostgreSQL/Redis
   environment with migrations applied. Preserve the source database and prove
   incomplete schedules cannot be marked complete.
4. Run full backend and frontend verification, including formatting/type checks,
   then run the documented PostgreSQL acceptance workflow only against a
   disposable database.
5. Build and run the production Compose configuration in an approved staging
   environment. Verify non-root execution, port exposure, readiness behavior,
   proxying, headers, and error paths.
6. Test backup and restoration into an isolated database, then conduct the
   authorization and tenant-isolation acceptance matrix.
7. Verify the actual HTTPS termination layer before enabling or asserting HSTS.

Until those gates have reproducible evidence, the correct release decision is
**NO-GO / BLOCKED**.
