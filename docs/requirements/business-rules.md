# Business Rules

## Department Scope

- Initially: Electronics & Telecommunication (E&TC) only
- Extensible to other departments in future

## Academic Structure

- **Class**: Year/Branch combination (e.g., SE E&TC, TE E&TC, BE E&TC)
- **Section**: Division within a class (e.g., Section A, Section B)
- **Batch**: Subdivision of section for practicals (typically 20-24 students)
- **Subject**: Course with theory/practical components

## Faculty Load

- Load defined per faculty per subject per section
- Includes theory hours, practical hours, tutorial hours
- Load distribution is the primary scheduling input

## Session Types

- **Lecture (L)**: Theory sessions, section-level
- **Practical (P)**: Lab sessions, batch-level
- **Tutorial (T)**: Small group sessions, batch-level
- **Project/PBL**: Project-based learning, section-level

## Timetable Structure

- Working days: Monday–Saturday
- Morning shift: 08:00–15:00
- Late shift: 10:00–17:15
- Periods and breaks defined in TimetableTemplate

## Resource Constraints

### Lecture Classrooms
- Normal: 3
- Emergency: 2
- Maximum capacity: 60 students

### Software Labs
- Normal: 4
- Emergency: 1
- Maximum capacity: 20 students

### Hardware Labs
- Normal: 4
- Emergency: 1
- Maximum capacity: 20 students

## Practical Batch Size

- 20–24 students per batch
- Batches derived from section strength

## Faculty Availability

- Default: Available during all valid periods
- Exceptions: Leave, substitutions, explicit unavailability

## Approval Workflow

1. Editor prepares load distribution
2. HOD reviews and approves
3. Timetable generated
4. HOD approves final timetable
5. Published to faculty and students

## Versioning

- Every timetable change creates new version
- Previous versions preserved for rollback
- Audit log tracks all changes