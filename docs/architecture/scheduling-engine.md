# Scheduling Engine (OR-Tools CP-SAT)

## Overview

The scheduling engine uses Google OR-Tools CP-SAT solver to find feasible and optimal timetables satisfying all hard constraints while minimizing soft constraint violations.

## Problem Formulation

### Sets

- `F`: Faculty members
- `S`: Sections
- `B`: Batches (subset of sections)
- `R`: Resources (classrooms, software labs, hardware labs)
- `T`: Time slots (from TimetableTemplate)
- `Sub`: Subjects
- `A`: Teaching Assignments (faculty, subject, section/batch, session_type, hours)

### Decision Variables

```
x[a, r, t] ∈ {0, 1}  for each assignment a ∈ A, resource r ∈ R, time slot t ∈ T
```

Where:
- `x[a, r, t] = 1` if assignment `a` is scheduled in resource `r` at time `t`
- Only created for valid (a, r, t) combinations (domain reduction)

### Derived Variables

```
faculty_at[f, t] = Σ x[a, r, t] where a.faculty = f
section_at[s, t] = Σ x[a, r, t] where a.section = s
batch_at[b, t]   = Σ x[a, r, t] where a.batch = b
resource_at[r, t] = Σ x[a, r, t]
```

## Hard Constraints

### C1: Assignment Coverage
Each assignment must be scheduled for its required hours:
```
Σ_{r,t} x[a, r, t] = a.hours_per_week  ∀ a ∈ A
```

### C2: Faculty Conflict
No faculty in two places at once:
```
Σ_{a: a.faculty=f, r} x[a, r, t] ≤ 1  ∀ f ∈ F, t ∈ T
```

### C3: Section Conflict
No section in two places at once (theory):
```
Σ_{a: a.section=s, a.session_type=LECTURE, r} x[a, r, t] ≤ 1  ∀ s ∈ S, t ∈ T
```

### C4: Batch Conflict
No batch in two places at once (practical):
```
Σ_{a: a.batch=b, r} x[a, r, t] ≤ 1  ∀ b ∈ B, t ∈ T
```

### C5: Resource Conflict
No resource double-booked:
```
Σ_a x[a, r, t] ≤ 1  ∀ r ∈ R, t ∈ T
```

### C6: Resource Type Matching
```
x[a, r, t] = 0  if a.session_type=PRACTICAL and r.type ≠ a.required_lab_type
x[a, r, t] = 0  if a.session_type=LECTURE and r.type ≠ CLASSROOM
```

### C7: Capacity
```
x[a, r, t] = 0  if a.section.strength > r.capacity (for lectures)
x[a, r, t] = 0  if a.batch.strength > r.capacity (for practicals)
```

### C8: Availability
```
x[a, r, t] = 0  if faculty a.faculty unavailable at t
x[a, r, t] = 0  if resource r unavailable at t
```

### C9: Template Compliance
```
x[a, r, t] = 0  if t.slot_type ≠ TEACHING
```

### C10: Batch Parallelism
All batches of a section for same practical subject must be scheduled simultaneously:
```
For each practical assignment group (same subject, same section, different batches):
  x[a1, r1, t] = x[a2, r2, t] = ...  ∀ t ∈ T
```

### C11: Shift Compliance
Morning shift faculty only in morning slots, etc. (if specified)

## Soft Constraints (Objective Terms)

### SC1: Faculty Day Distribution
Penalize multiple sessions same day:
```
penalty = Σ_f Σ_d max(0, Σ_{t∈day_d} faculty_at[f, t] - 1) * w1
```

### SC2: Faculty Gap Minimization
Penalize gaps in faculty day:
```
For each faculty f, day d:
  sessions = sorted(t where faculty_at[f, t] = 1)
  gaps = Σ (sessions[i+1].period - sessions[i].period - 1)
  penalty += gaps * w2
```

### SC3: Student Gap Minimization
Similar for sections/batches

### SC4: Room Continuity
Prefer same room for same assignment:
```
penalty = Σ_a (num_distinct_rooms(a) - 1) * w3
```

### SC5: Morning Preference for Theory
```
penalty = Σ_{a: lecture} Σ_{t: late_shift} x[a, r, t] * w4
```

### SC6: Emergency Resource Usage
```
penalty = Σ_{r: emergency} Σ_a Σ_t x[a, r, t] * w5
```

### SC7: Preferred Days/Shifts
```
penalty = Σ_{a,t not in preferred} x[a, r, t] * w6
```

## Objective Function

```
Minimize: w1*SC1 + w2*SC2 + w3*SC3 + w4*SC4 + w5*SC5 + w6*SC6 + w7*SC7
```

Weights configurable via config (default: w1=10, w2=5, w3=3, w4=2, w5=20, w6=5, w7=3)

## Solver Configuration

```python
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 300
solver.parameters.num_search_workers = 8
solver.parameters.log_search_progress = True
solver.parameters.cp_model_probing_level = 2
solver.parameters.linearization_level = 2
solver.parameters.symmetry_level = 2
```

## Solution Extraction

```python
entries = []
for a in assignments:
    for r in resources:
        for t in time_slots:
            if solver.Value(x[a, r, t]) == 1:
                entries.append(TimetableEntry(
                    faculty_id=a.faculty_id,
                    subject_id=a.subject_id,
                    section_id=a.section_id,
                    batch_id=a.batch_id,
                    resource_id=r.id,
                    time_slot_id=t.id,
                    day_of_week=t.day_of_week,
                    session_type=a.session_type
                ))
```

## Re-optimization (Incremental)

### Pinning Strategy
```python
# For unaffected entries from previous version
for entry in pinned_entries:
    model.Add(x[entry.assignment, entry.resource, entry.time_slot] == 1)
```

### Affected Scope Identification
1. Find all entries involving changed faculty/section/resource
2. Find entries in same time slots (ripple effect)
3. Expand by 1-2 degrees for soft constraint propagation
4. Pin everything outside scope

## Validation (Post-Solve)

Independent validator checks:
1. All hard constraints satisfied
2. All assignments covered
3. No conflicts
4. Soft constraint violations reported with scores
5. Comparison with previous version (if re-optimizing)

## Performance Considerations

- Domain reduction: Only create variables for valid (assignment, resource, slot) triples
- Symmetry breaking: Order resources, faculty
- Decomposition: Solve per day or per shift if problem too large
- Warm start: Use previous solution as hint
- Parallel: Multiple workers explore search tree