# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SchedulAI Monorepo                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Frontend   │  │   Backend    │  │     AI       │         │
│  │  (React/TS)  │◄─┤  (FastAPI)   │──┤  (Python)    │         │
│  └──────────────┘  └──────┬───────┘  └──────┬───────┘         │
│                           │                 │                  │
│                    ┌──────▼───────┐  ┌──────▼───────┐         │
│                    │  PostgreSQL  │  │    Redis     │         │
│                    │  (Primary)   │  │  (Cache/Jobs)│         │
│                    └──────────────┘  └──────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Frontend | React + TypeScript + Vite | 18+ / 5+ |
| Backend | FastAPI + Python | 3.11+ |
| Database | PostgreSQL | 16+ |
| ORM | SQLAlchemy 2.0 + Alembic | 2.0+ |
| Cache/Queue | Redis | 7+ |
| Optimization | Google OR-Tools CP-SAT | 9.8+ |
| Excel | openpyxl | 3.1+ |
| Auth | JWT (PyJWT) | 2.8+ |
| Validation | Pydantic v2 | 2.7+ |
| Testing | pytest / Vitest | latest |

## Module Boundaries

### Backend (`backend/app/`)
```
app/
├── core/           # Config, security, permissions, exceptions, logging
├── database/       # Connection, models, migrations
├── api/            # REST endpoints (thin, delegate to services)
├── schemas/        # Pydantic request/response models
├── services/       # Business logic (transactional)
├── scheduler/      # OR-Tools CP-SAT engine (isolated)
├── validators/     # Independent validation (no solver dependency)
├── importers/      # Excel → domain objects
├── processors/     # Data transformation pipelines
├── exporters/      # Domain objects → Excel
└── workers/        # Background job handlers
```

### Frontend (`frontend/src/`)
```
src/
├── components/     # Reusable UI components
├── pages/          # Route-level page components
├── layouts/        # Page layouts
├── hooks/          # Custom React hooks
├── services/api/   # API client (TanStack Query)
├── store/          # Global state (Zustand/Redux)
├── types/          # TypeScript types (shared with backend via OpenAPI)
├── utils/          # Helpers
└── constants/      # Enums, config
```

### AI (`ai/`)
```
ai/
├── prompts/        # Prompt templates
├── schemas/        # JSON schemas for structured output
├── services/       # Python services calling LLM
└── tests/
```

## Data Flow

```
Load Distribution (Excel)
        │
        ▼
Excel Import (importers/excel_loader.py)
        │
        ▼
Data Validation (validators/load_validator.py)
        │
        ▼
Load Normalization (processors/load_normalizer.py)
        │
        ▼
Faculty→Section→Subject Mapping (services/assignment_derivation_service.py)
        │
        ▼
TeachingAssignment (database/models/teaching_assignment.py)
        │
        ▼
Resources + Availability (database/models/resource.py)
        │
        ▼
Timetable Template (database/models/timetable_template.py)
        │
        ▼
Constraint Engine (scheduler/model.py + constraints.py)
        │
        ▼
OR-Tools CP-SAT Solver (scheduler/solver.py)
        │
        ▼
Independent Validator (validators/timetable_validator.py)
        │
        ▼
Timetable Version + TimetableEntry (database/models/timetable.py)
        │
        ▼
Class / Faculty / Master Views (exporters/)
        │
        ▼
Excel Export (exporters/excel_exporter.py)
```

## Key Design Principles

1. **Single Source of Truth**: `TimetableEntry` only
2. **Separation of Concerns**: Scheduler isolated from API/DB
3. **Independent Validation**: Validator doesn't use solver
4. **Version Everything**: TimetableVersion for every change
5. **Audit Trail**: All mutations logged
6. **Configuration over Code**: Resources, periods in DB
7. **AI as Constraint Parser**: Never generates timetable directly