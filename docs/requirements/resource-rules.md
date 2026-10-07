# Resource Rules

## Resource Types

### Lecture Classroom
- Purpose: Theory lectures, tutorials
- Capacity: Up to 60 students
- Count: 3 normal + 2 emergency

### Software Lab
- Purpose: Programming, simulation, software-based practicals
- Capacity: Up to 20 students (1 per workstation)
- Count: 4 normal + 1 emergency
- Equipment: PCs with required software

### Hardware Lab
- Purpose: Electronics, communication, hardware practicals
- Capacity: Up to 20 students
- Count: 4 normal + 1 emergency
- Equipment: Oscilloscopes, function generators, power supplies, trainers

## Resource Properties

- **Name**: Unique identifier
- **Type**: classroom/software_lab/hardware_lab
- **Capacity**: Maximum students
- **Is Emergency**: Boolean (used only when normal exhausted)
- **Building/Floor**: Location for proximity optimization
- **Features**: JSON list (projector, whiteboard, specific equipment)
- **Availability**: TimeSlot-based availability calendar

## Allocation Rules

1. **Type Matching**
   - Theory → Lecture Classroom
   - Software Practical → Software Lab
   - Hardware Practical → Hardware Lab

2. **Capacity Check**
   - Section strength ≤ Classroom capacity
   - Batch size ≤ Lab capacity

3. **Emergency Fallback**
   - Only allocate emergency when all normal resources of type booked
   - Track emergency usage for reporting

4. **Availability Windows**
   - Resources can have maintenance blocks
   - Resources can be reserved for other departments
   - Default: Available all working periods

## Resource Editing

- Only EDITOR, ADMIN, SUPER_ADMIN can modify resources
- Changes trigger impact analysis
- Audit log entry for every change