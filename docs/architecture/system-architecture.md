# System Architecture Details

## Component Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                         External Systems                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │   Excel     │  │   Email     │  │   LLM API   │  │  Browser │ │
│  │   Files     │  │   Server    │  │  (OpenAI)   │  │  (User)  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬─────┘ │
└─────────│────────────────│────────────────│─────────────│───────┘
          │                │                │             │
          ▼                ▼                ▼             ▼
┌────────────────────────────────────────────────────────────────────┐
│                        API Gateway (FastAPI)                       │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Auth │ Users │ Faculty │ Load │ Classes │ Resources │ ... │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────┐
│                      Service Layer                                 │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────┐ │
│  │  Auth Svc  │ │ Faculty Svc│ │ Load Svc   │ │ Timetable Svc  │ │
│  └────────────┘ └────────────┘ └────────────┘ └────────────────┘ │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────┐ │
│  │Resource Svc│ │ Leave Svc  │ │Version Svc │ │ ImpactAnalysis │ │
│  └────────────┘ └────────────┘ └────────────┘ └────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
          │
    ┌─────┴─────┬─────────────┐
    ▼           ▼             ▼
┌───────┐ ┌───────────┐ ┌────────────┐
│ Postgres │ │  Redis    │ │ Scheduler  │
│ (Data)   │ │ (Cache/Q) │ │ (OR-Tools) │
└───────┘ └───────────┘ └────────────┘
```

## Database Schema Overview

### Core Entities

```
User ◄───────── Role ◄───────── Permission
    │
    ▼
Faculty ◄────── FacultyLoad ◄────── TeachingAssignment ◄────── Subject
    │                    │                      ▲
    │                    │                      │
    │                    ▼                      │
    │             Section ◄──── Class           │
    │                    │                      │
    │                    ▼                      │
    │             Batch ◄───────────────────────┘
    │
    ▼
Leave ◄──────── Substitution

Resource ◄────── ResourceAvailability
    │
    ▼
TimetableTemplate ◄────── TimeSlot

Timetable ◄────── TimetableVersion ◄────── TimetableEntry
    │                                          │
    │                                          ▼
    └────────────────── Class/Faculty/Master Views
```

## Scheduler Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Constraint Engine                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Variables  │───►│  Constraints │───►│  Objectives  │      │
│  │  (Decision)  │    │  (Hard/Soft) │    │  (Minimize)  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │                │
│         └───────────────────┼───────────────────┘                │
│                             ▼                                    │
│                    ┌──────────────┐                              │
│                    │   CP-SAT     │                              │
│                    │   Solver     │                              │
│                    └──────┬───────┘                              │
│                           │                                      │
│                           ▼                                      │
│                    ┌──────────────┐                              │
│                    │  Solution    │                              │
│                    │  Extractor   │                              │
│                    └──────────────┘                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Variables
- `x[f, s, r, t]` = 1 if faculty `f` teaches section `s` in resource `r` at time `t`
- Binary decision variables for each valid assignment

### Hard Constraints
- One faculty per slot
- One section per slot
- One resource per slot
- Capacity limits
- Availability windows
- Template period compliance

### Soft Constraints (with weights)
- Faculty day distribution
- Student gap minimization
- Room continuity
- Shift preferences

## API Layer

### Authentication
- JWT Bearer tokens
- Role-based access control (RBAC)
- Permission-based endpoint guards

### Endpoints Structure
```
/api/v1/
├── auth/
│   ├── POST /login
│   ├── POST /refresh
│   └── GET  /me
├── users/
├── faculty/
├── load/
├── assignments/
├── classes/
├── sections/
├── batches/
├── subjects/
├── resources/
├── templates/
├── timetable/
├── leave/
├── substitutions/
├── reports/
└── notifications/
```

## Background Jobs

```
Redis Queue (RQ/Celery)
├── timetable_generation     # Long-running solver jobs
├── reoptimization           # Incremental re-solve
├── excel_import             # Large file processing
├── excel_export             # Report generation
└── notification             # Email/push delivery
```

## Security

- TLS in production
- CORS configured for frontend origin
- Rate limiting on auth endpoints
- Input validation via Pydantic
- SQL injection prevention via SQLAlchemy ORM
- Audit logging for all mutations