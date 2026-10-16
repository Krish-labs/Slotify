# SchedulAI Backend

FastAPI-based backend for intelligent academic timetable management.

## Phase 1 - Foundation

- FastAPI application with `/api/v1/health` endpoint
- Environment configuration with pydantic-settings
- PostgreSQL connection layer with SQLAlchemy 2.x async
- Alembic for database migrations
- Centralized exception handling
- Basic security foundation
- Comprehensive test coverage
- Ruff linting

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run linting
ruff check .

# Start development server
uvicorn app.main:app --reload
```

## Configuration

Environment variables (see `.env.example`):

- `APP_ENV` - Environment (development/production)
- `DEBUG` - Debug mode (forced off in production)
- `SECRET_KEY` - Secret key for JWT (required in production, 32+ characters;
  development uses an insecure local marker that production rejects at startup)
- `DATABASE_URL` - PostgreSQL connection string (production rejects the
  development password)
- `REDIS_URL` - Redis connection string (production requires a password;
  compose sets `requirepass` from `REDIS_PASSWORD`)
- `API_CORS_ORIGINS` - Explicit trusted origins; `"*"` is rejected in every
  environment, and production rejects the development defaults
- `PASSWORD_MIN_LENGTH` - Minimum password length for new/seeding accounts (default 12)
- `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` / `LOGIN_RATE_LIMIT_WINDOW_SECONDS` - Login throttling
- `AUTH_STATE_BACKEND` - `auto` (Redis when reachable, else local), `redis`
  (require shared state; fails loudly), or `memory` (single-process/tests)
- `LOCAL_AUTH_DISABLED` - development-only local prototype switch. It bypasses
  token and RBAC checks without creating a user record; it is rejected outside
  `APP_ENV=development`.
- `LOCAL_AUTH_USER_EMAIL` - optional email for the existing active database user
  used as the local persistence actor. If unset, the oldest active user is used.

## Production deployment

1. `cp .env.prod.example .env.prod` (repo root) and fill every value with
   `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` output
   where a secret is required. `.env.prod` is Git-ignored; never commit it.
2. If the `postgres_data` volume was created with the development password,
   back up with `pg_dump`, remove the volume, boot with the new password,
   and restore. Changing the password against the old volume only breaks
   connections; PostgreSQL reads it at initialization time.
3. `make prod-build && make prod-up` (or the equivalent `docker compose`
   commands). The stack refuses to boot with missing or development
   credentials, and serves the production frontend build on port 8080.
4. Terminate TLS in front of the stack (reverse proxy / load balancer):
   production auth cookies are `Secure` and browsers will not return them
   over plain HTTP.
