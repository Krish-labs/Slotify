# Scheduling Rules

## Hard Constraints (Must Satisfy)

### Faculty Constraints
- No faculty double-booked in same time slot
- Faculty not scheduled during leave/unavailability
- Faculty load matches assigned hours exactly

### Class/Section Constraints
- No section double-booked in same time slot
- All assigned subjects scheduled for required hours
- Theory sessions at section level
- Practical sessions at batch level

### Resource Constraints
- No resource double-booked in same time slot
- Room capacity ≥ assigned students
- Lab type matches session type (software/hardware)
- Emergency resources only when normal exhausted

### Batch Constraints
- All batches of a section scheduled for same subject simultaneously (parallel)
- Batch size 20-24 students
- No batch split across multiple resources in same slot

### Timetable Template Constraints
- Sessions only in defined periods
- Respect break periods
- Shift boundaries respected (morning/late)

## Soft Constraints (Optimization Objectives)

### Preferences (with weights)
1. **Faculty continuity** - Same faculty for same subject across week
2. **Day distribution** - Spread subject sessions across days
3. **Compact schedule** - Minimize gaps in faculty/student day
4. **Morning preference** - Theory in morning, practicals in afternoon
5. **Resource locality** - Same room for same subject when possible
6. **Faculty preference** - Honor faculty time preferences when specified

### Penalty Costs
- Gap hours in faculty schedule
- Gap hours in student schedule
- Late shift assignments (if morning available)
- Emergency resource usage
- Split practical batches across non-adjacent slots

## Re-optimization Rules

### Trigger Events
- Load change (add/remove/modify assignment)
- Resource change (add/remove/modify room/lab)
- Faculty availability change
- Leave/substitution
- Template change

### Process
1. Identify affected TimetableEntry records
2. Pin unaffected entries (fixed)
3. Re-optimize only affected scope
4. Validate result
5. Create new TimetableVersion
6. Update all views

### Minimal Disruption
- Maximize pinned entries
- Minimize moved sessions
- Preserve faculty-day assignments where possible