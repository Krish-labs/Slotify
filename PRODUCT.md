# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + TypeScript (Vite) frontend; FastAPI + Python backend; PostgreSQL + Redis

## Users

Primary users: faculty members and department admins/HODs equally.

- Faculty: view personal timetables, submit leave requests, see teaching load distribution, request substitutions
- Admins/HODs: manage teaching load data (import from Excel), validate constraints, generate timetables via OR-Tools CP-SAT solver, handle substitutions, export reports

Both audiences share workflows around the timetable grid as the central artifact.

## Product Purpose

SchedulAI automates academic timetable generation for departments. It replaces manual spreadsheet-based scheduling with a constraint-solving pipeline: import teaching load from Excel → validate resources and rules → generate conflict-free timetables using OR-Tools CP-SAT → handle substitutions and leave → export master/faculty/class timetables and load reports.

Success means: zero scheduling conflicts, balanced faculty load, and a process that takes hours instead of weeks.

## Positioning

The meaningfully different mechanism is the CP-SAT constraint solver wrapped in a faculty-first workflow. Neighboring products either:
- Are generic scheduling tools without academic domain logic (room types, session types, lab/lecture distinctions, faculty preferences)
- Or are heavyweight ERP modules that require IT deployment and don't expose the solver to faculty

SchedulAI keeps the solver transparent: faculty see constraints, admins tune them, and the generated timetable shows why each slot was chosen.

## Operating Context

- Academic terms (semesters/quarters) with fixed start/end dates
- Teaching load defined per faculty per subject (lecture hours, lab hours, tutorial hours)
- Resources: rooms (lecture halls, labs, tutorial rooms), time slots (typically 1-hour blocks, Mon-Sat), faculty availability
- Constraints: no double-booking, room capacity, faculty max hours/day, lab sessions need consecutive slots, faculty preferences
- Workflows: load import → validation → generation → review → publish → substitution management → leave tracking
- Exports: master timetable (PDF/Excel), faculty timetables, class timetables, load distribution reports

## Capabilities and Constraints

Confirmed functionality:
- Excel-based teaching load import (faculty, subjects, hours, room types)
- Constraint validation (room conflicts, faculty overload, missing resources)
- Timetable generation via OR-Tools CP-SAT with configurable weights
- Substitution management (faculty leave → auto-suggest replacements)
- Leave requests and approval workflow
- Timetable versioning and audit log
- Role-based access (faculty, admin, HOD)

Technical constraints:
- React 18 + TypeScript + Vite frontend (port 5173 dev)
- FastAPI + SQLAlchemy 2.0 + asyncpg backend (port 8000)
- PostgreSQL 16 + Redis 7 (Docker Compose)
- Alembic migrations
- Background worker for long-running generation jobs
- No native mobile apps; responsive web only

Explicitly undecided:
- Multi-tenant (multiple departments/institutions) vs single-tenant
- Real-time collaboration on timetable editing
- Mobile-native offline support

## Brand Commitments

- Name: SchedulAI (established)
- Voice: warm, academic, precise — not corporate or playful
- Visual identity: Source Sans 3 typeface; deep navy core palette; neutral greys/white support; amber/gold accent for active states and highlights
- Personality: warm and academic, approachable but professional, data-first, humane not sterile
- Mood dials: ENERGY 1 (calm, data-first), RHYTHM 2 (consistent with deliberate section breaks), MOTION 1 (hover/focus only, no scroll choreography)

## Evidence on Hand

- DESIGN.md (this project's visual direction, authored by product owner)
- Figma/design files: none committed
- Real data: sample Excel files in `data/raw/` (TT Faculty_16_8_2026.xlsx, Load Distribution.xlsx)
- Demonstrations: none recorded
- Testimonials/case studies: none
- Press: none
- Absences: no marketing site, no public demo, no user research artifacts — future work must not fabricate these

## Product Principles

1. **Faculty-first, not admin-first** — Every screen serves the faculty experience; admin power follows the same visual language
2. **Constraints visible, not hidden** — Faculty see why a slot was assigned; admins tune weights, not black boxes
3. **Data density over decoration** — Timetable grids are the hero; chrome recedes
4. **Calm by default** — Low motion, consistent rhythm, purposeful color
5. **Auditability baked in** — Every change tracked, every generation reproducible

## Accessibility & Inclusion

- WCAG 2.1 AA target for all faculty/admin workflows
- Timetable grids must be navigable by keyboard and readable by screen readers (dense data tables)
- Color not sole carrier of meaning (amber accent paired with icons/labels)
- No motion beyond hover/focus respects prefers-reduced-motion