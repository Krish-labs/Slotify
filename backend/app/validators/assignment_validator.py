from dataclasses import dataclass


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]


class AssignmentValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_assignment(
        self,
        assignment: dict,
        faculty_exists: bool,
        subject_exists: bool,
        section_exists: bool,
        batch_exists: bool = True,
    ) -> ValidationResult:
        self.errors = []
        self.warnings = []

        if not faculty_exists:
            self.errors.append(f"Faculty {assignment.get('faculty_id')} does not exist")
        if not subject_exists:
            self.errors.append(f"Subject {assignment.get('subject_id')} does not exist")
        if not section_exists:
            self.errors.append(f"Section {assignment.get('section_id')} does not exist")
        if assignment.get("batch_id") and not batch_exists:
            self.errors.append(f"Batch {assignment.get('batch_id')} does not exist")

        session_type = assignment.get("session_type")
        if session_type not in ("LECTURE", "PRACTICAL", "TUTORIAL", "PROJECT"):
            self.errors.append(f"Invalid session_type: {session_type}")

        hours = assignment.get("hours_per_week", 0)
        if hours <= 0:
            self.errors.append("hours_per_week must be positive")

        if session_type in ("PRACTICAL", "TUTORIAL") and not assignment.get("batch_id"):
            self.errors.append("Practical and tutorial sessions require a batch_id")

        if session_type == "LECTURE" and assignment.get("batch_id"):
            self.warnings.append("Lecture sessions typically don't need a batch_id")

        preferred_days = assignment.get("preferred_days", [])
        valid_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
        for day in preferred_days:
            if day not in valid_days:
                self.warnings.append(f"Invalid preferred day: {day}")

        preferred_shifts = assignment.get("preferred_shifts", [])
        valid_shifts = ["MORNING", "LATE"]
        for shift in preferred_shifts:
            if shift not in valid_shifts:
                self.warnings.append(f"Invalid preferred shift: {shift}")

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )

    def validate_assignments(
        self,
        assignments: list[dict],
        faculty_map: dict,
        subject_map: dict,
        section_map: dict,
        batch_map: dict,
    ) -> ValidationResult:
        self.errors = []
        self.warnings = []

        for i, assignment in enumerate(assignments):
            result = self.validate_assignment(
                assignment,
                assignment.get("faculty_id") in faculty_map,
                assignment.get("subject_id") in subject_map,
                assignment.get("section_id") in section_map,
                assignment.get("batch_id") in batch_map if assignment.get("batch_id") else True,
            )
            for err in result.errors:
                self.errors.append(f"Assignment {i}: {err}")
            for warn in result.warnings:
                self.warnings.append(f"Assignment {i}: {warn}")

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
        )
