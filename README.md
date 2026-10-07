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