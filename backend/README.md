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
- `DEBUG` - Debug mode
- `SECRET_KEY` - Secret key for JWT (required in production)
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string