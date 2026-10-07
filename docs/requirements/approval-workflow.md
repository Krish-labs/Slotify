# Approval Workflow

## Roles & Permissions

| Role | Load Edit | Resource Edit | Timetable Generate | Timetable Approve | View All |
|------|-----------|---------------|-------------------|-------------------|----------|
| SUPER_ADMIN | ✓ | ✓ | ✓ | ✓ | ✓ |
| ADMIN | ✓ | ✓ | ✓ | ✓ | ✓ |
| HOD | ✓ | ✓ | ✓ | ✓ | ✓ |
| EDITOR | ✓ | ✓ | ✗ | ✗ | ✓ |
| FACULTY | ✗ | ✗ | ✗ | ✗ | Own |
| VIEWER | ✗ | ✗ | ✗ | ✗ | ✓ |

## Workflow States

### Load Distribution
1. **DRAFT** - Editor working on load
2. **SUBMITTED** - Editor submits for review
3. **UNDER_REVIEW** - HOD reviewing
4. **APPROVED** - HOD approved, ready for scheduling
5. **REJECTED** - HOD rejected with comments

### Timetable
1. **GENERATED** - Solver produced timetable
2. **VALIDATED** - Passed independent validation
3. **UNDER_REVIEW** - HOD reviewing
4. **APPROVED** - HOD approved, published
5. **PUBLISHED** - Visible to faculty/students
6. **ARCHIVED** - Superseded by new version

## State Transitions

```
Load: DRAFT → SUBMITTED → UNDER_REVIEW → APPROVED
                          ↘ REJECTED → DRAFT

Timetable: GENERATED → VALIDATED → UNDER_REVIEW → APPROVED → PUBLISHED
                                  ↘ REJECTED → GENERATED (re-optimize)
```

## Notifications

- Email/in-app on state changes
- HOD notified on SUBMITTED
- Editor notified on APPROVED/REJECTED
- Faculty notified on PUBLISHED

## Audit Requirements

Every state change records:
- Actor (user ID)
- Timestamp
- Previous state
- New state
- Comments
- Changed fields (for load/resource edits)