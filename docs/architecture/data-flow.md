# Data Flow Architecture

## End-to-End Flow

```
┌─────────────┐
│  Excel File │
│ (Load Dist) │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  IMPORT PIPELINE                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Excel       │──►│ Data        │──►│ Load        │              │
│  │ Loader      │   │ Validator   │   │ Normalizer  │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                    │                             │
│                                    ▼                             │
│                          ┌─────────────────┐                     │
│                          │ Assignment      │                     │
│                          │ Builder         │                     │
│                          └────────┬────────┘                     │
└───────────────────────────────────│─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  DOMAIN MODEL (TeachingAssignment)                              │
│  Faculty → Section → Subject → Load mapping                     │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  RESOURCE & TEMPLATE SETUP                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Resources   │  │ Availability│  │ Timetable   │              │
│  │ (DB Config) │  │ Calendar    │  │ Template    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  CONSTRAINT ENGINE                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Variables   │  │ Hard        │  │ Soft        │              │
│  │ Definition  │  │ Constraints │  │ Constraints │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                    │                             │
│                                    ▼                             │
│                          ┌─────────────────┐                     │
│                          │ OR-Tools CP-SAT │                     │
│                          └────────┬────────┘                     │
└───────────────────────────────────│─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  SOLUTION EXTRACTION & VALIDATION                               │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │ Solution    │──►│ Independent │                               │
│  │ Extractor   │   │ Validator   │                               │
│  └─────────────┘  └─────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  PERSISTENCE & VERSIONING                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Timetable   │  │ Timetable   │  │ Timetable   │              │
│  │ Version     │  │ Entry       │  │ Audit Log   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  VIEW GENERATION                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Class       │  │ Faculty     │  │ Master      │              │
│  │ Timetable   │  │ Timetable   │  │ Timetable   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  EXPORT PIPELINE                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Class       │  │ Faculty     │  │ Master      │              │
│  │ Exporter    │  │ Exporter    │  │ Exporter    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│                                    │                             │
│                                    ▼                             │
│                          ┌─────────────────┐                     │
│                          │ Excel Files     │                     │
│                          └─────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

## Pipeline Stages Detail

### 1. Import Pipeline (`backend/app/importers/`)

**Excel Loader** (`excel_loader.py`)
- Reads raw Excel files from `data/raw/`
- Returns raw pandas DataFrames
- No business logic

**Load Validator** (`validators/load_validator.py`)
- Validates required columns exist
- Checks data types
- Validates referential integrity (faculty exists, subject exists, etc.)
- Checks for duplicates
- Returns `ValidationResult` with errors/warnings

**Load Normalizer** (`processors/load_normalizer.py`)
- Standardizes faculty names, subject codes
- Maps to canonical IDs
- Handles missing/inferred data
- Outputs normalized `FacultyLoad` records

**Assignment Builder** (`services/assignment_derivation_service.py`)
- Expands load into `TeachingAssignment` records
- Creates batch-level entries for practicals
- Applies default preferences
- Outputs list of `TeachingAssignment` for DB insert

### 2. Constraint Engine (`backend/app/scheduler/`)

**Model** (`model.py`)
- Defines CP-SAT model structure
- Creates decision variables
- Maps domain entities to solver variables

**Variables** (`variables.py`)
- `x[f, s, r, t]` binary variables
- Domain reduction (only valid combinations)
- Symmetry breaking

**Constraints** (`constraints.py`, `hard_constraints.py`, `soft_constraints.py`)
- Hard: Faculty/Section/Resource/Capacity/Template
- Soft: Preferences with weights

**Objectives** (`objectives.py`)
- Weighted sum of soft constraint violations
- Lexicographic optimization (primary: feasibility, secondary: quality)

**Solver** (`solver.py`)
- Configures CP-SAT parameters
- Runs solver with time limit
- Handles multiple solutions
- Returns `SolverResult`

**Solution** (`solution.py`)
- Extracts assignments from solver
- Maps back to domain entities
- Creates `TimetableEntry` records

### 3. Validation (`backend/app/validators/`)

**Timetable Validator** (`timetable_validator.py`)
- Independent from solver
- Checks all hard constraints satisfied
- Checks soft constraint violations
- Returns `ValidationReport` with pass/fail and details

**Conflict Detector** (`conflict_detector.py`)
- Detects faculty/section/resource conflicts
- Reports specific conflicting entries

### 4. Persistence (`backend/app/services/`)

**Version Service** (`version_service.py`)
- Creates new `TimetableVersion`
- Links to parent version
- Records change summary
- Manages version lifecycle

**Timetable Service** (`timetable_service.py`)
- Coordinates generation workflow
- Manages timetable status transitions
- Triggers export jobs

### 5. Export (`backend/app/exporters/`)

**Excel Exporter** (`excel_exporter.py`)
- Base class for all exporters
- Shared formatting logic

**Class/Faculty/Master Exporters**
- Pivot `TimetableEntry` to view-specific layout
- Apply formatting (colors, merged cells, borders)
- Write to `outputs/timetables/`

## Change Propagation Flow

```
Change Event (Load/Resource/Leave/Template)
         │
         ▼
┌────────────────────────────────────────────┐
│  IMPACT ANALYSIS                           │
│  ┌─────────────┐  ┌─────────────┐          │
│  │ Identify    │  │ Pin         │          │
│  │ Affected    │  │ Unaffected  │          │
│  │ Entries     │  │ Entries     │          │
│  └─────────────┘  └─────────────┘          │
└────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│  RE-OPTIMIZATION                           │
│  ┌─────────────┐  ┌─────────────┐          │
│  │ Solve       │  │ Validate    │          │
│  │ Sub-problem │  │ Result      │          │
│  └─────────────┘  └─────────────┘          │
└────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────┐
│  VERSION & PUBLISH                         │
│  ┌─────────────┐  ┌─────────────┐          │
│  │ New Version │  │ Update All  │          │
│  │ with Pinned │  │ Views       │          │
│  └─────────────┘  └─────────────┘          │
└────────────────────────────────────────────┘
```

## Data Contracts

### Between Pipeline Stages

Each stage passes typed objects (Pydantic models):
- `RawLoadData` → `ValidatedLoadData` → `NormalizedLoadData` → `TeachingAssignment[]`
- `TeachingAssignment[]` + `Resources` + `Template` → `SolverInput`
- `SolverResult` → `ValidatedSolution` → `TimetableEntry[]`

### Error Handling

- Each stage returns `Result[T, E]` (success/error)
- Pipeline stops on hard validation errors
- Warnings collected but don't stop pipeline
- All errors logged with context for debugging