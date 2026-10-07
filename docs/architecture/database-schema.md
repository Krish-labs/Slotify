# Database Schema

## Naming Conventions

- Tables: `snake_case`, plural (e.g., `faculty_loads`)
- Columns: `snake_case` (e.g., `faculty_id`)
- Primary Keys: `id` (UUID)
- Foreign Keys: `{table}_id` (e.g., `faculty_id`)
- Timestamps: `created_at`, `updated_at` (timezone-aware)
- Soft deletes: `deleted_at` (nullable)

## Core Tables

### users
```sql
id              UUID        PK
email           VARCHAR(255) UNIQUE NOT NULL
hashed_password VARCHAR(255) NOT NULL
full_name       VARCHAR(255)
is_active       BOOLEAN     DEFAULT true
is_superuser    BOOLEAN     DEFAULT false
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

### roles
```sql
id          UUID        PK
name        VARCHAR(50) UNIQUE NOT NULL  -- SUPER_ADMIN, ADMIN, HOD, EDITOR, FACULTY, VIEWER
description TEXT
created_at  TIMESTAMPTZ DEFAULT now()
```

### permissions
```sql
id          UUID        PK
name        VARCHAR(100) UNIQUE NOT NULL  -- e.g., "load:edit", "timetable:generate"
resource    VARCHAR(50) NOT NULL
action      VARCHAR(50) NOT NULL
description TEXT
```

### role_permissions (many-to-many)
```sql
role_id       UUID  FK → roles.id
permission_id UUID  FK → permissions.id
PRIMARY KEY (role_id, permission_id)
```

### user_roles (many-to-many)
```sql
user_id UUID FK → users.id
role_id UUID FK → roles.id
PRIMARY KEY (user_id, role_id)
```

### faculty
```sql
id              UUID        PK
user_id         UUID        FK → users.id (nullable, for faculty portal access)
employee_id     VARCHAR(50) UNIQUE NOT NULL
first_name      VARCHAR(100) NOT NULL
last_name       VARCHAR(100) NOT NULL
email           VARCHAR(255) UNIQUE NOT NULL
phone           VARCHAR(20)
department      VARCHAR(100) DEFAULT 'E&TC'
designation     VARCHAR(100)  -- Professor, Associate Professor, Assistant Professor
joining_date    DATE
is_active       BOOLEAN     DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

### faculty_loads
```sql
id              UUID        PK
faculty_id      UUID        FK → faculty.id
subject_id      UUID        FK → subjects.id
section_id      UUID        FK → sections.id
theory_hours    INTEGER     DEFAULT 0
practical_hours INTEGER     DEFAULT 0
tutorial_hours  INTEGER     DEFAULT 0
academic_year   VARCHAR(20) NOT NULL  -- e.g., "2025-26"
semester        INTEGER     NOT NULL  -- 1-8
is_active       BOOLEAN     DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
UNIQUE (faculty_id, subject_id, section_id, academic_year, semester)
```

### teaching_assignments
```sql
id                  UUID        PK
faculty_id          UUID        FK → faculty.id
subject_id          UUID        FK → subjects.id
section_id          UUID        FK → sections.id
batch_id            UUID        FK → batches.id (nullable, for practicals)
session_type        VARCHAR(20) NOT NULL  -- LECTURE, PRACTICAL, TUTORIAL, PROJECT
hours_per_week      INTEGER     NOT NULL
preferred_days      JSONB       DEFAULT '[]'  -- e.g., ["MON", "WED"]
preferred_shifts    JSONB       DEFAULT '[]'  -- e.g., ["MORNING"]
academic_year       VARCHAR(20) NOT NULL
semester            INTEGER     NOT NULL
is_active           BOOLEAN     DEFAULT true
created_at          TIMESTAMPTZ DEFAULT now()
updated_at          TIMESTAMPTZ DEFAULT now()
```

### classes
```sql
id              UUID        PK
name            VARCHAR(100) NOT NULL  -- e.g., "SE E&TC", "TE E&TC"
year            INTEGER     NOT NULL  -- 2, 3, 4
branch          VARCHAR(50) NOT NULL  -- E&TC
academic_year   VARCHAR(20) NOT NULL
strength        INTEGER     DEFAULT 0
is_active       BOOLEAN     DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
UNIQUE (name, academic_year)
```

### sections
```sql
id              UUID        PK
class_id        UUID        FK → classes.id
name            VARCHAR(10) NOT NULL  -- A, B, C
strength        INTEGER     DEFAULT 0
is_active       BOOLEAN     DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
UNIQUE (class_id, name)
```

### batches
```sql
id              UUID        PK
section_id      UUID        FK → sections.id
name            VARCHAR(20) NOT NULL  -- B1, B2, B3
batch_number    INTEGER     NOT NULL
strength        INTEGER     DEFAULT 0
is_active       BOOLEAN     DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
UNIQUE (section_id, name)
```

### subjects
```sql
id              UUID        PK
code            VARCHAR(20) UNIQUE NOT NULL  -- e.g., "ETC301"
name            VARCHAR(255) NOT NULL
subject_type    VARCHAR(20) NOT NULL  -- THEORY, PRACTICAL, BOTH
credits         INTEGER     DEFAULT 0
theory_hours    INTEGER     DEFAULT 0
practical_hours INTEGER     DEFAULT 0
tutorial_hours  INTEGER     DEFAULT 0
semester        INTEGER     NOT NULL
department      VARCHAR(50) DEFAULT 'E&TC'
is_active       BOOLEAN     DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

### resources
```sql
id              UUID        PK
name            VARCHAR(100) UNIQUE NOT NULL
resource_type   VARCHAR(30) NOT NULL  -- CLASSROOM, SOFTWARE_LAB, HARDWARE_LAB
capacity        INTEGER     NOT NULL
building        VARCHAR(100)
floor           VARCHAR(20)
room_number     VARCHAR(50)
features        JSONB       DEFAULT '[]'  -- ["projector", "whiteboard", "oscilloscope"]
is_emergency    BOOLEAN     DEFAULT false
is_active       BOOLEAN     DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

### resource_availability
```sql
id              UUID        PK
resource_id     UUID        FK → resources.id
day_of_week     INTEGER     NOT NULL  -- 0=Mon, 6=Sun
start_time      TIME        NOT NULL
end_time        TIME        NOT NULL
is_available    BOOLEAN     DEFAULT true
reason          VARCHAR(255)  -- maintenance, reserved, etc.
academic_year   VARCHAR(20) NOT NULL
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
UNIQUE (resource_id, day_of_week, start_time, academic_year)
```

### timetable_templates
```sql
id              UUID        PK
name            VARCHAR(100) NOT NULL
description     TEXT
academic_year   VARCHAR(20) NOT NULL
is_default      BOOLEAN     DEFAULT false
is_active       BOOLEAN     DEFAULT true
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

### time_slots
```sql
id                  UUID        PK
template_id         UUID        FK → timetable_templates.id
day_of_week         INTEGER     NOT NULL  -- 0=Mon, 5=Sat
period_number       INTEGER     NOT NULL
start_time          TIME        NOT NULL
end_time            TIME        NOT NULL
slot_type           VARCHAR(20) NOT NULL  -- TEACHING, BREAK, LUNCH
shift               VARCHAR(20) NOT NULL  -- MORNING, LATE
is_active           BOOLEAN     DEFAULT true
created_at          TIMESTAMPTZ DEFAULT now()
updated_at          TIMESTAMPTZ DEFAULT now()
UNIQUE (template_id, day_of_week, period_number)
```

### timetables
```sql
id              UUID        PK
name            VARCHAR(255) NOT NULL
template_id     UUID        FK → timetable_templates.id
academic_year   VARCHAR(20) NOT NULL
semester        INTEGER     NOT NULL
status          VARCHAR(30) NOT NULL  -- DRAFT, GENERATED, VALIDATED, UNDER_REVIEW, APPROVED, PUBLISHED, ARCHIVED
generated_by    UUID        FK → users.id
approved_by     UUID        FK → users.id (nullable)
approved_at     TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

### timetable_versions
```sql
id              UUID        PK
timetable_id    UUID        FK → timetables.id
version_number  INTEGER     NOT NULL
parent_version  UUID        FK → timetable_versions.id (nullable)
change_summary  TEXT
change_type     VARCHAR(50)  -- LOAD_CHANGE, RESOURCE_CHANGE, LEAVE, SUBSTITUTION, TEMPLATE_CHANGE, FULL_REGENERATION
status          VARCHAR(30) NOT NULL  -- PENDING, VALIDATING, VALIDATED, APPROVED, REJECTED
created_by      UUID        FK → users.id
created_at      TIMESTAMPTZ DEFAULT now()
UNIQUE (timetable_id, version_number)
```

### timetable_entries
```sql
id                  UUID        PK
version_id          UUID        FK → timetable_versions.id
faculty_id          UUID        FK → faculty.id
subject_id          UUID        FK → subjects.id
section_id          UUID        FK → sections.id
batch_id            UUID        FK → batches.id (nullable)
resource_id         UUID        FK → resources.id
time_slot_id        UUID        FK → time_slots.id
day_of_week         INTEGER     NOT NULL
session_type        VARCHAR(20) NOT NULL  -- LECTURE, PRACTICAL, TUTORIAL, PROJECT
is_pinned           BOOLEAN     DEFAULT false  -- For re-optimization
created_at          TIMESTAMPTZ DEFAULT now()
updated_at          TIMESTAMPTZ DEFAULT now()

-- Unique constraint: one entry per resource per time slot per version
UNIQUE (version_id, resource_id, time_slot_id)
-- Unique constraint: one entry per faculty per time slot per version
UNIQUE (version_id, faculty_id, time_slot_id)
-- Unique constraint: one entry per section per time slot per version
UNIQUE (version_id, section_id, time_slot_id)
-- Unique constraint: one entry per batch per time slot per version
UNIQUE (version_id, batch_id, time_slot_id)
```

### leaves
```sql
id              UUID        PK
faculty_id      UUID        FK → faculty.id
leave_type      VARCHAR(30) NOT NULL  -- CASUAL, SICK, EARNED, ON_DUTY, OTHER
start_date      DATE        NOT NULL
end_date        DATE        NOT NULL
start_time      TIME        (nullable, for half-day)
end_time        TIME        (nullable, for half-day)
reason          TEXT
status          VARCHAR(20) DEFAULT 'PENDING'  -- PENDING, APPROVED, REJECTED, CANCELLED
approved_by     UUID        FK → users.id (nullable)
approved_at     TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

### substitutions
```sql
id                  UUID        PK
leave_id            UUID        FK → leaves.id (nullable)
original_faculty_id UUID        FK → faculty.id
substitute_faculty_id UUID      FK → faculty.id
subject_id          UUID        FK → subjects.id
section_id          UUID        FK → sections.id
batch_id            UUID        FK → batches.id (nullable)
date                DATE        NOT NULL
time_slot_id        UUID        FK → time_slots.id
status              VARCHAR(20) DEFAULT 'PENDING'  -- PENDING, APPROVED, REJECTED
approved_by         UUID        FK → users.id (nullable)
approved_at         TIMESTAMPTZ
created_at          TIMESTAMPTZ DEFAULT now()
updated_at          TIMESTAMPTZ DEFAULT now()
```

### notifications
```sql
id              UUID        PK
user_id         UUID        FK → users.id
title           VARCHAR(255) NOT NULL
message         TEXT        NOT NULL
type            VARCHAR(50)  -- INFO, WARNING, ERROR, SUCCESS
reference_type  VARCHAR(50)  -- TIMETABLE, LEAVE, SUBSTITUTION, LOAD
reference_id    UUID
is_read         BOOLEAN     DEFAULT false
created_at      TIMESTAMPTZ DEFAULT now()
```

### audit_logs
```sql
id              UUID        PK
user_id         UUID        FK → users.id (nullable)
action          VARCHAR(100) NOT NULL  -- CREATE, UPDATE, DELETE, APPROVE, REJECT, GENERATE
entity_type     VARCHAR(50) NOT NULL  -- FACULTY, LOAD, TIMETABLE, RESOURCE, etc.
entity_id       UUID
old_values      JSONB
new_values      JSONB
ip_address      INET
user_agent      TEXT
created_at      TIMESTAMPTZ DEFAULT now()

INDEX (entity_type, entity_id)
INDEX (user_id, created_at)
INDEX (created_at)
```

## Indexes

```sql
-- Performance indexes
CREATE INDEX idx_faculty_loads_faculty_year ON faculty_loads(faculty_id, academic_year);
CREATE INDEX idx_teaching_assignments_faculty ON teaching_assignments(faculty_id, academic_year);
CREATE INDEX idx_teaching_assignments_section ON teaching_assignments(section_id, academic_year);
CREATE INDEX idx_timetable_entries_version ON timetable_entries(version_id);
CREATE INDEX idx_timetable_entries_faculty_day ON timetable_entries(version_id, faculty_id, day_of_week);
CREATE INDEX idx_timetable_entries_section_day ON timetable_entries(version_id, section_id, day_of_week);
CREATE INDEX idx_resource_availability_resource_day ON resource_availability(resource_id, day_of_week);
CREATE INDEX idx_leaves_faculty_date ON leaves(faculty_id, start_date, end_date);
CREATE INDEX idx_substitutions_date ON substitutions(date);
```

## Initial Data (Seeds)

### Roles
```sql
INSERT INTO roles (name, description) VALUES
('SUPER_ADMIN', 'Full system access'),
('ADMIN', 'Administrative access'),
('HOD', 'Head of Department - approval authority'),
('EDITOR', 'Can edit load distribution and resources'),
('FACULTY', 'Faculty member - view own timetable'),
('VIEWER', 'Read-only access');
```

### Permissions (sample)
```sql
INSERT INTO permissions (name, resource, action, description) VALUES
('load:create', 'load', 'create', 'Create load distribution'),
('load:read', 'load', 'read', 'View load distribution'),
('load:update', 'load', 'update', 'Edit load distribution'),
('load:delete', 'load', 'delete', 'Delete load distribution'),
('resource:create', 'resource', 'create', 'Create resources'),
('resource:read', 'resource', 'read', 'View resources'),
('resource:update', 'resource', 'update', 'Edit resources'),
('resource:delete', 'resource', 'delete', 'Delete resources'),
('timetable:generate', 'timetable', 'generate', 'Generate timetable'),
('timetable:read', 'timetable', 'read', 'View timetable'),
('timetable:approve', 'timetable', 'approve', 'Approve timetable'),
('timetable:export', 'timetable', 'export', 'Export timetable to Excel'),
('faculty:read', 'faculty', 'read', 'View faculty'),
('leave:create', 'leave', 'create', 'Apply for leave'),
('leave:approve', 'leave', 'approve', 'Approve leave'),
('substitution:create', 'substitution', 'create', 'Create substitution'),
('substitution:approve', 'substitution', 'approve', 'Approve substitution');
```

### Default Resources (E&TC)
```sql
-- Lecture Classrooms (3 normal + 2 emergency)
INSERT INTO resources (name, resource_type, capacity, is_emergency) VALUES
('LH-101', 'CLASSROOM', 60, false),
('LH-102', 'CLASSROOM', 60, false),
('LH-103', 'CLASSROOM', 60, false),
('LH-201', 'CLASSROOM', 60, true),
('LH-202', 'CLASSROOM', 60, true);

-- Software Labs (4 normal + 1 emergency)
INSERT INTO resources (name, resource_type, capacity, is_emergency, features) VALUES
('SL-301', 'SOFTWARE_LAB', 20, false, '["pcs", "projector", "matlab", "python"]'),
('SL-302', 'SOFTWARE_LAB', 20, false, '["pcs", "projector", "matlab", "python"]'),
('SL-303', 'SOFTWARE_LAB', 20, false, '["pcs", "projector", "matlab", "python"]'),
('SL-304', 'SOFTWARE_LAB', 20, false, '["pcs", "projector", "matlab", "python"]'),
('SL-401', 'SOFTWARE_LAB', 20, true, '["pcs", "projector", "matlab", "python"]');

-- Hardware Labs (4 normal + 1 emergency)
INSERT INTO resources (name, resource_type, capacity, is_emergency, features) VALUES
('HL-501', 'HARDWARE_LAB', 20, false, '["oscilloscopes", "function_generators", "power_supplies", "trainers"]'),
('HL-502', 'HARDWARE_LAB', 20, false, '["oscilloscopes", "function_generators", "power_supplies", "trainers"]'),
('HL-503', 'HARDWARE_LAB', 20, false, '["oscilloscopes", "function_generators", "power_supplies", "trainers"]'),
('HL-504', 'HARDWARE_LAB', 20, false, '["oscilloscopes", "function_generators", "power_supplies", "trainers"]'),
('HL-601', 'HARDWARE_LAB', 20, true, '["oscilloscopes", "function_generators", "power_supplies", "trainers"]');
```