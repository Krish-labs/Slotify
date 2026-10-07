# SchedulAI Requirements

## Project Overview

SchedulAI is an intelligent academic timetable management and constraint-optimization platform initially built for the Electronics & Telecommunication (E&TC) department.

## Core Deliverables

1. **Class/Section Timetable** - Timetable view for each class/section
2. **Faculty Timetable** - Individual faculty timetable
3. **Master Timetable** - Comprehensive department-wide timetable

## Primary Input

- **Faculty Load Distribution** - Excel file containing faculty teaching assignments

## Supported Features

### Mapping & Assignment
- Faculty → Section → Subject → Load mapping
- Practical batch scheduling
- Teaching assignment management

### Resource Management
- Classroom management (lecture halls)
- Software lab management
- Hardware lab management
- Emergency resource allocation
- Resource availability tracking

### Faculty Management
- Faculty availability tracking
- Leave management
- Substitution management

### Editorial Controls
- Load editing by authorized editorial users
- Resource editing by authorized editorial users

### Conflict Detection
- Faculty clashes
- Class/student clashes
- Resource clashes

### Timetable Operations
- Timetable versioning
- Change impact analysis
- Minimal-disruption re-optimization
- Excel import/export
- Timetable validation

### Workflow
- HOD approval workflow
- Audit logging

### Future Extensibility
- AI-assisted constraint interpretation (natural language → structured constraints)

## Non-Functional Requirements

- Modular monorepo architecture (no microservices)
- Role-based access control
- Comprehensive audit trail
- Data integrity and validation
- Scalable for future departments