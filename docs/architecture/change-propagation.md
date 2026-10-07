# Change Propagation & Re-optimization

## Overview

When scheduling inputs change, the system must efficiently update the timetable with minimal disruption while maintaining all constraints.

## Change Types

| Change Type | Source | Affected Entities |
|-------------|--------|-------------------|
| Load Change | FacultyLoad add/edit/delete | TeachingAssignment, TimetableEntry |
| Resource Change | Resource add/edit/delete/availability | TimetableEntry (resource assignments) |
| Faculty Availability | Leave, Substitution, explicit unavailability | TimetableEntry (faculty assignments) |
| Template Change | TimeSlot add/edit/delete, shift change | All TimetableEntry |
| Batch/Section Change | Section strength, batch restructuring | TeachingAssignment, TimetableEntry |

## Propagation Algorithm

### Phase 1: Impact Analysis

```python
def analyze_impact(change: ChangeEvent) -> ImpactReport:
    affected_entries = set()
    
    # Direct impact
    if change.type == LOAD_CHANGE:
        affected_entries.update(find_entries_by_assignment(change.assignment_ids))
    elif change.type == RESOURCE_CHANGE:
        affected_entries.update(find_entries_by_resource(change.resource_id))
    elif change.type == FACULTY_AVAILABILITY:
        affected_entries.update(find_entries_by_faculty_time(change.faculty_id, change.time_range))
    elif change.type == TEMPLATE_CHANGE:
        affected_entries.update(find_entries_by_time_slots(change.time_slot_ids))
    
    # Ripple impact (soft constraint propagation)
    ripple_entries = find_ripple_impact(affected_entries, depth=2)
    affected_entries.update(ripple_entries)
    
    # Unaffected = all - affected
    all_entries = get_current_timetable_entries()
    pinned_entries = all_entries - affected_entries
    
    return ImpactReport(
        affected_entries=affected_entries,
        pinned_entries=pinned_entries,
        change_scope=calculate_scope(affected_entries)
    )
```

### Phase 2: Sub-problem Construction

```python
def build_subproblem(impact: ImpactReport) -> SolverInput:
    # Variables only for affected assignments
    affected_assignments = get_assignments_for_entries(impact.affected_entries)
    
    # Pinned entries become fixed constraints
    pinned_constraints = []
    for entry in impact.pinned_entries:
        pinned_constraints.append(
            x[entry.assignment, entry.resource, entry.time_slot] == 1
        )
    
    # Only affected time slots and resources in domain
    affected_slots = get_time_slots_for_entries(impact.affected_entries)
    affected_resources = get_resources_for_entries(impact.affected_entries)
    
    return SolverInput(
        assignments=affected_assignments,
        resources=affected_resources,
        time_slots=affected_slots,
        pinned_constraints=pinned_constraints
    )
```

### Phase 3: Re-optimization

```python
def reoptimize(subproblem: SolverInput) -> SolverResult:
    model = build_model(subproblem)
    
    # Add pinned constraints as hard constraints
    for constraint in subproblem.pinned_constraints:
        model.Add(constraint)
    
    # Solve with same objective
    solver = CpSolver()
    solver.parameters.max_time_in_seconds = 60  # Shorter for incremental
    status = solver.Solve(model)
    
    return extract_solution(solver, subproblem)
```

### Phase 4: Validation & Versioning

```python
def commit_changes(result: SolverResult, impact: ImpactReport, change: ChangeEvent):
    # Create new version
    new_version = TimetableVersion(
        timetable_id=current_timetable.id,
        version_number=current_version + 1,
        parent_version_id=current_version.id,
        change_type=change.type,
        change_summary=generate_summary(change, impact),
        status=VALIDATING
    )
    
    # Combine pinned + new entries
    all_entries = list(impact.pinned_entries) + result.new_entries
    
    # Validate combined result
    validation = validate_timetable(all_entries)
    if not validation.passed:
        new_version.status = REJECTED
        new_version.validation_errors = validation.errors
        save(new_version)
        raise ValidationError(validation.errors)
    
    # Success
    new_version.status = VALIDATED
    save(new_version)
    save_entries(new_version.id, all_entries)
    
    # Update views (async)
    trigger_view_regeneration(new_version.id)
    
    return new_version
```

## Pinning Strategies

### Conservative (Maximum Pinning)
- Pin all entries not directly affected
- Safest, least disruption
- May miss better global optimum

### Balanced (Default)
- Pin entries outside ripple radius (depth=2)
- Allow local rearrangement for quality
- Good balance of stability/quality

### Aggressive (Minimum Pinning)
- Only pin entries with no constraint connection
- Maximum optimization freedom
- Risk of cascading changes

## Conflict Resolution

When re-optimization fails (no feasible solution):

1. **Relax soft constraints** - Increase weights gradually
2. **Expand scope** - Include more entries in re-optimization
3. **Emergency resources** - Allow emergency resource usage
4. **Manual intervention** - Flag for HOD/Editor resolution

## Audit Trail

Every change propagation creates:
- `TimetableVersion` with change metadata
- `AuditLog` entries for each modified `TimetableEntry`
- `Notification` to affected faculty

## API for Change Trigger

```
POST /api/v1/timetable/{id}/reoptimize
{
  "change_type": "LOAD_CHANGE",
  "change_details": {...},
  "pinning_strategy": "BALANCED",
  "triggered_by": "user_id"
}

Response:
{
  "version_id": "uuid",
  "status": "VALIDATED",
  "affected_entries": 15,
  "pinned_entries": 142,
  "solve_time_seconds": 12.3
}
```

## Testing Scenarios

1. Single load hour change → minimal entries affected
2. Faculty leave for week → all their entries reoptimized
3. Room maintenance → all entries in that room reoptimized
4. New batch added → practical sessions restructured
5. Template period moved → cascade to all entries in that period
6. Multiple simultaneous changes → combined impact analysis