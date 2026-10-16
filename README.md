# SchedulAI

Intelligent academic timetable management and constraint-optimization platform for Electronics & Telecommunication (E&TC) department.

## Architecture

- **Frontend**: React + TypeScript + Vite
- **Backend**: Python + FastAPI
- **Database**: PostgreSQL
- **Optimization**: Google OR-Tools CP-SAT
- **Cache/Jobs**: Redis
- **Excel**: openpyxl
- **AI**: Separate module for natural language → structured constraints

## Project Structure

```
SchedulAI/
├── backend/          # FastAPI application
├── frontend/         # React + TypeScript application
├── ai/               # AI constraint interpretation module
├── data/             # Data files (raw, processed, templates, samples)
├── docs/             # Documentation
├── scripts/          # Operational scripts
├── tests/            # Test suites
├── outputs/          # Generated outputs
└── .github/          # CI/CD workflows
```

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Local prototype without login

The development Docker Compose stack enables a reversible local-only auth bypass:

```bash
docker compose up --build
```

It keeps the real API, PostgreSQL, Redis, load-distribution flow, and solver path. The
frontend does not show `/login`, and the backend accepts local requests without a token.
`LOCAL_AUTH_DISABLED` is rejected outside `APP_ENV=development`; the production compose
overlay replaces the development environment and keeps authentication enabled.

The bypass never creates a user or other database record. Protected requests still need
an already-migrated application schema and an active row in `users` so audit, notification,
and timetable-version foreign keys remain valid. A database containing only
`alembic_version` is therefore not a successful timetable-generation setup.

For direct Vite development, use `VITE_AUTH_DISABLED=true` in a local ignored env file.
Leave `VITE_DEMO_MODE=false` when testing real API/database persistence; demo mode serves
fixtures and intentionally blocks writes.

## Data Flow

1. Load Distribution (Excel) → Import & Validate
2. Normalize → Faculty → Section → Subject Mapping
3. TeachingAssignment → Resources + Availability
4. Timetable Template → Constraint Engine (OR-Tools CP-SAT)
5. Independent Validation → Timetable Version → TimetableEntry
6. Class/Faculty/Master Views → Excel Export

## Development Rules

- No microservices (modular monorepo)
- AI does NOT generate timetables directly
- Single TimetableEntry source of truth
- All scheduling logic in `backend/app/scheduler/`
- Validation independent from solver
- Database migrations required
- Environment variables for secrets

## License

MIT
